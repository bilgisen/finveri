import json
import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)

try:
    from app.core.d1 import D1Repository
    _HAS_D1 = True
except ImportError:
    _HAS_D1 = False

try:
    from app.core.redis_client import get_redis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

from app.core.config import settings
from app.core.ticker_store import get_ticker, get_all_tickers
from app.models.instrument import (
    Instrument, InstrumentsResponse,
    StockQuote, StockQuotesResponse,
    MarketSummaryItem, MarketSummaryResponse,
    StockDetail,
    TopMoversResponse,
    FundamentalData,
    CompanyProfile, Shareholder,
)
from app.sources.isyatirim import fetch_detail
from app.sources.company_profile import fetch_company_profile
from app.core.workers_cache import cache_get, cache_set

router = APIRouter(
    prefix="/instruments",
    tags=["instruments"],
)

_KEY_DATA = "pool:{data_type}:data"
_KEY_LAST_UPDATED = "pool:{data_type}:last_updated"


def _filter_by_index(data: List[dict], index: str) -> List[dict]:
    """Endeks bileşen listesiyle data'yı filtreler."""
    from app.core.index_store import get_index

    index_data = get_index(index)
    if not index_data:
        raise HTTPException(status_code=404, detail=f"Endeks bulunamadı: {index}")

    members = index_data.get("members") or []
    if not members:
        raise HTTPException(status_code=404, detail=f"Endeks için bileşen listesi yok: {index}")

    member_codes = {str(m.get("code") if isinstance(m, dict) else m).upper() for m in members if m}
    if not member_codes:
        raise HTTPException(status_code=404, detail=f"Endeks için bileşen listesi boş: {index}")

    return [s for s in data if (s.get("code") or "").upper() in member_codes]


async def _read_cache(data_type: str):
    if not _HAS_REDIS:
        return None, None
    r = get_redis()
    key = _KEY_DATA.format(data_type=data_type)
    lu_key = _KEY_LAST_UPDATED.format(data_type=data_type)
    raw = r.get(key)
    last_updated = r.get(lu_key)
    if raw is not None:
        return (json.loads(raw) if raw else None), last_updated
    # Memory miss → KV fallback. Pool keys are written by hono cron AND the
    # 30-min refresh, often from a different isolate; memory is per-isolate,
    # so a cold/warm isolate must not serve stale or empty data.
    try:
        from app.core.workers_cache import cache_get_kv
        raw = await cache_get_kv(key)
        last_updated = await cache_get_kv(lu_key)
    except Exception as e:
        logger.warning("KV fallback read failed for %s: %s", data_type, e)
    return (json.loads(raw) if raw else None), last_updated


@router.get("/", response_model=InstrumentsResponse)
async def get_all_instruments(
    type: Optional[str] = Query(None, description="Tip filtresi: IMKB, Foreks, VIOP, ISEFunds"),
    search: Optional[str] = Query(None, description="Code veya Name içinde arama"),
):
    """Tüm enstrümanları döner (Oyak kaynağı — enstrüman listesi)."""
    data, last_updated = await _read_cache("instruments")

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
async def get_types():
    """Mevcut enstrüman tiplerini döner."""
    data, _ = await _read_cache("instruments")
    if data is None:
        raise HTTPException(status_code=503, detail="Veri henüz cache'e alınmadı.")
    return sorted({i.get("type") for i in data if i.get("type")})


@router.get("/stocks", response_model=StockQuotesResponse)
async def get_bist_stocks(
    search: Optional[str] = Query(None, description="Code veya Name içinde arama"),
):
    """BIST hisse senetlerini fiyat verileriyle döner (AA kaynağı)."""
    data, last_updated = await _read_cache("bist_stocks")

    if data is None:
        return StockQuotesResponse(total=0, last_updated=None, data=[])

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
async def get_gainers(
    period: str = Query("daily", pattern="^(daily|weekly|monthly|yearly|ytd)$", description="Değişim periyodu"),
    sector: Optional[str] = Query(None, description="Sektör filtresi (tickers.json'daki sektör adı)"),
    index: Optional[str] = Query(None, description="Endeks kodu filtresi (bileşen listesi üzerinden, ör. XU100)"),
    limit: int = Query(10, ge=1, le=50, description="Kaç hisse dönsün (max 50)"),
):
    """
    En çok kazandıran hisseler — periyot bazında (günlük/haftalık/aylık/yıllık).
    bist_stocks cache'indeki ilgili değişim alanına göre sıralanır.
    Sıfır değişim ve veri eksik olanlar hariç tutulur.
    """
    from app.services.periodic_movers import compute_periodic_movers

    data, last_updated = await _read_cache("bist_stocks")
    if data is None:
        raise HTTPException(status_code=503, detail="BIST fiyat verisi henüz cache'e alınmadı.")

    if index:
        data = _filter_by_index(data, index)

    movers = compute_periodic_movers(data, period=period, sector=sector, direction="top", limit=limit)

    return TopMoversResponse(
        direction="gainers",
        period=(period or "daily").lower(),
        total=len(movers),
        last_updated=last_updated,
        data=[StockQuote(**{k: v for k, v in i.items() if k in StockQuote.__fields__}) for i in movers],
    )


@router.get("/stocks/losers", response_model=TopMoversResponse, tags=["movers"])
async def get_losers(
    period: str = Query("daily", pattern="^(daily|weekly|monthly|yearly|ytd)$", description="Değişim periyodu"),
    sector: Optional[str] = Query(None, description="Sektör filtresi (tickers.json'daki sektör adı)"),
    index: Optional[str] = Query(None, description="Endeks kodu filtresi (bileşen listesi üzerinden, ör. XU100)"),
    limit: int = Query(10, ge=1, le=50, description="Kaç hisse dönsün (max 50)"),
):
    """
    En çok kaybettiren hisseler — periyot bazında (günlük/haftalık/aylık/yıllık).
    bist_stocks cache'indeki ilgili değişim alanına göre sıralanır.
    """
    from app.services.periodic_movers import compute_periodic_movers

    data, last_updated = await _read_cache("bist_stocks")
    if data is None:
        raise HTTPException(status_code=503, detail="BIST fiyat verisi henüz cache'e alınmadı.")

    if index:
        data = _filter_by_index(data, index)

    movers = compute_periodic_movers(data, period=period, sector=sector, direction="bottom", limit=limit)

    return TopMoversResponse(
        direction="losers",
        period=(period or "daily").lower(),
        total=len(movers),
        last_updated=last_updated,
        data=[StockQuote(**{k: v for k, v in i.items() if k in StockQuote.__fields__}) for i in movers],
    )


@router.get("/stocks/{code}", response_model=StockQuote)
async def get_stock_by_code(code: str):
    """Belirli bir hissenin fiyat verisini döner (AA kaynağı)."""
    data, _ = await _read_cache("bist_stocks")
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


@router.get("/stocks/{code}/company-profile", response_model=CompanyProfile)
def get_company_profile(code: str, refresh: bool = False):
    """
    Şirket Künyesi ve Ortaklık Yapısı — İş Yatırım kaynağı.
    Veri neredeyse hiç değişmez; Workers KV'de 30 gün cache'lenir.
    refresh=true ile cache bypass edilir.
    """
    ticker_upper = code.upper()
    cache_key = f"company_profile:v2:{ticker_upper}"

    if not refresh:
        cached = cache_get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                return CompanyProfile(**data)
            except Exception as e:
                logger.warning("[company-profile] Cache parse hatası: %s", e)

    result = fetch_company_profile(ticker_upper)
    if result is None:
        raise HTTPException(
            status_code=503,
            detail=f"'{code}' için şirket profili alınamadı.",
        )

    try:
        cache_set(cache_key, json.dumps(result, ensure_ascii=False), ttl=settings.COMPANY_PROFILE_CACHE_TTL)
    except Exception as e:
        logger.warning("[company-profile] KV yazma hatası: %s", e)

    return CompanyProfile(**result)


@router.post("/admin/refresh-company-profiles", tags=["admin"])
def refresh_company_profiles(offset: int = 0, limit: int = 20):
    """
    Şirket profillerini toplu halde KV cache'e ön yükler.
    Limit/adet kadar ticker işlenir. Progress için offset kullanılır.
    Tümünü doldurmak için birden çok çağrı yapılabilir.
    """
    from app.core.tickers_data import TICKERS

    codes = sorted(TICKERS.keys())
    batch = codes[offset:offset + limit]
    if not batch:
        return {"status": "done", "total": len(codes), "processed": offset}

    results = {"success": 0, "skipped": 0, "failed": 0, "errors": []}
    profile_ttl = settings.COMPANY_PROFILE_CACHE_TTL

    for code in batch:
        cache_key = f"company_profile:v2:{code}"
        cached = cache_get(cache_key)
        if cached:
            results["skipped"] += 1
            continue
        try:
            data = fetch_company_profile(code)
            if data:
                cache_set(cache_key, json.dumps(data), ttl=profile_ttl)
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(code)
        except Exception as e:
            logger.error("[refresh-profiles] %s: %s", code, e)
            results["failed"] += 1
            results["errors"].append(code)

    return {
        "status": "in_progress",
        "total": len(codes),
        "processed": offset + len(batch),
        "batch": results,
    }


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
    
    data, _ = await _read_cache("bist_stocks")
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
async def get_market_summary(
    category: Optional[str] = Query(None, description="Kategori filtresi: forex, index, commodity, crypto, gold, repo, viop"),
):
    """
    Piyasa özeti — Brent, Altın, USD/TRY, EUR/TRY, BIST 100/500, Bitcoin vb.
    Sitelerin header ticker bandı için tasarlanmıştır.
    """
    data, last_updated = await _read_cache("market_summary")

    if data is None:
        return MarketSummaryResponse(total=0, last_updated=None, data=[])

    if category:
        data = [i for i in data if i.get("category", "").lower() == category.lower()]

    return MarketSummaryResponse(
        total=len(data),
        last_updated=last_updated,
        data=[MarketSummaryItem(**{k: v for k, v in i.items() if k in MarketSummaryItem.__fields__}) for i in data],
    )


@router.get("/indices", tags=["indices"])
async def get_indices():
    """Bilinen BIST endeks listesini fiyat verileriyle döner."""
    from app.core.index_store import get_all_indices
    indices = get_all_indices()
    
    data, last_updated = await _read_cache("market_summary")
    
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


@router.get("/indices/performance", tags=["indices"])
async def get_indices_performance(
    period: str = Query("daily", pattern="^(daily|weekly|monthly|yearly|ytd)$", description="Değişim periyodu"),
):
    """
    Tüm bilinen BIST endekslerinin periyot bazında performansı.

    İş Yatırım OneEndeks'ten on-demand çekilir (her endeks weekClose/
    monthClose/yearClose döndürür) ve KV'de 5 dakika cache'lenir.
    """
    import asyncio

    from app.core.index_store import get_all_indices

    cache_key = f"indices:performance:{period}"
    cached = cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception as e:
            logger.warning("[indices/performance] cache parse hatası: %s", e)

    indices = get_all_indices()
    if not indices:
        raise HTTPException(status_code=404, detail="Endeks listesi bulunamadı.")

    codes = list(indices.keys())
    details = await asyncio.gather(*[asyncio.to_thread(fetch_detail, code) for code in codes])

    base_field = {
        "daily": "day_close",
        "weekly": "week_close",
        "monthly": "month_close",
        "yearly": "year_close",
        "ytd": "year_close",
    }.get((period or "daily").lower(), "day_close")

    rows = []
    for code, det in zip(codes, details):
        if not det:
            continue
        last = det.get("last")
        base = det.get(base_field)
        if last is None or not base:
            continue
        change_pct = round(((float(last) - float(base)) / float(base)) * 100, 2)
        info = indices[code]
        rows.append({
            "code": code,
            "name": info.get("name", code),
            "category": info.get("category"),
            "last_price": float(last),
            "change_pct": change_pct,
        })

    rows.sort(key=lambda r: r["change_pct"], reverse=True)

    result = {
        "success": True,
        "period": (period or "daily").lower(),
        "total": len(rows),
        "data": rows,
    }

    try:
        cache_set(cache_key, json.dumps(result, ensure_ascii=False), ttl=300)
    except Exception as e:
        logger.warning("[indices/performance] KV yazma hatası: %s", e)

    return result


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
async def get_instrument_by_code(code: str):
    """Belirli bir enstrümanı code ile döner (enstrüman listesinden)."""
    data, _ = await _read_cache("instruments")
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
    Workers: D1 database'den direkt okur.
    """
    ticker_upper = code.upper()

    if not _HAS_D1:
        raise HTTPException(status_code=503, detail="D1 database not available")

    from app.core.d1 import get_db
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="D1 database not initialized")

    repo = D1Repository(db)

    prices = await repo.get_prices(ticker_upper, limit)

    if not prices:
        raise HTTPException(status_code=404, detail=f"'{ticker_upper}' için geçmiş veri bulunamadı.")

    return {
        "success": True,
        "ticker": ticker_upper,
        "data": [
            {
                "time": int(datetime.fromisoformat(p["date"]).replace(tzinfo=timezone.utc).timestamp() * 1000),
                "open": p["open"],
                "high": p["high"],
                "low": p["low"],
                "close": p["close"],
                "volume": p["volume"],
            }
            for p in prices
        ]
    }
