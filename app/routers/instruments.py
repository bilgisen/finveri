import json
import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.history import DailyPrice

from app.core.redis_client import get_redis
from app.core.ticker_store import get_ticker, get_all_tickers
from app.models.instrument import (
    Instrument, InstrumentsResponse,
    StockQuote, StockQuotesResponse,
    MarketSummaryItem, MarketSummaryResponse,
    StockDetail,
    TopMoversResponse,
    FundamentalData,
)
from app.sources.isyatirim import fetch_detail

router = APIRouter(
    prefix="/instruments",
    tags=["instruments"],
)

_KEY_DATA = "pool:{data_type}:data"
_KEY_LAST_UPDATED = "pool:{data_type}:last_updated"


def _read_cache(data_type: str):
    r = get_redis()
    raw = r.get(_KEY_DATA.format(data_type=data_type))
    last_updated = r.get(_KEY_LAST_UPDATED.format(data_type=data_type))
    return (json.loads(raw) if raw else None), last_updated


@router.get("/", response_model=InstrumentsResponse)
def get_all_instruments(
    type: Optional[str] = Query(None, description="Tip filtresi: IMKB, Foreks, VIOP, ISEFunds"),
    search: Optional[str] = Query(None, description="Code veya Name içinde arama"),
):
    """Tüm enstrümanları döner (Oyak kaynağı — enstrüman listesi)."""
    data, last_updated = _read_cache("instruments")

    if data is None:
        raise HTTPException(
            status_code=503,
            detail="Veri henüz cache'e alınmadı. Lütfen kısa süre sonra tekrar deneyin.",
        )

    if type:
        data = [i for i in data if i.get("type", "").lower() == type.lower()]

    if search:
        q = search.lower()
        data = [
            i for i in data
            if q in i.get("code", "").lower()
            or q in i.get("name", "").lower()
            or q in i.get("display_name", "").lower()
        ]

    return InstrumentsResponse(
        total=len(data),
        last_updated=last_updated,
        data=[Instrument(**{k: v for k, v in i.items() if k in Instrument.__fields__}) for i in data],
    )


@router.get("/types", response_model=List[str])
def get_types():
    """Mevcut enstrüman tiplerini döner."""
    data, _ = _read_cache("instruments")
    if data is None:
        raise HTTPException(status_code=503, detail="Veri henüz cache'e alınmadı.")
    return sorted({i.get("type") for i in data if i.get("type")})


@router.get("/stocks", response_model=StockQuotesResponse)
def get_bist_stocks(
    search: Optional[str] = Query(None, description="Code veya Name içinde arama"),
):
    """BIST hisse senetlerini fiyat verileriyle döner (AA kaynağı)."""
    data, last_updated = _read_cache("bist_stocks")

    if data is None:
        raise HTTPException(
            status_code=503,
            detail="BIST fiyat verisi henüz cache'e alınmadı.",
        )

    if search:
        q = search.lower()
        data = [
            i for i in data
            if q in i.get("code", "").lower()
            or q in i.get("name", "").lower()
        ]

    return StockQuotesResponse(
        total=len(data),
        last_updated=last_updated,
        data=[StockQuote(**{k: v for k, v in i.items() if k in StockQuote.__fields__}) for i in data],
    )


@router.get("/stocks/gainers", response_model=TopMoversResponse, tags=["movers"])
def get_gainers(
    limit: int = Query(10, ge=1, le=50, description="Kaç hisse dönsün (max 50)"),
):
    """
    Günün en çok yükselen hisseleri.
    bist_stocks cache'indeki diff_percent değerine göre sıralanır.
    Sıfır değişim ve veri eksik olanlar hariç tutulur.
    """
    data, last_updated = _read_cache("bist_stocks")
    if data is None:
        raise HTTPException(status_code=503, detail="BIST fiyat verisi henüz cache'e alınmadı.")

    gainers = sorted(
        [i for i in data if i.get("diff_percent") and i["diff_percent"] > 0],
        key=lambda x: x["diff_percent"],
        reverse=True,
    )[:limit]

    return TopMoversResponse(
        direction="gainers",
        total=len(gainers),
        last_updated=last_updated,
        data=[StockQuote(**{k: v for k, v in i.items() if k in StockQuote.__fields__}) for i in gainers],
    )


@router.get("/stocks/losers", response_model=TopMoversResponse, tags=["movers"])
def get_losers(
    limit: int = Query(10, ge=1, le=50, description="Kaç hisse dönsün (max 50)"),
):
    """
    Günün en çok düşen hisseleri.
    bist_stocks cache'indeki diff_percent değerine göre sıralanır.
    Sıfır değişim ve veri eksik olanlar hariç tutulur.
    """
    data, last_updated = _read_cache("bist_stocks")
    if data is None:
        raise HTTPException(status_code=503, detail="BIST fiyat verisi henüz cache'e alınmadı.")

    losers = sorted(
        [i for i in data if i.get("diff_percent") and i["diff_percent"] < 0],
        key=lambda x: x["diff_percent"],
    )[:limit]

    return TopMoversResponse(
        direction="losers",
        total=len(losers),
        last_updated=last_updated,
        data=[StockQuote(**{k: v for k, v in i.items() if k in StockQuote.__fields__}) for i in losers],
    )


@router.get("/stocks/{code}", response_model=StockQuote)
def get_stock_by_code(code: str):
    """Belirli bir hissenin fiyat verisini döner (AA kaynağı)."""
    data, _ = _read_cache("bist_stocks")
    if data is None:
        raise HTTPException(status_code=503, detail="BIST fiyat verisi henüz cache'e alınmadı.")

    code_upper = code.upper()
    for item in data:
        if item.get("code", "").upper() == code_upper:
            return StockQuote(**{k: v for k, v in item.items() if k in StockQuote.__fields__})

    raise HTTPException(status_code=404, detail=f"'{code}' kodu bulunamadı.")


@router.get("/stocks/{code}/detail", response_model=StockDetail)
def get_stock_detail(code: str):
    """
    Tek hisse detay verisi — İş Yatırım kaynağı.

    AA'nın toplu verisine ek olarak: limitUp/Down, weekHigh/Low,
    monthHigh/Low, yearClose, capital, equity, circulationShare vb.

    Sonuç 60 saniye cache'lenir (ONDEMAND_CACHE_TTL_SECONDS).
    """
    result = fetch_detail(code.upper())
    if result is None:
        raise HTTPException(
            status_code=503,
            detail=f"'{code}' için İş Yatırım verisi alınamadı.",
        )
    return StockDetail(**result)


@router.get("/stocks/{code}/fundamental", response_model=FundamentalData, tags=["analysis"])
def get_stock_fundamental(code: str):
    """
    Temel analiz verisi — P/E ratio ve finansal rasyolar.

    İş Yatırım'dan fiyat + equity + capital,
    COMP API'den ROE, net_margin vb. rasyolar çeker.
    P/E = Fiyat / ((ROE × Equity) / Capital) formülüyle hesaplanır.

    Sonuç 5 dakika cache'lenir.
    """
    from app.services.fundamental_service import get_fundamental_data

    result = get_fundamental_data(code.upper())
    if result is None:
        raise HTTPException(
            status_code=503,
            detail=f"'{code}' için temel analiz verisi alınamadı.",
        )
    return FundamentalData(**result)


@router.get("/stocks/{code}/header-summary", tags=["analysis"])
async def get_stock_header_summary(code: str):
    """Şirket veya endeks detay sayfası için dinamik 2-3 paragraflık analiz metnini döner."""
    from app.services.summary_generator import generate_header_summary
    result = await generate_header_summary(code)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/stocks/{code}/summary-card", tags=["analysis"])
async def get_stock_summary_card(code: str):
    """UI dashboard kartları ve grid'ler için optimize edilmiş kompakt özet verileri döner."""
    from app.services.ta_engine import generate_llm_summary
    result = await generate_llm_summary(code)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    ticker_upper = code.upper()
    live_price = result.get("close", 0.0)
    
    data, _ = _read_cache("bist_stocks")
    diff_percent = 0.0
    diff_price = 0.0
    display_name = ticker_upper
    
    if data:
        match = next((item for item in data if item.get("code", "").upper() == ticker_upper), None)
        if match:
            diff_percent = match.get("diff_percent", 0.0)
            diff_price = match.get("diff_price", 0.0)
            display_name = match.get("display_name") or match.get("name") or ticker_upper

    return {
        "ticker": ticker_upper,
        "display_name": display_name,
        "last_price": live_price,
        "diff_price": diff_price,
        "diff_percent": diff_percent,
        "trend": result.get("trend", "Nötr"),
        "rsi": result.get("rsi", {}).get("value", 50.0),
        "rsi_status": result.get("rsi", {}).get("status", "Nötr"),
        "macd_status": result.get("macd", "Nötr"),
        "support": result.get("support_resistance", {}).get("support", 0.0),
        "resistance": result.get("support_resistance", {}).get("resistance", 0.0),
        "stop_loss": result.get("atr_stop_loss", 0.0),
        "sma_20": result.get("sma", {}).get("sma_20"),
        "sma_50": result.get("sma", {}).get("sma_50"),
        "sma_200": result.get("sma", {}).get("sma_200"),
    }


@router.get("/market-summary", response_model=MarketSummaryResponse, tags=["market"])
def get_market_summary(
    category: Optional[str] = Query(None, description="Kategori filtresi: forex, index, commodity, crypto, gold, repo, viop"),
):
    """
    Piyasa özeti — Brent, Altın, USD/TRY, EUR/TRY, BIST 100/500, Bitcoin vb.
    Sitelerin header ticker bandı için tasarlanmıştır.
    """
    data, last_updated = _read_cache("market_summary")

    if data is None:
        raise HTTPException(
            status_code=503,
            detail="Piyasa özeti henüz cache'e alınmadı.",
        )

    if category:
        data = [i for i in data if i.get("category", "").lower() == category.lower()]

    return MarketSummaryResponse(
        total=len(data),
        last_updated=last_updated,
        data=[MarketSummaryItem(**{k: v for k, v in i.items() if k in MarketSummaryItem.__fields__}) for i in data],
    )


@router.get("/indices", tags=["indices"])
def get_indices():
    """Bilinen BIST endeks listesini fiyat verileriyle döner."""
    from app.core.index_store import get_all_indices
    indices = get_all_indices()
    
    data, last_updated = _read_cache("market_summary")
    
    result = []
    for code, info in indices.items():
        price_info = {}
        if data:
            match = next((item for item in data if item.get("code", "").upper() == code), None)
            if match:
                price_info = {
                    "last_price": match.get("last_price"),
                    "diff_percent": match.get("diff_percent"),
                    "volume": match.get("volume", 0.0),
                }
        
        result.append({
            **info,
            **price_info
        })
        
    return {
        "success": True,
        "last_updated": last_updated,
        "data": result
    }


@router.get("/tickers", tags=["tickers"])
def get_tickers():
    """Bilinen BIST ticker listesini döner."""
    return get_all_tickers()


@router.get("/tickers/{code}", tags=["tickers"])
def get_ticker_info(code: str):
    """Belirli bir ticker'ın meta bilgilerini döner."""
    ticker = get_ticker(code.upper())
    if not ticker:
        raise HTTPException(status_code=404, detail=f"'{code}' ticker bulunamadı.")
    return ticker


@router.get("/{code}", response_model=Instrument)
def get_instrument_by_code(code: str):
    """Belirli bir enstrümanı code ile döner (enstrüman listesinden)."""
    data, _ = _read_cache("instruments")
    if data is None:
        raise HTTPException(status_code=503, detail="Veri henüz cache'e alınmadı.")

    code_upper = code.upper()
    for item in data:
        if item.get("code", "").upper() == code_upper:
            return Instrument(**{k: v for k, v in item.items() if k in Instrument.__fields__})

    raise HTTPException(status_code=404, detail=f"'{code}' kodu bulunamadı.")


@router.get("/{code}/history")
async def get_instrument_history(code: str, limit: int = Query(500, le=1000)):
    """
    Belirli bir enstrümanın geçmiş OHLCV mum verilerini döner.
    Redis cache: 1 saat TTL ile cache'lenir.
    """
    ticker_upper = code.upper()
    cache_key = f"history:{ticker_upper}:{limit}"
    r = get_redis()
    
    # Redis'ten kontrol et
    try:
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis read failed for history {ticker_upper}: {e}")
    
    # Cache yoksa DB'den çek
    async with AsyncSessionLocal() as session:
        stmt = (
            select(DailyPrice)
            .where(DailyPrice.ticker == ticker_upper)
            .order_by(DailyPrice.date.asc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        prices = res.scalars().all()
        
        if not prices:
            raise HTTPException(status_code=404, detail=f"'{ticker_upper}' için geçmiş veri bulunamadı.")
        
        result = {
            "success": True,
            "ticker": ticker_upper,
            "data": [
                {
                    "time": int(datetime.combine(p.date, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp() * 1000),
                    "open": p.open,
                    "high": p.high,
                    "low": p.low,
                    "close": p.close,
                    "volume": p.volume,
                }
                for p in prices
            ]
        }
        
        # Redis'e cache'le (1 saat TTL)
        try:
            r.setex(cache_key, 3600, json.dumps(result))
        except Exception as e:
            logger.warning(f"Redis write failed for history {ticker_upper}: {e}")
        
        return result
