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


def _get_cached(prefix: str, ticker: str):
    """Read from KV-backed cache."""
    from app.core.redis_client import get_redis
    r = get_redis()
    raw = r.get(_cache_key(prefix, ticker))
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
        r.setex(_cache_key(prefix, ticker), ttl, json.dumps(data, default=str))
    except Exception:
        pass


# ── NEW ENDPOINTS (3 Content Layers) ──────────────────────────────────────

@router.get("/public/{code}/summary")
async def get_public_summary(code: str):
    """
    Layer: Public | Role: Herkes
    Limited field set: price, basic indicators, regime label, 2-sentence summary.
    """
    ticker = code.upper()
    cached = _get_cached("public", ticker)
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
    cached = _get_cached("member", ticker)
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
    cached = _get_cached("full", ticker)
    if cached:
        return cached

    full = await calculate_full_analysis(ticker, with_breadth=True)
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
    cached = _get_cached(cache_key, "")
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
    result = await generate_ceo_report(ticker.upper())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
