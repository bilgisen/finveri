"""
Technical Analysis Engine — Rewritten for Workers (pure Python, no pandas/ta).
Works with List[Dict] from D1, uses indicators.py for calculations.
"""
from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services import indicators
from app.services.indicators import compute_all, compute_selected

try:
    from app.services.advanced_ta import (
        calculate_volume_profile,
        detect_market_regime,
        detect_liquidity_voids,
        calculate_support_resistance_zones,
        enhanced_technical_score,
    )
    _HAS_ADV_TA = True
except ImportError:
    _HAS_ADV_TA = False

logger = logging.getLogger(__name__)


async def get_historical_prices(ticker: str, limit: int = 500) -> List[Dict[str, Any]]:
    """Fetches price history from D1."""
    from app.core.d1 import get_db, D1Repository
    db = get_db()
    if db is None:
        return []
    repo = D1Repository(db)
    rows = await repo.get_prices(ticker, limit)
    rows.reverse()  # oldest first
    return rows


def _overlay_live_data(ticker: str, data: List[Dict]) -> List[Dict]:
    """Overlays today's live price if available from KV cache."""
    try:
        import json
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
                today_str = datetime.now().strftime("%Y-%m-%d")
                if not data or str(data[-1].get("date", "")) != today_str:
                    if is_stock:
                        live_open = live_data.get("first_price") or data[-1]["close"] if data else live_close
                        live_high = live_data.get("high_price") or live_close
                        live_low = live_data.get("low_price") or live_close
                        live_vol = float(live_data.get("volume") or 0.0)
                    else:
                        live_open = live_close
                        live_high = live_close
                        live_low = live_close
                        live_vol = 0.0
                    data.append({
                        "date": today_str,
                        "open": live_open,
                        "high": live_high,
                        "low": live_low,
                        "close": live_close,
                        "volume": live_vol,
                    })
    except Exception as e:
        logger.warning(f"Failed to overlay live data for {ticker}: {e}")
    return data


async def get_mtf_analysis(ticker: str) -> Dict[str, str]:
    """Weekly trend analysis using pure Python."""
    data = await get_historical_prices(ticker, limit=100)
    if len(data) < 20:
        return {"weekly_trend": "Unknown"}
    closes = [float(r["close"]) for r in data]
    sma_20 = indicators.sma(closes, 20)
    last_close = closes[-1]
    last_sma = sma_20[-1]
    trend = "Bullish" if last_sma is not None and last_close > last_sma else "Bearish" if last_sma is not None else "Unknown"
    return {"weekly_trend": trend}


async def calculate_indicators(ticker: str, indicators_list: list[str]) -> Dict[str, Any]:
    """Calculates requested basic indicators for a given ticker."""
    try:
        redis_client = None
        cache_hit = False
        try:
            from app.core.redis_client import get_redis
            import json
            redis_client = get_redis()
            cached = redis_client.get(f"ta_data:{ticker}")
            if cached:
                result = json.loads(cached)
                result["source"] = "cache"
                return result
        except Exception:
            pass

        data = await get_historical_prices(ticker, limit=500)
        if not data:
            return {"error": "No historical data found"}
        data = _overlay_live_data(ticker, data)
        result = compute_selected(data, indicators_list)
        result["source"] = "live"

        # Cache result
        if redis_client:
            try:
                import json
                redis_client.setex(f"ta_data:{ticker}", 300, json.dumps(result))
            except Exception:
                pass

        return result
    except Exception as e:
        logger.error(f"TA calculation error for {ticker}: {e}")
        return {"error": str(e)}


def detect_divergences_from_prices(data: List[Dict], column: str = "rsi", window: int = 5) -> Dict[str, bool]:
    """Detect divergences between price and an indicator column."""
    closes = [float(r.get("close", 0)) for r in data]
    # Indicator would need to be pre-computed; this is a simplified version
    return {"bullish": False, "bearish": False}


async def get_market_breadth() -> Dict[str, Any]:
    """Calculates approximate market breadth from cached TA data."""
    try:
        from app.core.redis_client import get_redis
        import json
        r = get_redis()
        keys_raw = r.keys("ta_data:*")
        if not keys_raw:
            return {"breadth": 50, "status": "Neutral"}
        keys = [keys_raw] if isinstance(keys_raw, str) else keys_raw if isinstance(keys_raw, list) else []
        above = 0
        total = 0
        for key in keys:
            try:
                data = json.loads(r.get(key))
                close_val = data.get("close", 0)
                sma_50 = None
                if "indicators" in data:
                    sma_50 = data["indicators"].get("sma_50")
                elif "sma_50" in data:
                    sma_50 = data.get("sma_50")
                if sma_50 and close_val > sma_50:
                    above += 1
                total += 1
            except Exception:
                continue
        if total == 0:
            return {"breadth": 50, "status": "Neutral"}
        pct = (above / total) * 100
        status = "Strong" if pct > 70 else "Weak" if pct < 30 else "Neutral"
        return {"breadth": pct, "status": status}
    except Exception as e:
        logger.warning(f"Market breadth error: {e}")
        return {"breadth": 50, "status": "Neutral"}


async def calculate_beta(ticker: str) -> float:
    """Simplified beta calculation using pure Python."""
    try:
        stock_data = await get_historical_prices(ticker, limit=252)
        market_data = await get_historical_prices("XU100", limit=252)
        if len(stock_data) < 100 or len(market_data) < 100:
            return 1.0
        stock_returns = []
        market_returns = []
        min_len = min(len(stock_data), len(market_data))
        for i in range(1, min_len):
            s_ret = (stock_data[i]["close"] - stock_data[i - 1]["close"]) / stock_data[i - 1]["close"]
            m_ret = (market_data[i]["close"] - market_data[i - 1]["close"]) / market_data[i - 1]["close"]
            stock_returns.append(s_ret)
            market_returns.append(m_ret)
        if len(stock_returns) < 100:
            return 1.0
        n = len(stock_returns)
        mean_s = sum(stock_returns) / n
        mean_m = sum(market_returns) / n
        cov = sum((s - mean_s) * (m - mean_m) for s, m in zip(stock_returns, market_returns)) / n
        var_m = sum((m - mean_m) ** 2 for m in market_returns) / n
        return round(cov / var_m, 2) if var_m > 0 else 1.0
    except Exception as e:
        logger.warning(f"Beta calculation error: {e}")
        return 1.0


async def generate_llm_summary(ticker: str) -> Dict[str, Any]:
    """Generates a Pro-Level institutional-grade TA summary."""
    try:
        data = await get_historical_prices(ticker, limit=500)
        if not data:
            return {"error": "No historical data found"}
        data = _overlay_live_data(ticker, data)

        # 1. Calculate ALL indicators
        all_indicators = compute_all(data)
        if "error" in all_indicators:
            return all_indicators

        close = all_indicators.get("close", 0)
        unit = "puan" if ticker.upper().startswith("X") else "TL"

        # 2. ADVANCED ANALYSIS
        regime = detect_market_regime(data) if _HAS_ADV_TA else {"regime": "Unknown", "error": "not available"}
        volume_profile = calculate_volume_profile(data, num_bins=50) if _HAS_ADV_TA else {"error": "not available"}
        liquidity_voids = detect_liquidity_voids(data) if _HAS_ADV_TA else []
        sr_zones = calculate_support_resistance_zones(data) if _HAS_ADV_TA else {"error": "not available"}
        score_data = enhanced_technical_score(data, regime) if _HAS_ADV_TA else {"score": 50, "signals": [], "confidence": "Low"}

        mtf = await get_mtf_analysis(ticker)
        breadth = await get_market_breadth()
        beta = await calculate_beta(ticker)

        # 3. Risk/Reward
        atr_val = all_indicators.get("atr", 0) or 0
        nearest_support = 0
        nearest_resistance = 0
        if "error" not in sr_zones:
            nearest_support = sr_zones.get("nearest_support", {}).get("price", close * 0.95)
            nearest_resistance = sr_zones.get("nearest_resistance", {}).get("price", close * 1.05)
        else:
            nearest_support = close * 0.95
            nearest_resistance = close * 1.05

        trend = "Bullish" if score_data.get("score", 50) > 55 else "Bearish" if score_data.get("score", 50) < 45 else "Neutral"
        if trend == "Bullish":
            stop_loss = max(close - (1.5 * atr_val), nearest_support)
            take_profit = nearest_resistance
        else:
            stop_loss = min(close + (1.5 * atr_val), nearest_resistance)
            take_profit = nearest_support
        rr_ratio = abs(take_profit - close) / abs(close - stop_loss) if abs(close - stop_loss) > 0 else 0

        rsi_val = all_indicators.get("rsi", 50) or 50
        macd_val = all_indicators.get("macd", {}).get("value", 0) or 0

        # LLM text
        llm_text = (
            f"=== {ticker} TEKNIK ANALIZ RAPORU ===\n\n"
            f"GENEL GORUNUM:\n"
            f"Fiyat: {close:.2f} {unit} | Teknik Skor: {score_data.get('score', 50)}/100 ({score_data.get('confidence', 'Low')} guven)\n"
            f"Trend: {trend} (Gunluk), {mtf['weekly_trend']} (Haftalik)\n"
            f"Piyasa Rejimi: {regime.get('regime', 'Unknown')} - {regime.get('trend_direction', 'Neutral')}\n"
            f"Strateji Onerisi: {regime.get('recommended_strategy', 'N/A')}\n\n"
            f"TEKNIK GOSTERGELER:\n"
            f"RSI(14): {rsi_val:.1f} | MACD: {macd_val:.2f}\n"
            f"ADX: {regime.get('adx', 0):.1f} (Trend Gucu) | Volatilite: {regime.get('volatility_pct', 0):.2f}%\n\n"
            f"DESTEK VE DIRENC:\n"
            f"Yakin Destek: {nearest_support:.2f} {unit}\n"
            f"Yakin Direnc: {nearest_resistance:.2f} {unit}\n\n"
            f"RISK YONETIMI:\n"
            f"Stop-Loss: {stop_loss:.2f} {unit} | Hedef: {take_profit:.2f} {unit}\n"
            f"Risk/Odul Orani: {rr_ratio:.2f}\n"
            f"Beta (XU100): {beta} | Piyasa Genisligi: {breadth.get('breadth', 50):.1f}% ({breadth.get('status', 'Neutral')})\n\n"
            f"AKTIF SINYALLER:\n"
            + "\n".join([f"* {sig}" for sig in score_data.get('signals', [])[:8]]) + "\n\n"
            f"SAPMA ANALIZI:\n"
            f"RSI: {'Bullish Divergence' if all_indicators.get('divergences', {}).get('rsi', {}).get('bullish') else 'Bearish Divergence' if all_indicators.get('divergences', {}).get('rsi', {}).get('bearish') else 'Yok'}\n"
            f"MACD: {'Bullish Divergence' if all_indicators.get('divergences', {}).get('macd', {}).get('bullish') else 'Bearish Divergence' if all_indicators.get('divergences', {}).get('macd', {}).get('bearish') else 'Yok'}"
        )

        macd_h = all_indicators.get("macd", {}).get("histogram", 0) or 0
        macd_status = "Boga (Al)" if macd_h > 0 else "Ayi (Sat)"

        return {
            "ticker": ticker,
            "close": round(close, 2),
            "date": all_indicators.get("date", ""),
            "score": score_data.get("score", 50),
            "confidence": score_data.get("confidence", "Low"),
            "trend": trend,
            "weekly_trend": mtf["weekly_trend"],
            "rsi": {
                "value": round(rsi_val, 2),
                "status": "Asiri Alim" if rsi_val > 70 else "Asiri Satim" if rsi_val < 30 else "Notr",
            },
            "support_resistance": {
                "support": round(nearest_support, 2),
                "resistance": round(nearest_resistance, 2),
            },
            "atr_stop_loss": round(stop_loss, 2),
            "macd_status": macd_status,
            "sma": {
                "sma_20": round(all_indicators.get("sma_20", 0) or 0, 2),
                "sma_50": round(all_indicators.get("sma_50", 0) or 0, 2),
                "sma_200": round(all_indicators.get("sma_200", 0) or 0, 2),
            },
            "market_regime": regime,
            "volume_profile": volume_profile,
            "liquidity_voids": liquidity_voids,
            "support_resistance_zones": sr_zones,
            "beta": beta,
            "market_breadth": breadth,
            "rr_ratio": round(rr_ratio, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "signals": score_data.get("signals", []),
            "divergences": all_indicators.get("divergences", {}),
            "score_components": {
                "trend": score_data.get("trend_component", 0),
                "momentum": score_data.get("momentum_component", 0),
                "volume": score_data.get("volume_component", 0),
            },
            "llm_summary_prompt": llm_text,
        }
    except Exception as e:
        logger.error(f"Ultimate TA error for {ticker}: {e}", exc_info=True)
        return {"error": str(e)}
