"""
Advanced Technical Analysis Module
Pro-level indicators for institutional-grade analysis
"""
from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import numpy as np
except ImportError:
    np = None

logger = logging.getLogger(__name__)


def calculate_volume_profile(df: pd.DataFrame, num_bins: int = 50) -> Dict[str, Any]:
    """
    Calculates Volume Profile with POC (Point of Control), Value Area High/Low
    Essential for institutional-level support/resistance identification
    
    Returns:
        - poc: Price level with highest volume (strongest support/resistance)
        - value_area_high: Upper boundary of 70% volume area
        - value_area_low: Lower boundary of 70% volume area
        - profile_bins: Complete volume distribution
    """
    try:
        if df.empty or len(df) < 20:
            return {"error": "Insufficient data for volume profile"}
        
        # Define price range and bins
        price_min = df['low'].min()
        price_max = df['high'].max()
        price_range = price_max - price_min
        
        if price_range == 0:
            return {"error": "Zero price range"}
        
        bin_size = price_range / num_bins
        
        # Calculate volume for each price level
        bins = []
        for i in range(num_bins):
            low = price_min + (i * bin_size)
            high = low + bin_size
            
            # Sum volume where price traded in this bin
            mask = (df['close'] >= low) & (df['close'] < high)
            volume = df.loc[mask, 'volume'].sum()
            
            if volume > 0:
                bins.append({
                    'price': round((low + high) / 2, 2),
                    'volume': float(volume)
                })
        
        if not bins:
            return {"error": "No volume data available"}
        
        # Find POC (Point of Control - highest volume node)
        poc = max(bins, key=lambda x: x['volume'])
        
        # Calculate Value Area (70% of total volume)
        total_volume = sum(b['volume'] for b in bins)
        sorted_bins = sorted(bins, key=lambda x: x['volume'], reverse=True)
        
        cumulative_volume = 0
        value_area_bins = []
        
        for b in sorted_bins:
            cumulative_volume += b['volume']
            value_area_bins.append(b)
            if cumulative_volume >= total_volume * 0.70:
                break
        
        # Get VAH and VAL
        vah = max(value_area_bins, key=lambda x: x['price'])['price']
        val = min(value_area_bins, key=lambda x: x['price'])['price']
        
        return {
            "poc": round(poc['price'], 2),
            "poc_volume": round(poc['volume'], 0),
            "value_area_high": round(vah, 2),
            "value_area_low": round(val, 2),
            "total_volume": round(total_volume, 0),
            "value_area_volume_pct": 70,
            "profile_bins": bins[:10]  # Return top 10 for context
        }
        
    except Exception as e:
        logger.error(f"Volume profile calculation error: {e}")
        return {"error": str(e)}


def detect_market_regime(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Classifies market into: Strong Trend / Weak Trend / Range / High Volatility
    Essential for strategy selection and chatbot context
    
    Uses:
    - ADX for trend strength
    - Efficiency Ratio for trend quality
    - ATR/Price for volatility classification
    """
    try:
        if df.empty or len(df) < 30:
            return {"error": "Insufficient data for regime detection"}
        
        # Calculate ADX if not present
        if 'ADX_14' not in df.columns:
            df.ta.adx(length=14, append=True)
        
        # Calculate ATR if not present
        if 'ATRr_14' not in df.columns:
            df.ta.atr(length=14, append=True)
        
        last_row = df.iloc[-1]
        adx = last_row.get('ADX_14', 0)
        atr = last_row.get('ATRr_14', 0)
        close = last_row.get('close', 0)
        
        # Efficiency Ratio (Kaufman's formula)
        # Measures how efficiently price moves from A to B
        lookback = min(20, len(df) - 1)
        change = abs(df['close'].iloc[-1] - df['close'].iloc[-lookback-1])
        volatility = df['close'].diff().abs().tail(lookback).sum()
        efficiency_ratio = change / volatility if volatility > 0 else 0
        
        # Volatility as percentage of price
        volatility_pct = (atr / close) * 100 if close > 0 else 0
        
        # Calculate trend direction
        sma_20 = df['close'].rolling(20).mean().iloc[-1]
        sma_50 = df['close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else sma_20
        
        trend_direction = "Bullish" if close > sma_20 and sma_20 > sma_50 else \
                         "Bearish" if close < sma_20 and sma_20 < sma_50 else "Neutral"
        
        # Regime Classification
        regime = ""
        strategy = ""
        confidence = 0
        
        if adx > 25 and efficiency_ratio > 0.5:
            regime = "Strong Trend"
            strategy = "Trend Following: Use MA crossovers, Supertrend, breakout strategies"
            confidence = 90
            
        elif adx > 20 and efficiency_ratio > 0.3:
            regime = "Weak Trend"
            strategy = "Hybrid: Combine trend following with mean reversion filters"
            confidence = 70
            
        elif adx < 20:
            regime = "Range Bound"
            strategy = "Mean Reversion: Use RSI, Bollinger Bands, support/resistance trades"
            confidence = 75
            
        else:
            regime = "Choppy / Uncertain"
            strategy = "Reduce position size, wait for clarity"
            confidence = 40
        
        # Volatility adjustment
        volatility_regime = "Normal"
        if volatility_pct > 4:
            volatility_regime = "High Volatility"
            strategy += " | Widen stop-losses, reduce leverage"
        elif volatility_pct < 1.5:
            volatility_regime = "Low Volatility"
            strategy += " | Potential breakout ahead, monitor closely"
        
        return {
            "regime": regime,
            "trend_direction": trend_direction,
            "volatility_regime": volatility_regime,
            "adx": round(adx, 1),
            "efficiency_ratio": round(efficiency_ratio, 2),
            "volatility_pct": round(volatility_pct, 2),
            "confidence": confidence,
            "recommended_strategy": strategy,
            "interpretation": f"{regime} piyasa rejimi ({trend_direction} yönlü), {volatility_regime} volatilite ile karakterize ediliyor."
        }
        
    except Exception as e:
        logger.error(f"Market regime detection error: {e}")
        return {"error": str(e)}


def detect_liquidity_voids(df: pd.DataFrame, threshold: float = 2.5) -> List[Dict[str, Any]]:
    import pandas as pd
    """
    Detects price gaps with low volume (liquidity voids/fair value gaps)
    Critical for institutional entry/exit points
    
    Args:
        threshold: Gap size multiplier vs average range
    """
    try:
        if df.empty or len(df) < 20:
            return []
        
        df = df.copy()
        df['price_range'] = df['high'] - df['low']
        avg_range = df['price_range'].rolling(20).mean()
        
        voids = []
        
        for i in range(1, min(len(df), 60)):  # Check last 60 bars
            gap = abs(df.iloc[-i]['open'] - df.iloc[-i-1]['close'])
            avg_r = avg_range.iloc[-i]
            
            if pd.notna(avg_r) and avg_r > 0 and gap > avg_r * threshold:
                gap_start = df.iloc[-i-1]['close']
                gap_end = df.iloc[-i]['open']
                
                voids.append({
                    'date': str(df.index[-i].date()) if hasattr(df.index[-i], 'date') else str(df.index[-i]),
                    'gap_start': round(gap_start, 2),
                    'gap_end': round(gap_end, 2),
                    'gap_size': round(gap, 2),
                    'gap_pct': round((gap / gap_start) * 100, 2),
                    'direction': 'up' if gap_end > gap_start else 'down',
                    'bars_ago': i
                })
        
        # Return only most recent 5 significant voids
        return sorted(voids, key=lambda x: x['gap_size'], reverse=True)[:5]
        
    except Exception as e:
        logger.error(f"Liquidity void detection error: {e}")
        return []


def calculate_support_resistance_zones(df: pd.DataFrame, lookback: int = 60) -> Dict[str, Any]:
    """
    Calculates dynamic support and resistance zones using:
    - Swing highs/lows
    - Volume Profile POC/VAH/VAL
    - Bollinger Bands
    - Psychological levels
    """
    try:
        if df.empty or len(df) < lookback:
            return {"error": "Insufficient data"}
        
        recent_df = df.tail(lookback)
        current_price = df.iloc[-1]['close']
        
        # 1. Swing levels
        swing_high = recent_df['high'].max()
        swing_low = recent_df['low'].min()
        
        # 2. Volume Profile levels
        vp = calculate_volume_profile(recent_df, num_bins=40)
        
        # 3. Bollinger Bands
        bb_upper = df.iloc[-1].get('BBU_20_2.0', swing_high)
        bb_lower = df.iloc[-1].get('BBL_20_2.0', swing_low)
        
        # 4. Psychological levels (round numbers)
        price_magnitude = 10 ** (len(str(int(current_price))) - 1)
        psych_above = np.ceil(current_price / price_magnitude) * price_magnitude
        psych_below = np.floor(current_price / price_magnitude) * price_magnitude
        
        # Combine and prioritize resistance levels
        resistance_levels = [
            {"price": swing_high, "type": "Swing High", "strength": 85},
            {"price": bb_upper, "type": "Bollinger Upper", "strength": 70},
            {"price": psych_above, "type": "Psychological", "strength": 60},
        ]
        
        if "error" not in vp:
            resistance_levels.append({
                "price": vp['value_area_high'], 
                "type": "Volume VAH", 
                "strength": 90
            })
        
        # Filter only levels above current price
        resistance_levels = [r for r in resistance_levels if r['price'] > current_price]
        resistance_levels = sorted(resistance_levels, key=lambda x: x['price'])[:3]
        
        # Combine and prioritize support levels
        support_levels = [
            {"price": swing_low, "type": "Swing Low", "strength": 85},
            {"price": bb_lower, "type": "Bollinger Lower", "strength": 70},
            {"price": psych_below, "type": "Psychological", "strength": 60},
        ]
        
        if "error" not in vp:
            support_levels.append({
                "price": vp['value_area_low'], 
                "type": "Volume VAL", 
                "strength": 90
            })
            support_levels.append({
                "price": vp['poc'], 
                "type": "Volume POC", 
                "strength": 95
            })
        
        # Filter only levels below current price
        support_levels = [s for s in support_levels if s['price'] < current_price]
        support_levels = sorted(support_levels, key=lambda x: x['price'], reverse=True)[:3]
        
        # Round prices
        for r in resistance_levels:
            r['price'] = round(r['price'], 2)
        for s in support_levels:
            s['price'] = round(s['price'], 2)
        
        return {
            "current_price": round(current_price, 2),
            "resistance_zones": resistance_levels,
            "support_zones": support_levels,
            "nearest_resistance": resistance_levels[0] if resistance_levels else None,
            "nearest_support": support_levels[0] if support_levels else None,
        }
        
    except Exception as e:
        logger.error(f"Support/Resistance calculation error: {e}")
        return {"error": str(e)}


def enhanced_technical_score(df: pd.DataFrame, regime: Dict[str, Any]) -> Dict[str, Any]:
    import pandas as pd
    """
    Enhanced scoring system with regime-awareness
    Adjusts weights based on market regime for better accuracy
    """
    try:
        if df.empty or len(df) < 50:
            return {"score": 50, "signals": ["Insufficient data"], "confidence": "Low"}
        
        last_row = df.iloc[-1].to_dict()
        prev_row = df.iloc[-2].to_dict()
        close = last_row.get('close', 0)
        
        score = 50  # Neutral starting point
        signals = []
        weight_adjustments = {"trend": 1.0, "momentum": 1.0, "volume": 1.0}
        
        # Adjust weights based on regime
        regime_type = regime.get('regime', 'Unknown')
        
        if regime_type == "Strong Trend":
            weight_adjustments["trend"] = 1.5
            weight_adjustments["momentum"] = 1.2
            weight_adjustments["volume"] = 0.8
        elif regime_type == "Range Bound":
            weight_adjustments["trend"] = 0.6
            weight_adjustments["momentum"] = 1.4
            weight_adjustments["volume"] = 1.0
        
        # === TREND INDICATORS (Base: 40 points) ===
        trend_score = 0
        
        # Moving Averages
        sma_20 = last_row.get('SMA_20', 0)
        sma_50 = last_row.get('SMA_50', 0)
        sma_200 = last_row.get('SMA_200', 0)
        
        if sma_200 > 0:
            if close > sma_200:
                trend_score += 10
                signals.append("✓ Above SMA 200 (Long-term Bullish)")
            else:
                trend_score -= 10
                signals.append("✗ Below SMA 200 (Long-term Bearish)")
        
        if sma_20 > 0 and sma_50 > 0:
            if sma_20 > sma_50:
                trend_score += 8
                signals.append("✓ Golden Cross alignment (SMA 20 > SMA 50)")
            else:
                trend_score -= 8
                signals.append("✗ Death Cross alignment (SMA 20 < SMA 50)")
        
        # Supertrend
        st_cols = [c for c in last_row.keys() if 'SUPERT_' in c]
        if st_cols:
            supertrend = last_row[st_cols[0]]
            if not pd.isna(supertrend) and close > supertrend:
                trend_score += 12
                signals.append("✓ Supertrend Bullish")
            elif not pd.isna(supertrend):
                trend_score -= 12
                signals.append("✗ Supertrend Bearish")
        
        # Ichimoku Cloud
        lead_a = last_row.get('ISA_9', 0)
        lead_b = last_row.get('ISB_26', 0)
        
        if lead_a > 0 and lead_b > 0:
            cloud_top = max(lead_a, lead_b)
            cloud_bottom = min(lead_a, lead_b)
            
            if close > cloud_top:
                trend_score += 10
                signals.append("✓ Above Ichimoku Cloud (Strong Bullish)")
            elif close < cloud_bottom:
                trend_score -= 10
                signals.append("✗ Below Ichimoku Cloud (Strong Bearish)")
        
        # Apply weight
        score += trend_score * weight_adjustments["trend"]
        
        # === MOMENTUM INDICATORS (Base: 30 points) ===
        momentum_score = 0
        
        # RSI
        rsi_cols = [c for c in last_row.keys() if 'RSI' in c]
        rsi = last_row[rsi_cols[0]] if rsi_cols else 50
        
        if rsi < 30:
            momentum_score += 8
            signals.append("✓ RSI Oversold (Potential Rebound)")
        elif rsi > 70:
            momentum_score -= 8
            signals.append("✗ RSI Overbought (Potential Correction)")
        elif 40 <= rsi <= 60:
            signals.append("⊙ RSI Neutral")
        
        # MACD
        macd_cols = [c for c in last_row.keys() if 'MACD_' in c and 's' not in c and 'h' not in c]
        macds_cols = [c for c in last_row.keys() if 'MACDs_' in c]
        
        if macd_cols and macds_cols:
            macd = last_row[macd_cols[0]]
            signal_line = last_row[macds_cols[0]]
            prev_macd = prev_row.get(macd_cols[0], 0)
            prev_signal = prev_row.get(macds_cols[0], 0)
            
            if macd > signal_line:
                momentum_score += 6
                if prev_macd <= prev_signal:
                    momentum_score += 6
                    signals.append("✓✓ MACD Bullish Crossover (Fresh Signal)")
                else:
                    signals.append("✓ MACD Bullish")
            else:
                momentum_score -= 6
                if prev_macd >= prev_signal:
                    momentum_score -= 6
                    signals.append("✗✗ MACD Bearish Crossover (Fresh Signal)")
                else:
                    signals.append("✗ MACD Bearish")
        
        # Stochastic
        stoch_k_cols = [c for c in last_row.keys() if 'STOCHk_' in c]
        stoch_d_cols = [c for c in last_row.keys() if 'STOCHd_' in c]
        
        if stoch_k_cols and stoch_d_cols:
            k = last_row[stoch_k_cols[0]]
            d = last_row[stoch_d_cols[0]]
            
            if k < 20 and d < 20:
                momentum_score += 5
                signals.append("✓ Stochastic Oversold")
            elif k > 80 and d > 80:
                momentum_score -= 5
                signals.append("✗ Stochastic Overbought")
        
        # Apply weight
        score += momentum_score * weight_adjustments["momentum"]
        
        # === VOLUME & MONEY FLOW (Base: 20 points) ===
        volume_score = 0
        
        # MFI
        mfi_cols = [c for c in last_row.keys() if 'MFI' in c]
        mfi = last_row[mfi_cols[0]] if mfi_cols else 50
        
        if mfi < 20:
            volume_score += 5
            signals.append("✓ MFI Oversold (Strong Buying)")
        elif mfi > 80:
            volume_score -= 5
            signals.append("✗ MFI Overbought (Weak Buying)")
        
        # OBV Trend
        if 'OBV' in df.columns and len(df) >= 20:
            obv_sma = df['OBV'].rolling(20).mean()
            if df['OBV'].iloc[-1] > obv_sma.iloc[-1]:
                volume_score += 5
                signals.append("✓ OBV Rising (Accumulation)")
            else:
                volume_score -= 5
                signals.append("✗ OBV Falling (Distribution)")
        
        # Apply weight
        score += volume_score * weight_adjustments["volume"]
        
        # === REGIME ADJUSTMENT ===
        if regime_type == "Strong Trend":
            if regime.get('trend_direction') == "Bullish" and score > 50:
                score += 5
                signals.append("⬆ Strong Bullish Trend Confirmation")
            elif regime.get('trend_direction') == "Bearish" and score < 50:
                score -= 5
                signals.append("⬇ Strong Bearish Trend Confirmation")
        
        # Cap score
        score = max(0, min(100, int(score)))
        
        # Confidence level
        adx = regime.get('adx', 0)
        if adx > 25 and abs(score - 50) > 20:
            confidence = "High"
        elif adx > 20 and abs(score - 50) > 10:
            confidence = "Medium"
        else:
            confidence = "Low"
        
        return {
            "score": score,
            "signals": signals[:10],  # Top 10 most important
            "confidence": confidence,
            "trend_component": int(trend_score * weight_adjustments["trend"]),
            "momentum_component": int(momentum_score * weight_adjustments["momentum"]),
            "volume_component": int(volume_score * weight_adjustments["volume"])
        }
        
    except Exception as e:
        logger.error(f"Enhanced scoring error: {e}")
        return {"score": 50, "signals": [f"Error: {str(e)}"], "confidence": "Low"}
