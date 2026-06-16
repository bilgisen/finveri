"""
Advanced Technical Analysis Endpoints
Pro-level indicators for chatbot context enrichment
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any
import logging

from app.services.ta_engine import get_historical_dataframe
from app.services.advanced_ta import (
    calculate_volume_profile,
    detect_market_regime,
    detect_liquidity_voids,
    calculate_support_resistance_zones
)

router = APIRouter(prefix="/api/v1/ta/advanced", tags=["Advanced Technical Analysis"])
logger = logging.getLogger(__name__)


@router.get("/regime/{ticker}")
async def get_market_regime_endpoint(ticker: str):
    """
    Market Regime Classification
    
    Returns:
    - regime: Strong Trend / Weak Trend / Range Bound / Choppy
    - trend_direction: Bullish / Bearish / Neutral
    - volatility_regime: Normal / High Volatility / Low Volatility
    - recommended_strategy: Trading strategy based on regime
    - confidence: High / Medium / Low
    
    Use Case: Chatbot can recommend appropriate strategies based on current market regime
    """
    try:
        ticker_upper = ticker.upper()
        df = await get_historical_dataframe(ticker_upper, limit=200)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker_upper}")
        
        # Calculate required indicators
        df.ta.adx(length=14, append=True)
        df.ta.atr(length=14, append=True)
        
        result = detect_market_regime(df)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "ticker": ticker_upper,
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regime detection error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/volume-profile/{ticker}")
async def get_volume_profile_endpoint(ticker: str, bars: int = Query(100, ge=50, le=500)):
    """
    Volume Profile Analysis
    
    Returns:
    - poc: Point of Control (highest volume price level)
    - value_area_high: Upper boundary of 70% volume area
    - value_area_low: Lower boundary of 70% volume area
    - profile_bins: Volume distribution across price levels
    
    Use Case: Identify institutional support/resistance levels for chatbot to mention
    """
    try:
        ticker_upper = ticker.upper()
        df = await get_historical_dataframe(ticker_upper, limit=bars)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker_upper}")
        
        result = calculate_volume_profile(df, num_bins=50)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "ticker": ticker_upper,
            "analysis_period_bars": len(df),
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Volume profile error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/liquidity-voids/{ticker}")
async def get_liquidity_voids_endpoint(ticker: str):
    """
    Liquidity Voids / Fair Value Gaps Detection
    
    Returns list of price gaps with:
    - gap_start: Start price of gap
    - gap_end: End price of gap
    - direction: up / down
    - gap_size: Absolute gap size
    - bars_ago: How many bars ago the gap occurred
    
    Use Case: Chatbot can mention unfilled gaps as potential price magnets
    """
    try:
        ticker_upper = ticker.upper()
        df = await get_historical_dataframe(ticker_upper, limit=100)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker_upper}")
        
        voids = detect_liquidity_voids(df, threshold=2.5)
        
        return {
            "ticker": ticker_upper,
            "voids_found": len(voids),
            "liquidity_voids": voids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Liquidity voids error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sr-zones/{ticker}")
async def get_support_resistance_zones_endpoint(ticker: str):
    """
    Multi-Method Support & Resistance Zones
    
    Combines:
    - Swing highs/lows
    - Volume Profile (POC, VAH, VAL)
    - Bollinger Bands
    - Psychological levels (round numbers)
    
    Returns ranked support and resistance zones with strength scores
    
    Use Case: Chatbot provides precise entry/exit levels with confidence scores
    """
    try:
        ticker_upper = ticker.upper()
        df = await get_historical_dataframe(ticker_upper, limit=200)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker_upper}")
        
        # Calculate required indicators
        df.ta.bbands(length=20, std=2, append=True)
        
        result = calculate_support_resistance_zones(df, lookback=60)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "ticker": ticker_upper,
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SR zones error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/full-context/{ticker}")
async def get_full_advanced_context(ticker: str):
    """
    Complete Advanced TA Context in One Call
    
    Returns all advanced analysis combined:
    - Market regime
    - Volume profile
    - Liquidity voids
    - Support/Resistance zones
    
    Use Case: Single endpoint for chatbot to get comprehensive context
    Optimized for chatbot integration
    """
    try:
        ticker_upper = ticker.upper()
        df = await get_historical_dataframe(ticker_upper, limit=200)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker_upper}")
        
        # Calculate all required indicators
        df.ta.adx(length=14, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        
        # Run all analyses
        regime = detect_market_regime(df)
        volume_profile = calculate_volume_profile(df.tail(100), num_bins=50)
        liquidity_voids = detect_liquidity_voids(df, threshold=2.5)
        sr_zones = calculate_support_resistance_zones(df, lookback=60)
        
        # Build chatbot-friendly summary
        current_price = df.iloc[-1]['close']
        
        summary_text = f"""
{ticker_upper} Advanced Analysis Summary:

MARKET REGIME: {regime.get('regime', 'Unknown')} ({regime.get('trend_direction', 'Neutral')})
Strategy: {regime.get('recommended_strategy', 'N/A')}

KEY LEVELS:
"""
        
        if "error" not in volume_profile:
            summary_text += f"• Volume POC (strongest level): {volume_profile['poc']:.2f} TL\n"
            summary_text += f"• Value Area: {volume_profile['value_area_low']:.2f} - {volume_profile['value_area_high']:.2f} TL\n"
        
        if "error" not in sr_zones and sr_zones.get('nearest_support'):
            summary_text += f"• Next Support: {sr_zones['nearest_support']['price']:.2f} TL ({sr_zones['nearest_support']['type']})\n"
        
        if "error" not in sr_zones and sr_zones.get('nearest_resistance'):
            summary_text += f"• Next Resistance: {sr_zones['nearest_resistance']['price']:.2f} TL ({sr_zones['nearest_resistance']['type']})\n"
        
        if liquidity_voids:
            summary_text += f"\nUNFILLED GAPS: {len(liquidity_voids)} liquidity void(s) detected\n"
            for void in liquidity_voids[:2]:
                summary_text += f"• {void['gap_start']:.2f} → {void['gap_end']:.2f} TL ({void['direction']})\n"
        
        return {
            "ticker": ticker_upper,
            "current_price": round(current_price, 2),
            "market_regime": regime,
            "volume_profile": volume_profile,
            "liquidity_voids": liquidity_voids[:5],  # Top 5 only
            "support_resistance_zones": sr_zones,
            "chatbot_summary": summary_text.strip()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Full context error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
