"""
Technical Analysis Router — Restructured for 3 Content Layers.
Endpoints:
  GET /api/v1/ta/public/{kod}/summary    → Public
  GET /api/v1/ta/member/{kod}/summary    → Member
  GET /api/v1/ta/full/{kod}              → Full (Abone)
  GET /api/v1/ta/context/{kod}           → Chatbot (Hono)
  GET /api/v1/ta/batch                   → Screening
   GET /api/v1/ta/{ticker}                → Legacy → redirect /public
   GET /api/v1/ta/summary/{ticker}         → Legacy → redirect /member
   GET /api/v1/ta/ceo-report/{ticker}      → CEO AI Report (Abone)
"""
import json
import logging
from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.services.ta_engine import (
    calculate_full_analysis,
    filter_public,
    filter_member,
    filter_context,
    filter_batch_result,
)
from app.services.ceo_ta_report import generate_ceo_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ta", tags=["Technical Analysis"])


def _cache_key(prefix: str, ticker: str) -> str:
    return f"ta:{prefix}:{ticker.upper()}"


async def _get_cached(prefix: str, ticker: str):
    """Read from KV-backed cache — memory first, KV fallback."""
    from app.core.workers_cache import cache_get, cache_get_kv
    key = _cache_key(prefix, ticker)
    raw = cache_get(key)
    if raw is None:
        raw = await cache_get_kv(key)
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return None


def _set_cache(prefix: str, ticker: str, data: dict, ttl: int):
    """Write to KV-backed cache."""
    try:
        from app.core.redis_client import get_redis
        r = get_redis()
        r.set(_cache_key(prefix, ticker), json.dumps(data, default=str), ex=ttl)
    except Exception:
        pass


def _is_index(code: str) -> bool:
    return code.upper().startswith("X") and len(code.upper()) >= 4


# ── PERIODIC RANKING ───────────────────────────────────────────────────────

@router.get("/rank")
def get_periodic_rank(
    period: str = Query("weekly", pattern="^(daily|weekly|monthly|yearly|ytd)$", description="Değişim periyodu"),
    sector: str = Query(None, description="Sektör filtresi (tickers.json'daki sektör adı)"),
    index: str = Query(None, description="Endeks kodu (bileşen listesi üzerinde sıralama)"),
    direction: str = Query("top", pattern="^(top|bottom)$", description="top: yükselenler, bottom: düşenler"),
    limit: int = Query(10, ge=1, le=50, description="Kaç hisse dönsün (max 50)"),
):
    """
    Periyot bazında sıralama — chatbot ve screener için.

    Seçenekler:
      - Tüm pazar / sektör filtresi
      - Endeks bileşen listesi üzerinde sıralama (index=XU100 gibi)
    """
    from app.core.redis_client import get_redis
    from app.services.periodic_movers import compute_periodic_movers

    r = get_redis()
    raw = r.get("pool:bist_stocks:data")
    if not raw:
        raise HTTPException(status_code=503, detail="BIST fiyat verisi henüz cache'e alınmadı.")
    data = json.loads(raw)

    if index:
        from app.core.index_store import get_index
        index_data = get_index(index)
        if not index_data:
            raise HTTPException(status_code=404, detail=f"Endeks bulunamadı: {index}")
        members = index_data.get("members") or []
        member_codes = {m.get("code") if isinstance(m, dict) else m for m in members}
        member_codes = {str(c).upper() for c in member_codes if c}
        if not member_codes:
            raise HTTPException(status_code=404, detail=f"Endeks için bileşen listesi yok: {index}")
        data = [i for i in data if (i.get("code") or "").upper() in member_codes]

    rows = compute_periodic_movers(data, period=period, sector=sector, direction=direction, limit=limit)

    return {
        "success": True,
        "period": (period or "weekly").lower(),
        "direction": direction,
        "sector": sector,
        "index": index,
        "total": len(rows),
        "data": rows,
    }


# ── NEW ENDPOINTS (3 Content Layers) ──────────────────────────────────────

@router.get("/public/{code}/summary")
async def get_public_summary(code: str):
    """
    Layer: Public | Role: Herkes
    Limited field set: price, basic indicators, regime label, 2-sentence summary.
    """
    ticker = code.upper()
    cached = await _get_cached("public", ticker)
    if cached:
        return cached

    full = await calculate_full_analysis(ticker, with_breadth=False)
    if "error" in full:
        raise HTTPException(status_code=400, detail=full["error"])

    result = filter_public(full)
    _set_cache("public", ticker, result, 300)
    return result


@router.get("/member/{code}/summary")
async def get_member_summary(code: str):
    """
    Layer: Member | Role: Uye
    Extended: indicators, divergences, volume profile, S/R, MTF alignment.
    """
    ticker = code.upper()
    cached = await _get_cached("member", ticker)
    if cached:
        return cached

    full = await calculate_full_analysis(ticker, with_breadth=False)
    if "error" in full:
        raise HTTPException(status_code=400, detail=full["error"])

    result = filter_member(full)
    _set_cache("member", ticker, result, 300)
    return result


@router.get("/full/{code}")
async def get_full_analysis_endpoint(code: str):
    """
    Layer: Advanced | Role: Abone
    Complete dataset: all indicators, patterns, scenarios, risk, composite score.
    Used by AI report generator (via Hono orchestrator).
    """
    ticker = code.upper()
    cached = await _get_cached("full", ticker)
    if cached:
        return cached

    # Indices: skip beta/breadth/relative-strength (meaningless vs themselves)
    full = await calculate_full_analysis(ticker, with_breadth=not _is_index(ticker))
    if "error" in full:
        raise HTTPException(status_code=400, detail=full["error"])

    _set_cache("full", ticker, full, 900)
    return full


@router.get("/context/{code}")
async def get_context_endpoint(
    code: str,
    query_type: str = Query("general", regex="^(general|entry|risk|comparison)$"),
):
    """
    Layer: Chatbot | Role: Hono Orchestrator
    Lightweight, query-optimized context. query_type filters the response:
    - general (default): everything
    - entry: S/R, R/R, scenarios, signals
    - risk: stop-loss, volatility, max drawdown
    - comparison: MTF alignment, relative strength
    """
    ticker = code.upper()
    cache_key = f"context:{ticker}:{query_type}"
    cached = await _get_cached(cache_key, "")
    if cached:
        return cached

    full = await calculate_full_analysis(ticker, with_breadth=False)
    if "error" in full:
        raise HTTPException(status_code=400, detail=full["error"])

    result = filter_context(full, query_type)
    try:
        _set_cache(cache_key, "", result, 300)
    except Exception:
        pass
    return result


@router.post("/batch")
async def batch_screening(request: Request):
    """
    Layer: Screening | Role: Abone/Hono
    POST body: {"tickers": ["THYAO", "ASELS", ...], "filters": {"score_min": 65, ...}}
    Returns lightweight screening results for up to 500 tickers.
    """
    from app.models.technical import BatchTickerRequest
    body_data = await request.json()
    tickers = body_data.get("tickers", [])
    filters = body_data.get("filters", {})

    if not tickers:
        raise HTTPException(status_code=400, detail="tickers list required")
    if len(tickers) > 500:
        raise HTTPException(status_code=400, detail="Max 500 tickers")

    score_min = filters.get("score_min", 0)
    regime_filter = filters.get("regime")
    trend_filter = filters.get("trend")

    results = []
    for code in tickers:
        try:
            full = await calculate_full_analysis(code, with_breadth=False)
            if "error" in full:
                continue
            br = filter_batch_result(full)
            results.append(br)
        except Exception:
            continue

    # Apply filters
    if score_min > 0:
        results = [r for r in results if (r.get("score") or 0) >= score_min]
    if regime_filter:
        results = [r for r in results if r.get("regime") == regime_filter]
    if trend_filter:
        results = [r for r in results if r.get("trend") == trend_filter]

    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    return {
        "results": results,
        "total": len(tickers),
        "filtered": len(results),
    }


# ── LEGACY ENDPOINTS (backward compat redirects) ─────────────────────────

@router.get("/{ticker}")
async def legacy_get_ta(ticker: str):
    """Legacy: redirect to /public/{ticker}/summary"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/api/v1/ta/public/{ticker}/summary", status_code=301)


@router.get("/summary/{ticker}")
async def legacy_get_ta_summary(ticker: str):
    """Legacy: redirect to /member/{ticker}/summary"""
    return RedirectResponse(url=f"/api/v1/ta/member/{ticker}/summary", status_code=301)


@router.get("/ceo-report/{ticker}")
async def get_ceo_report(ticker: str):
    """
    CEO-level AI Technical Analysis Report.
    Returns structured narrative report: overview, key levels, indicators,
    scenarios, volume profile, risk assessment, watchlist.
    Used by Hono orchestrator for subscriber-tier frontend (CeoTaReport.tsx).
    """
    ticker_upper = ticker.upper()
    cached = await _get_cached("ceo", ticker_upper)
    if cached:
        return cached

    result = await _generate_ceo_report_cached(ticker_upper)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


async def _generate_ceo_report_cached(ticker: str):
    """Generate CEO report, cache with market-aware TTL (stock vs index same)."""
    result = await generate_ceo_report(ticker)
    if "error" not in result:
        ttl = _market_ttl(300, 3600)
        _set_cache("ceo", ticker, result, ttl)
    return result


def _market_ttl(open_ttl: int, closed_ttl: int) -> int:
    """Market-aware TTL: shorter during trading hours, longer when closed."""
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=3))
    now = datetime.now(ist)
    if now.weekday() >= 5:
        return closed_ttl
    market_open = 9 <= now.hour < 18
    return open_ttl if market_open else closed_ttl
