import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.redis_client import get_redis
from app.core.ticker_store import get_ticker, get_all_tickers
from app.models.instrument import (
    Instrument, InstrumentsResponse,
    StockQuote, StockQuotesResponse,
    MarketSummaryItem, MarketSummaryResponse,
    StockDetail,
    TopMoversResponse,
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
