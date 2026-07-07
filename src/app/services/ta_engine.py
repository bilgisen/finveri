from __future__ import annotations
import logging
from typing import Dict, Any

try:
    import pandas_ta as ta
    _HAS_PANDAS_TA = True
except ImportError:
    _HAS_PANDAS_TA = False

try:
    from sqlalchemy import select
    from app.core.db import AsyncSessionLocal
    from app.models.history import DailyPrice
    _HAS_DB = True
except ImportError:
    _HAS_DB = False

try:
    from app.services.advanced_ta import (
        calculate_volume_profile,
        detect_market_regime,
        detect_liquidity_voids,
        calculate_support_resistance_zones,
        enhanced_technical_score
    )
    _HAS_ADV_TA = True
except ImportError:
    _HAS_ADV_TA = False

logger = logging.getLogger(__name__)

async def get_historical_dataframe(ticker: str, limit: int = 500, interval: str = "1d") -> pd.DataFrame:
    import pandas as pd
    """
    Fetches price history from D1. If interval is 1d, applies real-time overlay.
    """
    from app.core.d1 import get_db, D1Repository

    db = get_db()
    if db is None:
        return pd.DataFrame()

    repo = D1Repository(db)

    rows = await repo.get_prices(ticker, limit)

    if not rows:
        return pd.DataFrame()

    rows.reverse()

    df = pd.DataFrame([{
        "date": r["date"],
        "open": r["open"],
        "high": r["high"],
        "low": r["low"],
        "close": r["close"],
        "volume": r["volume"]
    } for r in rows])

    df.set_index("date", inplace=True)
    df.index = pd.to_datetime(df.index)

    # Resample for weekly if requested
    if interval == "1w":
        df = df.resample('W-FRI').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        return df.tail(limit)

    # --- REAL-TIME INDICATOR OVERLAY LAYER (1D only) ---
    if interval == "1d" and _HAS_REDIS:
        try:
            import json
            from datetime import datetime
            from app.core.redis_client import get_redis

            r_client = get_redis()
            live_data = None
            is_stock = True

            stocks_raw = r_client.get("pool:bist_stocks:data")
            if stocks_raw:
                stocks = json.loads(stocks_raw)
                live_data = next((item for item in stocks if item.get("code", "").upper() == ticker), None)

            if not live_data:
                summary_raw = r_client.get("pool:market_summary:data")
                if summary_raw:
                    summary = json.loads(summary_raw)
                    live_data = next((item for item in summary if item.get("code", "").upper() == ticker), None)
                    is_stock = False

            if live_data:
                live_close = live_data.get("last_price")
                if live_close is not None and live_close > 0:
                    if is_stock:
                        live_open = live_data.get("first_price") or df.iloc[-1]["close"] if not df.empty else live_close
                        live_high = live_data.get("high_price") or live_close
                        live_low = live_data.get("low_price") or live_close
                        live_vol = float(live_data.get("volume") or 0.0)
                    else:
                        live_open = live_close
                        live_high = live_close
                        live_low = live_close
                        live_vol = 0.0

                    today_date = pd.Timestamp(datetime.now().date())
                    df.loc[today_date] = [live_open, live_high, live_low, live_close, live_vol]

        except Exception as overlay_err:
            logger.warning(f"Failed to apply Real-time Indicator Overlay for {ticker}: {overlay_err}")

    return df

async def get_mtf_analysis(ticker: str) -> Dict[str, str]:
    """
    Performs Weekly trend analysis to provide context for daily signals.
    """
    df_w = await get_historical_dataframe(ticker, limit=100, interval="1w")
    if df_w.empty or len(df_w) < 20:
        return {"weekly_trend": "Unknown"}
        
    df_w.ta.sma(length=20, append=True)
    last_w = df_w.iloc[-1].to_dict()
    close_w = last_w.get("close", 0)
    sma_20_w = last_w.get("SMA_20", 0)
    
    trend = "Bullish" if close_w > sma_20_w else "Bearish"
    return {"weekly_trend": trend}

async def calculate_indicators(ticker: str, indicators: list[str]) -> Dict[str, Any]:
    """Calculates requested basic indicators for a given ticker."""
    df = await get_historical_dataframe(ticker, limit=500)
    
    if df.empty:
        return {"error": "No historical data found"}

    result = {}
    try:
        for ind in indicators:
            ind = ind.lower()
            if ind == "rsi":
                df.ta.rsi(length=14, append=True)
            elif ind == "macd":
                df.ta.macd(fast=12, slow=26, signal=9, append=True)
            elif ind == "stoch":
                df.ta.stoch(k=14, d=3, smooth_k=3, append=True)
            elif ind == "bbands":
                df.ta.bbands(length=20, std=2, append=True)
            elif ind == "supertrend":
                df.ta.supertrend(period=7, multiplier=3, append=True)
            elif ind == "obv":
                df.ta.obv(append=True)
            elif ind == "mfi":
                df.ta.mfi(length=14, append=True)
            elif ind == "ichimoku":
                df.ta.ichimoku(append=True)
            elif ind == "psar":
                df.ta.psar(append=True)
            elif ind == "vwap":
                df.ta.vwap(append=True)
            elif ind.startswith("sma_"):
                period = int(ind.split("_")[1])
                df.ta.sma(length=period, append=True)
            elif ind.startswith("ema_"):
                period = int(ind.split("_")[1])
                df.ta.ema(length=period, append=True)
            
        last_row = df.iloc[-1].to_dict()
        
        for ind in indicators:
            ind = ind.lower()
            if ind == "rsi":
                rsi_col = [c for c in last_row.keys() if "RSI" in c]
                if rsi_col: result["rsi"] = last_row[rsi_col[0]]
            elif ind == "macd":
                macd_col = [c for c in last_row.keys() if "MACD_" in c]
                macds_col = [c for c in last_row.keys() if "MACDs_" in c]
                macdh_col = [c for c in last_row.keys() if "MACDh_" in c]
                if macd_col:
                    result["macd"] = {
                        "value": last_row[macd_col[0]],
                        "signal": last_row[macds_col[0]],
                        "histogram": last_row[macdh_col[0]]
                    }
            elif ind == "stoch":
                k_col = [c for c in last_row.keys() if "STOCHk_" in c]
                d_col = [c for c in last_row.keys() if "STOCHd_" in c]
                if k_col and d_col:
                    result["stoch"] = {"k": last_row[k_col[0]], "d": last_row[d_col[0]]}
            elif ind == "bbands":
                bbl_col = [c for c in last_row.keys() if "BBL_" in c]
                bbu_col = [c for c in last_row.keys() if "BBU_" in c]
                if bbl_col and bbu_col:
                    result["bbands"] = {"lower": last_row[bbl_col[0]], "upper": last_row[bbu_col[0]]}
            elif ind == "supertrend":
                st_col = [c for c in last_row.keys() if "SUPERT_" in c]
                if st_col:
                    result["supertrend"] = last_row[st_col[0]]
            elif ind == "obv":
                obv_col = [c for c in last_row.keys() if "OBV" in c]
                if obv_col: result["obv"] = last_row[obv_col[0]]
            elif ind == "mfi":
                mfi_col = [c for c in last_row.keys() if "MFI" in c]
                if mfi_col: result["mfi"] = last_row[mfi_col[0]]
            elif ind.startswith("sma_"):
                sma_col = [c for c in last_row.keys() if "SMA" in c]
                if sma_col:
                    period = int(ind.split("_")[1])
                    specific_col = [c for c in sma_col if f"_{period}" in c]
                    if specific_col: result[ind] = last_row[specific_col[0]]
            elif ind.startswith("ema_"):
                ema_col = [c for c in last_row.keys() if "EMA" in c]
                if ema_col:
                    period = int(ind.split("_")[1])
                    specific_col = [c for c in ema_col if f"_{period}" in c]
                    if specific_col: result[ind] = last_row[specific_col[0]]

        result["close"] = last_row.get("close")
        result["date"] = df.index[-1].isoformat() if hasattr(df.index[-1], 'isoformat') else str(df.index[-1])

    except Exception as e:
        logger.error(f"TA calculation error for {ticker}: {e}")
        return {"error": str(e)}

    return result



def detect_divergences(df, column: str, window: int = 5) -> Dict[str, bool]:
    """
    Detects simple regular bullish and bearish divergences between price and an indicator.
    """
    if len(df) < window * 4:
        return {"bullish": False, "bearish": False}

    # Simplified divergence detection logic
    # Find local peaks/troughs
    df = df.copy()
    df['price_high'] = df['high'].rolling(window=window, center=True).max()
    df['price_low'] = df['low'].rolling(window=window, center=True).min()
    df['ind_high'] = df[column].rolling(window=window, center=True).max()
    df['ind_low'] = df[column].rolling(window=window, center=True).min()

    # Get the last two significant peaks/troughs
    # For a real implementation, we'd look for points where high == price_high
    # But for a summary, we can look at the relative changes over the last N bars
    
    n_recent = 30
    recent_df = df.tail(n_recent)
    
    # Bearish Divergence: Higher High in Price, Lower High in Indicator
    price_peaks = recent_df[recent_df['high'] == recent_df['price_high']]
    ind_peaks = recent_df[recent_df[column] == recent_df['ind_high']]
    
    bearish = False
    if len(price_peaks) >= 2 and len(ind_peaks) >= 2:
        p1, p2 = price_peaks.iloc[-2]['high'], price_peaks.iloc[-1]['high']
        i1, i2 = ind_peaks.iloc[-2][column], ind_peaks.iloc[-1][column]
        if p2 > p1 and i2 < i1:
            bearish = True

    # Bullish Divergence: Lower Low in Price, Higher Low in Indicator
    price_troughs = recent_df[recent_df['low'] == recent_df['price_low']]
    ind_troughs = recent_df[recent_df[column] == recent_df['ind_low']]
    
    bullish = False
    if len(price_troughs) >= 2 and len(ind_troughs) >= 2:
        t1, t2 = price_troughs.iloc[-2]['low'], price_troughs.iloc[-1]['low']
        j1, j2 = ind_troughs.iloc[-2][column], ind_troughs.iloc[-1][column]
        if t2 < t1 and j2 > j1:
            bullish = True

    return {"bullish": bullish, "bearish": bearish}

async def get_market_breadth() -> Dict[str, Any]:
    """Calculates what % of BIST100 stocks are above their SMA 50."""
    from app.core.ticker_store import get_all_tickers
    from app.core.redis_client import get_redis
    import json
    
    # In a real scenario, we'd check cached TA data. 
    # For now, let's look at the ta_data:* keys in Redis.
    r = get_redis()
    keys = r.keys("ta_data:*")
    if not keys:
        return {"breadth": 50, "status": "Neutral"}
        
    above_sma50 = 0
    total = 0
    for key in keys:
        try:
            data = json.loads(r.get(key))
            if data.get("close", 0) > data.get("sma", {}).get("sma_50", 0):
                above_sma50 += 1
            total += 1
        except: continue
        
    if total == 0: return {"breadth": 50, "status": "Neutral"}
    percentage = (above_sma50 / total) * 100
    status = "Strong" if percentage > 70 else "Weak" if percentage < 30 else "Neutral"
    return {"breadth": percentage, "status": status}

async def calculate_beta(ticker: str) -> float:
    """Calculates 1-year Beta relative to XU100."""
    df_stock = await get_historical_dataframe(ticker, limit=252)
    df_market = await get_historical_dataframe("XU100", limit=252)
    
    if df_stock.empty or df_market.empty or len(df_stock) < 100:
        return 1.0
        
    returns_stock = df_stock['close'].pct_change().dropna()
    returns_market = df_market['close'].pct_change().dropna()
    
    # Align indices
    common_idx = returns_stock.index.intersection(returns_market.index)
    if len(common_idx) < 100: return 1.0
    
    s = returns_stock.loc[common_idx]
    m = returns_market.loc[common_idx]
    
    covariance = s.cov(m)
    variance = m.var()
    
    return round(covariance / variance, 2) if variance > 0 else 1.0

async def generate_llm_summary(ticker: str) -> Dict[str, Any]:
    """Generates a Pro-Level Institutional-Grade TA summary with multi-layered context."""
    df = await get_historical_dataframe(ticker, limit=500)
    if df.empty:
        return {"error": "No historical data found"}
        
    try:
        # 1. Calculate ALL Indicators
        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.sma(length=20, append=True); df.ta.sma(length=50, append=True); df.ta.sma(length=200, append=True)
        df.ta.ema(length=9, append=True); df.ta.ema(length=21, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.adx(length=14, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.supertrend(period=7, multiplier=3, append=True)
        df.ta.stoch(k=14, d=3, smooth_k=3, append=True)
        df.ta.mfi(length=14, append=True)
        df.ta.ichimoku(append=True)
        df.ta.psar(append=True)
        df.ta.vwap(append=True)
        df.ta.obv(append=True)
        
        # 2. ADVANCED ANALYSIS LAYER
        # Market Regime Detection (CRITICAL for chatbot context)
        regime = detect_market_regime(df)
        
        # Volume Profile Analysis (Institutional support/resistance)
        volume_profile = calculate_volume_profile(df.tail(100))
        
        # Liquidity Voids (Fair Value Gaps)
        liquidity_voids = detect_liquidity_voids(df)
        
        # Enhanced Support/Resistance Zones
        sr_zones = calculate_support_resistance_zones(df)
        
        # Enhanced Technical Score (regime-aware)
        score_data = enhanced_technical_score(df, regime)
        
        # Multi-Timeframe Context
        mtf = await get_mtf_analysis(ticker)
        
        # Market Breadth & Beta
        breadth = await get_market_breadth()
        beta = await calculate_beta(ticker)
        
        last_row = df.iloc[-1].to_dict()
        close = last_row.get('close', 0)
        
        # Divergences
        rsi_col = [c for c in last_row.keys() if 'RSI' in c]
        rsi_div = detect_divergences(df, rsi_col[0]) if rsi_col else {"bullish": False, "bearish": False}
        macd_val_col = [c for c in last_row.keys() if 'MACD_' in c and 's' not in c and 'h' not in c]
        macd_div = detect_divergences(df, macd_val_col[0]) if macd_val_col[0] else {"bullish": False, "bearish": False}
        
        # 3. Risk/Reward Calculation with Enhanced SR Zones
        atr_val = last_row.get('ATRr_14', 0)
        
        # Use enhanced support/resistance zones
        nearest_support = sr_zones.get('nearest_support', {}).get('price', close * 0.95) if 'error' not in sr_zones else close * 0.95
        nearest_resistance = sr_zones.get('nearest_resistance', {}).get('price', close * 1.05) if 'error' not in sr_zones else close * 1.05
        
        trend = "Bullish" if score_data["score"] > 55 else "Bearish" if score_data["score"] < 45 else "Neutral"
        
        if trend == "Bullish":
            stop_loss = max(close - (1.5 * atr_val), nearest_support)
            take_profit = nearest_resistance
        else:
            stop_loss = min(close + (1.5 * atr_val), nearest_resistance)
            take_profit = nearest_support
            
        rr_ratio = abs(take_profit - close) / abs(close - stop_loss) if abs(close - stop_loss) > 0 else 0

        # 4. CHATBOT CONTEXT CONSTRUCTION
        # Build rich, multi-layered context for chatbot
        
        # Determine unit based on ticker type (Index starts with 'X')
        unit = "puan" if ticker.upper().startswith("X") else "TL"

        # Key indicators summary
        rsi_val = last_row.get([c for c in last_row.keys() if 'RSI' in c][0], 50) if [c for c in last_row.keys() if 'RSI' in c] else 50
        macd_val = last_row.get([c for c in last_row.keys() if 'MACD_' in c and 's' not in c and 'h' not in c][0], 0) if [c for c in last_row.keys() if 'MACD_' in c and 's' not in c and 'h' not in c] else 0
        
        # Volume Profile context
        vp_context = ""
        if "error" not in volume_profile:
            vp_context = (f"Volume POC (en yüksek hacim): {volume_profile['poc']:.2f} {unit}. "
                         f"Value Area: {volume_profile['value_area_low']:.2f} - {volume_profile['value_area_high']:.2f} {unit}. ")
        
        # Liquidity voids context
        lv_context = ""
        if liquidity_voids:
            recent_void = liquidity_voids[0]
            lv_context = f"Yakın likidite boşluğu: {recent_void['gap_start']:.2f} - {recent_void['gap_end']:.2f} {unit} ({recent_void['direction']} yönlü). "
        
        # Enhanced LLM Prompt
        llm_text = (
            f"=== {ticker} TEKNİK ANALİZ RAPORU ===\n\n"
            f"📊 GENEL GÖRÜNÜM:\n"
            f"Fiyat: {close:.2f} {unit} | Teknik Skor: {score_data['score']}/100 ({score_data['confidence']} güven)\n"
            f"Trend: {trend} (Günlük), {mtf['weekly_trend']} (Haftalık)\n"
            f"Piyasa Rejimi: {regime.get('regime', 'Unknown')} - {regime.get('trend_direction', 'Neutral')}\n"
            f"Strateji Önerisi: {regime.get('recommended_strategy', 'N/A')}\n\n"
            
            f"📈 TEKNİK GÖSTERGELER:\n"
            f"RSI(14): {rsi_val:.1f} | MACD: {macd_val:.2f}\n"
            f"ADX: {regime.get('adx', 0):.1f} (Trend Gücü) | Volatilite: {regime.get('volatility_pct', 0):.2f}%\n"
            f"VWAP: {'Fiyat üstünde' if close > last_row.get('VWAP_D', 0) else 'Fiyat altında'}\n\n"
            
            f"🎯 DESTEK VE DİRENÇ:\n"
            f"Yakın Destek: {nearest_support:.2f} {unit} ({sr_zones.get('nearest_support', {}).get('type', 'N/A')})\n"
            f"Yakın Direnç: {nearest_resistance:.2f} {unit} ({sr_zones.get('nearest_resistance', {}).get('type', 'N/A')})\n"
            f"{vp_context}"
            f"{lv_context}\n"
            
            f"💰 RİSK YÖNETİMİ:\n"
            f"Stop-Loss: {stop_loss:.2f} {unit} | Hedef: {take_profit:.2f} {unit}\n"
            f"Risk/Ödül Oranı: {rr_ratio:.2f}\n"
            f"Beta (XU100): {beta} | Piyasa Genişliği: {breadth['breadth']:.1f}% ({breadth['status']})\n\n"
            
            f"⚡ AKTİF SİNYALLER:\n"
            + "\n".join([f"• {sig}" for sig in score_data['signals'][:8]]) + "\n\n"
            
            f"🔍 SAPMA ANALİZİ:\n"
            f"RSI: {'Bullish Divergence ✓' if rsi_div['bullish'] else 'Bearish Divergence ✗' if rsi_div['bearish'] else 'Yok'}\n"
            f"MACD: {'Bullish Divergence ✓' if macd_div['bullish'] else 'Bearish Divergence ✗' if macd_div['bearish'] else 'Yok'}"
        )

        macd_hist_cols = [c for c in last_row.keys() if 'MACDh_' in c]
        macd_status = "Boğa (Al)" if macd_hist_cols and last_row.get(macd_hist_cols[0], 0) > 0 else "Ayı (Sat)" if macd_hist_cols else "Nötr"

        return {
            "ticker": ticker,
            "close": round(close, 2),
            "date": df.index[-1].isoformat() if hasattr(df.index[-1], 'isoformat') else str(df.index[-1]),
            
            # Core metrics
            "score": score_data["score"],
            "confidence": score_data["confidence"],
            "trend": trend,
            "weekly_trend": mtf["weekly_trend"],
            
            # Legacy and backward-compatibility fields for summary-card and template
            "rsi": {
                "value": round(rsi_val, 2),
                "status": "Aşırı Alım" if rsi_val > 70 else "Aşırı Satım" if rsi_val < 30 else "Nötr"
            },
            "support_resistance": {
                "support": round(nearest_support, 2),
                "resistance": round(nearest_resistance, 2)
            },
            "atr_stop_loss": round(stop_loss, 2),
            "macd_status": macd_status,
            "sma": {
                "sma_20": round(last_row.get('SMA_20', 0), 2) if last_row.get('SMA_20') else None,
                "sma_50": round(last_row.get('SMA_50', 0), 2) if last_row.get('SMA_50') else None,
                "sma_200": round(last_row.get('SMA_200', 0), 2) if last_row.get('SMA_200') else None
            },
            
            # NEW: Market Regime
            "market_regime": regime,
            
            # NEW: Volume Profile
            "volume_profile": volume_profile,
            
            # NEW: Liquidity Voids
            "liquidity_voids": liquidity_voids,
            
            # Enhanced Support/Resistance
            "support_resistance_zones": sr_zones,
            
            # Risk metrics
            "beta": beta,
            "market_breadth": breadth,
            "rr_ratio": round(rr_ratio, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            
            # Signals & Divergences
            "signals": score_data["signals"],
            "divergences": {"rsi": rsi_div, "macd": macd_div},
            
            # Score components (for debugging)
            "score_components": {
                "trend": score_data.get("trend_component", 0),
                "momentum": score_data.get("momentum_component", 0),
                "volume": score_data.get("volume_component", 0)
            },
            
            # Chatbot-ready summary
            "llm_summary_prompt": llm_text
        }

    except Exception as e:
        logger.error(f"Ultimate TA error for {ticker}: {e}", exc_info=True)
        return {"error": str(e)}
