import pandas as pd
import pandas_ta as ta
import logging
from sqlalchemy import select
from typing import Dict, Any

from app.core.db import AsyncSessionLocal
from app.models.history import DailyPrice

logger = logging.getLogger(__name__)

async def get_historical_dataframe(ticker: str, limit: int = 500) -> pd.DataFrame:
    """
    Fetches daily price history from DB and overlays the latest real-time quote
    from Redis cache (bist_stocks or market_summary) as a temporary final bar
    to support "Real-time Indicator Overlay".
    """
    import json
    from datetime import datetime
    from app.core.redis_client import get_redis

    async with AsyncSessionLocal() as session:
        # Get latest records for ticker from PostgreSQL
        stmt = select(DailyPrice).where(DailyPrice.ticker == ticker).order_by(DailyPrice.date.desc()).limit(limit)
        result = await session.execute(stmt)
        records = result.scalars().all()

        if not records:
            return pd.DataFrame()

        records.reverse()

        df = pd.DataFrame([{
            "date": r.date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume
        } for r in records])

        df.set_index("date", inplace=True)

        # --- REAL-TIME INDICATOR OVERLAY LAYER ---
        try:
            r_client = get_redis()
            live_data = None
            is_stock = True

            # 1. Try to find the ticker in BIST Stocks (AA source)
            stocks_raw = r_client.get("pool:bist_stocks:data")
            if stocks_raw:
                stocks = json.loads(stocks_raw)
                live_data = next((item for item in stocks if item.get("code", "").upper() == ticker), None)

            # 2. Try to find the ticker in Market Summary (Forex, Endeks, Commodity vb.)
            if not live_data:
                summary_raw = r_client.get("pool:market_summary:data")
                if summary_raw:
                    summary = json.loads(summary_raw)
                    live_data = next((item for item in summary if item.get("code", "").upper() == ticker), None)
                    is_stock = False

            if live_data:
                # Extract pricing from the live cached item
                live_close = live_data.get("last_price")
                
                if live_close is not None and live_close > 0:
                    if is_stock:
                        live_open = live_data.get("first_price") or df.iloc[-1]["close"] if not df.empty else live_close
                        live_high = live_data.get("high_price") or live_close
                        live_low = live_data.get("low_price") or live_close
                        live_vol = float(live_data.get("volume") or 0.0)
                    else:
                        # For indices/commodities where high/low/open might not be in summary
                        live_open = live_close
                        live_high = live_close
                        live_low = live_close
                        live_vol = 0.0

                    today_date = datetime.now().date()
                    
                    # If the last row in DB is already for today, overwrite it with latest live data
                    if not df.empty and df.index[-1] == today_date:
                        df.loc[today_date] = [live_open, live_high, live_low, live_close, live_vol]
                    else:
                        # Otherwise append today as a new temporary 501st row
                        df.loc[today_date] = [live_open, live_high, live_low, live_close, live_vol]

        except Exception as overlay_err:
            logger.warning(f"Failed to apply Real-time Indicator Overlay for {ticker}: {overlay_err}")

        return df

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

async def generate_llm_summary(ticker: str) -> Dict[str, Any]:
    """Generates an Ultimate-Level LLM-friendly summary of the current TA status."""
    df = await get_historical_dataframe(ticker, limit=500)
    if df.empty:
        return {"error": "No historical data found"}
        
    try:
        # 1. Base Indicators
        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        
        # 2. Advanced Indicators (ADX & ATR)
        df.ta.adx(length=14, append=True)
        df.ta.atr(length=14, append=True)
        
        # 3. Candlestick Patterns (Custom Pandas Logic to avoid TA-Lib dependency)
        df['body'] = df['close'] - df['open']
        df['prev_body'] = df['body'].shift(1)
        df['prev_close'] = df['close'].shift(1)
        df['prev_open'] = df['open'].shift(1)
        
        # Bullish Engulfing
        df['bullish_engulfing'] = (df['prev_body'] < 0) & (df['body'] > 0) & (df['close'] >= df['prev_open']) & (df['open'] <= df['prev_close'])
        # Bearish Engulfing
        df['bearish_engulfing'] = (df['prev_body'] > 0) & (df['body'] < 0) & (df['close'] <= df['prev_open']) & (df['open'] >= df['prev_close'])
        # Doji (Body is less than 5% of the high-low range)
        df['range'] = df['high'] - df['low']
        df['doji'] = abs(df['body']) <= (df['range'] * 0.05)

        last_row = df.iloc[-1].to_dict()
        prev_row = df.iloc[-2].to_dict() if len(df) > 1 else last_row

        close = last_row.get('close', 0)
        
        # --- TREND ANALYSIS (SMA + ADX) ---
        sma_50 = last_row.get('SMA_50', 0)
        sma_200 = last_row.get('SMA_200', 0)
        adx_keys = [k for k in last_row.keys() if 'ADX_' in k]
        adx_val = last_row[adx_keys[0]] if adx_keys else 0
        
        trend = "Neutral"
        if sma_50 > 0 and sma_200 > 0:
            if close > sma_50 and close > sma_200:
                trend = "Bullish"
            elif close < sma_50 and close < sma_200:
                trend = "Bearish"

        trend_strength = "Weak/Ranging (Prone to fake signals)"
        if adx_val > 25:
            trend_strength = "Strong Trend"
            trend = f"Strong {trend}" # E.g., Strong Bullish

        # --- RSI ---
        rsi_keys = [k for k in last_row.keys() if 'RSI' in k]
        rsi_val = last_row[rsi_keys[0]] if rsi_keys else 50
        rsi_status = "Neutral"
        if rsi_val > 70: rsi_status = "Overbought (Correction Risk)"
        elif rsi_val < 30: rsi_status = "Oversold (Rebound Potential)"

        # --- MACD ---
        macd_keys = [k for k in last_row.keys() if 'MACD_' in k]
        macds_keys = [k for k in last_row.keys() if 'MACDs_' in k]
        macd_val = last_row[macd_keys[0]] if macd_keys else 0
        macds_val = last_row[macds_keys[0]] if macds_keys else 0
        prev_macd = prev_row.get(macd_keys[0], 0) if macd_keys else 0
        prev_macds = prev_row.get(macds_keys[0], 0) if macds_keys else 0
        
        macd_status = "Neutral"
        if macd_val > macds_val and prev_macd <= prev_macds:
            macd_status = "Bullish Crossover (Buy Signal)"
        elif macd_val < macds_val and prev_macd >= prev_macds:
            macd_status = "Bearish Crossover (Sell Signal)"
        elif macd_val > macds_val:
            macd_status = "Bullish Momentum"
        elif macd_val < macds_val:
            macd_status = "Bearish Momentum"

        # --- STOP LOSS (ATR) ---
        atr_keys = [k for k in last_row.keys() if 'ATRr_' in k]
        atr_val = last_row[atr_keys[0]] if atr_keys else 0
        # 1.5x ATR is a standard trailing stop
        suggested_stop_loss = close - (1.5 * atr_val) if trend == "Bullish" or "Bullish" in trend else close + (1.5 * atr_val)

        # --- CANDLESTICK PATTERNS ---
        active_patterns = []
        if last_row.get('bullish_engulfing'): active_patterns.append("Bullish Engulfing")
        if last_row.get('bearish_engulfing'): active_patterns.append("Bearish Engulfing")
        if last_row.get('doji'): active_patterns.append("Doji (Indecision)")
        
        pattern_str = ", ".join(active_patterns) if active_patterns else "No significant patterns detected yesterday."

        # --- SUPPORT/RESISTANCE (BBands) ---
        bbl_keys = [k for k in last_row.keys() if 'BBL_' in k]
        bbu_keys = [k for k in last_row.keys() if 'BBU_' in k]
        support = last_row[bbl_keys[0]] if bbl_keys else 0
        resistance = last_row[bbu_keys[0]] if bbu_keys else 0

        # Construct LLM text
        llm_text = (
            f"Asset {ticker} is currently in a {trend} state. "
            f"Trend strength (ADX) is {adx_val:.1f}, indicating a {trend_strength} market. "
            f"RSI is {rsi_val:.1f} ({rsi_status}), and MACD shows {macd_status}. "
            f"Candlestick Analysis: {pattern_str} "
            f"Volatility (ATR) suggests a scientific stop-loss placement around {suggested_stop_loss:.2f}. "
            f"Immediate support is near {support:.2f} and resistance near {resistance:.2f}."
        )

        return {
            "ticker": ticker,
            "close": round(close, 2),
            "trend": trend,
            "adx_strength": trend_strength,
            "rsi": {"value": round(rsi_val, 2), "status": rsi_status},
            "macd": macd_status,
            "sma": {
                "sma_20": round(last_row.get('SMA_20', 0), 2) if last_row.get('SMA_20') else None,
                "sma_50": round(last_row.get('SMA_50', 0), 2) if last_row.get('SMA_50') else None,
                "sma_200": round(last_row.get('SMA_200', 0), 2) if last_row.get('SMA_200') else None,
            },
            "candlestick_patterns": active_patterns,
            "atr_stop_loss": round(suggested_stop_loss, 2),
            "support_resistance": {
                "support": round(support, 2),
                "resistance": round(resistance, 2)
            },
            "llm_summary_prompt": llm_text
        }

    except Exception as e:
        logger.error(f"LLM summary generation error for {ticker}: {e}")
        return {"error": str(e)}
