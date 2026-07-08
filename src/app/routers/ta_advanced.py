"""
Advanced Technical Analysis Endpoints — Workers edition (pure Python).
"""
from fastapi import APIRouter, HTTPException, Query
import logging

from app.services.ta_engine import get_historical_prices, _overlay_live_data
from app.services import indicators
from app.services.advanced_ta import (
    calculate_volume_profile,
    detect_market_regime,
    detect_liquidity_voids,
    calculate_support_resistance_zones,
)

router = APIRouter(prefix="/api/v1/ta/advanced", tags=["Advanced Technical Analysis"])
logger = logging.getLogger(__name__)


@router.get("/regime/{ticker}")
async def get_market_regime_endpoint(ticker: str):
    ticker_upper = ticker.upper()
    data = await get_historical_prices(ticker_upper, limit=200)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker_upper}")
    data = _overlay_live_data(ticker_upper, data)
    result = detect_market_regime(data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ticker": ticker_upper, **result}


@router.get("/volume-profile/{ticker}")
async def get_volume_profile_endpoint(ticker: str, bars: int = Query(100, ge=50, le=500)):
    ticker_upper = ticker.upper()
    data = await get_historical_prices(ticker_upper, limit=bars)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker_upper}")
    data = _overlay_live_data(ticker_upper, data)
    result = calculate_volume_profile(data, num_bins=50)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ticker": ticker_upper, "analysis_period_bars": len(data), **result}


@router.get("/liquidity-voids/{ticker}")
async def get_liquidity_voids_endpoint(ticker: str):
    ticker_upper = ticker.upper()
    data = await get_historical_prices(ticker_upper, limit=100)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker_upper}")
    data = _overlay_live_data(ticker_upper, data)
    voids = detect_liquidity_voids(data, threshold=2.5)
    return {"ticker": ticker_upper, "voids_found": len(voids), "liquidity_voids": voids}


@router.get("/sr-zones/{ticker}")
async def get_support_resistance_zones_endpoint(ticker: str):
    ticker_upper = ticker.upper()
    data = await get_historical_prices(ticker_upper, limit=200)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker_upper}")
    data = _overlay_live_data(ticker_upper, data)
    result = calculate_support_resistance_zones(data, lookback=60)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ticker": ticker_upper, **result}


@router.get("/full-context/{ticker}")
async def get_full_advanced_context(ticker: str):
    ticker_upper = ticker.upper()
    data = await get_historical_prices(ticker_upper, limit=200)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker_upper}")
    data = _overlay_live_data(ticker_upper, data)

    regime = detect_market_regime(data)
    volume_profile = calculate_volume_profile(data[-100:], num_bins=50)
    liquidity_voids = detect_liquidity_voids(data, threshold=2.5)
    sr_zones = calculate_support_resistance_zones(data, lookback=60)

    current_price = data[-1]["close"]
    summary_text = (
        f"{ticker_upper} Advanced Analysis Summary:\n\n"
        f"MARKET REGIME: {regime.get('regime', 'Unknown')} ({regime.get('trend_direction', 'Neutral')})\n"
        f"Strategy: {regime.get('recommended_strategy', 'N/A')}\n\nKEY LEVELS:\n"
    )
    if "error" not in volume_profile:
        summary_text += f"Volume POC: {volume_profile['poc']:.2f} TL\n"
        summary_text += f"Value Area: {volume_profile['value_area_low']:.2f} - {volume_profile['value_area_high']:.2f} TL\n"
    if "error" not in sr_zones and sr_zones.get('nearest_support'):
        summary_text += f"Next Support: {sr_zones['nearest_support']['price']:.2f} TL ({sr_zones['nearest_support']['type']})\n"
    if "error" not in sr_zones and sr_zones.get('nearest_resistance'):
        summary_text += f"Next Resistance: {sr_zones['nearest_resistance']['price']:.2f} TL ({sr_zones['nearest_resistance']['type']})\n"
    if liquidity_voids:
        summary_text += f"\nUNFILLED GAPS: {len(liquidity_voids)} detected\n"
        for void in liquidity_voids[:2]:
            summary_text += f"{void['gap_start']:.2f} -> {void['gap_end']:.2f} TL ({void['direction']})\n"

    return {
        "ticker": ticker_upper,
        "current_price": round(float(current_price), 2),
        "market_regime": regime,
        "volume_profile": volume_profile,
        "liquidity_voids": liquidity_voids[:5],
        "support_resistance_zones": sr_zones,
        "chatbot_summary": summary_text.strip(),
    }
