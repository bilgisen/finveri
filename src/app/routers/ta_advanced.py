"""
Legacy Advanced TA Endpoints — Delegates to new ta_engine pipeline.
Kept for backward compatibility. All logic is in ta_engine.calculate_full_analysis().
"""
from fastapi import APIRouter, HTTPException, Query
import logging

from app.services.ta_engine import calculate_full_analysis

router = APIRouter(prefix="/api/v1/ta/advanced", tags=["Advanced Technical Analysis (Legacy)"])
logger = logging.getLogger(__name__)


@router.get("/regime/{ticker}")
async def get_market_regime_endpoint(ticker: str):
    full = await calculate_full_analysis(ticker.upper())
    if "error" in full:
        raise HTTPException(status_code=400, detail=full["error"])
    return {"ticker": ticker.upper(), **full.get("regime", {})}


@router.get("/volume-profile/{ticker}")
async def get_volume_profile_endpoint(ticker: str, bars: int = Query(100, ge=50, le=500)):
    full = await calculate_full_analysis(ticker.upper())
    if "error" in full:
        raise HTTPException(status_code=400, detail=full["error"])
    vp = full.get("volume_profile", {})
    return {
        "ticker": ticker.upper(),
        "analysis_period_bars": bars,
        **vp,
    }


@router.get("/liquidity-voids/{ticker}")
async def get_liquidity_voids_endpoint(ticker: str):
    full = await calculate_full_analysis(ticker.upper())
    if "error" in full:
        raise HTTPException(status_code=400, detail=full["error"])
    voids = full.get("liquidity_voids", [])
    return {"ticker": ticker.upper(), "voids_found": len(voids), "liquidity_voids": voids}


@router.get("/sr-zones/{ticker}")
async def get_support_resistance_zones_endpoint(ticker: str):
    full = await calculate_full_analysis(ticker.upper())
    if "error" in full:
        raise HTTPException(status_code=400, detail=full["error"])
    sr = full.get("sr_zones", {})
    return {"ticker": ticker.upper(), **sr}


@router.get("/full-context/{ticker}")
async def get_full_advanced_context(ticker: str):
    full = await calculate_full_analysis(ticker.upper())
    if "error" in full:
        raise HTTPException(status_code=400, detail=full["error"])
    current_price = full.get("price", 0)
    summary_lines = [
        f"{ticker.upper()} Advanced Analysis Summary:\n",
        f"MARKET REGIME: {full.get('regime', {}).get('regime', 'Unknown')} ({full.get('regime', {}).get('trend_direction', 'Neutral')})",
        f"Strategy: {full.get('regime', {}).get('recommended_strategy', 'N/A')}",
        "\nKEY LEVELS:",
    ]
    vp = full.get("volume_profile", {})
    if "error" not in vp and vp.get("poc"):
        summary_lines.append(f"Volume POC: {vp['poc']:.2f} TL")
        summary_lines.append(f"Value Area: {vp['value_area_low']:.2f} - {vp['value_area_high']:.2f} TL")
    sr = full.get("sr_zones", {})
    if isinstance(sr, dict):
        ns = sr.get("nearest_support")
        nr = sr.get("nearest_resistance")
        if ns:
            summary_lines.append(f"Next Support: {ns.get('price', 0):.2f} TL ({ns.get('type', 'S/R')})")
        if nr:
            summary_lines.append(f"Next Resistance: {nr.get('price', 0):.2f} TL ({nr.get('type', 'S/R')})")
    voids = full.get("liquidity_voids", [])
    if voids:
        summary_lines.append(f"\nUNFILLED GAPS: {len(voids)} detected")
        for void in voids[:2]:
            summary_lines.append(f"{void.get('gap_start', 0):.2f} -> {void.get('gap_end', 0):.2f} TL ({void.get('direction', '?')})")
    score = full.get("score", {})
    return {
        "ticker": ticker.upper(),
        "current_price": round(float(current_price), 2),
        "market_regime": full.get("regime"),
        "volume_profile": vp,
        "liquidity_voids": voids[:5],
        "support_resistance_zones": sr,
        "score": score.get("total", 50),
        "signals": [s["label"] for s in full.get("signals", [])[:5]],
        "chatbot_summary": "\n".join(summary_lines),
    }
