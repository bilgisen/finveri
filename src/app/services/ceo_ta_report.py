"""
CEO / Yonetim Kurulu Seviyesi Teknik Analiz Raporu
Pure Python (no pandas/numpy) — Works in Workers.
"""
from __future__ import annotations
import logging
import math
from typing import Dict, Any, List
from datetime import datetime

from app.services.ta_engine import get_historical_prices, calculate_beta, get_market_breadth, _overlay_live_data
from app.services import indicators
from app.services.advanced_ta import (
    calculate_volume_profile,
    detect_market_regime,
    detect_liquidity_voids,
    calculate_support_resistance_zones,
    enhanced_technical_score,
    calculate_divergence_confidence,
)
from app.services.patterns import (
    detect_candlestick_patterns,
    detect_chart_patterns,
    calculate_pattern_score,
)

logger = logging.getLogger(__name__)


def _fmt_price(val: float, unit: str = "TL") -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "-"
    return f"{val:,.2f} {unit}"


def _trend_interpretation(score: float, close: float, sma_20: float, sma_50: float, sma_200: float) -> Dict[str, str]:
    interp = {}
    interp["short"] = "Kısa vadeli yapı pozitif" if close > sma_20 else "Kısa vadeli yapıda zayıflama"
    interp["medium"] = "Orta vadeli trend yapısı korunuyor" if sma_20 > sma_50 else "Orta vadeli yapıda bozulma"
    interp["long"] = "Uzun vadeli ana trend korunuyor" if close > sma_200 else "Uzun vadeli ana trend zayıflıyor"
    if score > 65:
        interp["character"] = "Yükseliş"
    elif score > 45:
        interp["character"] = "Yatay konsolidasyon"
    elif score > 30:
        interp["character"] = "Düzeltme"
    else:
        interp["character"] = "Trend dönüşümü riski"
    return interp


def _rsi_interpretation(rsi_val: float, prev_rsi: float = None) -> str:
    if rsi_val > 70:
        return "Aşırı alım bölgesinde, kar satışı riski bulunuyor."
    elif rsi_val > 60:
        return "Momentum pozitif ancak aşırı alıma yaklaşılıyor."
    elif rsi_val > 45:
        return "Nötr bölge, belirgin bir momentum yönü yok."
    elif rsi_val > 30:
        return "Momentum zayıflıyor, ancak aşırı satıma yaklaşım tepki potansiyeli oluşturuyor."
    else:
        return "Aşırı satım bölgesinde, kısa vadeli tepki potansiyeli yüksek."


def _macd_interpretation(macd_val: float, signal_val: float, hist_val: float) -> str:
    if hist_val > 0 and macd_val > signal_val:
        return "Pozitif momentum devam ediyor, trend güçlü."
    elif hist_val > 0:
        return "Histogram pozitife döndü, ancak kesişim henüz kesinleşmedi."
    elif hist_val < 0 and macd_val < signal_val:
        return "Negatif momentum devam ediyor, satış baskısı hakim."
    else:
        return "Histogram negatif bölgede, ancak zayıflama sinyalleri var."


def _calculate_confluence_score(close: float, sma_20: float, sma_50: float, sma_200: float,
                                 rsi_val: float, hist_val: float, regime: Dict) -> Dict[str, Any]:
    sma_bullish = 1 if sma_20 > sma_50 > sma_200 else (-1 if sma_20 < sma_50 < sma_200 else 0)
    price_bullish = 1 if close > sma_20 > sma_50 > sma_200 else (-1 if close < sma_20 < sma_50 < sma_200 else 0)
    rsi_bullish = 1 if rsi_val > 55 else (-1 if rsi_val < 45 else 0)
    macd_bullish = 1 if hist_val > 0 else (-1 if hist_val < 0 else 0)
    regime_dir = regime.get("trend_direction", "Neutral")
    regime_bullish = 1 if regime_dir in ("Yukselis", "Bullish", "Uptrend") else (-1 if regime_dir in ("Dusus", "Bearish", "Downtrend") else 0)
    raw = sma_bullish + price_bullish + rsi_bullish + macd_bullish + regime_bullish
    confluenced_score = max(-3, min(3, raw))
    if confluenced_score >= 2:
        label = "Güçlü pozitif uyum"
    elif confluenced_score >= 1:
        label = "Pozitif uyum"
    elif confluenced_score >= -1:
        label = "Uyumsuz / Nötr"
    elif confluenced_score >= -2:
        label = "Negatif uyum"
    else:
        label = "Güçlü negatif uyum"
    return {"confluence_score": confluenced_score, "confluence_label": label, "components": {"sma_alignment": sma_bullish, "price_vs_sma": price_bullish, "rsi": rsi_bullish, "macd": macd_bullish, "regime": regime_bullish}}


def _regime_tr(regime: str) -> str:
    t = {
        "Strong Trend": "Güçlü Trend (Strong Trend)",
        "Weak Trend": "Zayıf Trend (Weak Trend)",
        "Range Bound": "Bant (Range Bound)",
        "Choppy / Uncertain": "Dalgalı / Belirsiz (Choppy / Uncertain)",
    }
    return t.get(regime, regime)

def _trend_dir_tr(direction: str) -> str:
    t = {
        "Bullish": "Yükseliş (Bullish)",
        "Bearish": "Düşüş (Bearish)",
        "Neutral": "Nötr (Neutral)",
        "Uptrend": "Yükseliş (Uptrend)",
        "Downtrend": "Düşüş (Downtrend)",
    }
    return t.get(direction, direction)

def _volatility_tr(vol: str) -> str:
    t = {
        "Normal": "Normal",
        "High Volatility": "Yüksek Volatilite",
        "Low Volatility": "Düşük Volatilite",
    }
    return t.get(vol, vol)

def _generate_executive_summary(ticker: str, close: float, score: float, trend_data: Dict,
                                 rsi_val: float, regime: Dict, sr_zones: Dict,
                                 volume_profile: Dict, divergences: Dict = None,
                                 confluence: Dict = None, candle_patterns: list = None,
                                 chart_patterns: list = None, unit: str = "TL") -> str:
    trend_word = trend_data.get("character", "yatay")
    regime_word = _regime_tr(regime.get("regime", "belirsiz"))
    trend_dir = _trend_dir_tr(regime.get("trend_direction", "Nötr"))
    nearest_sup = sr_zones.get("nearest_support", {}).get("price", 0)
    nearest_res = sr_zones.get("nearest_resistance", {}).get("price", 0)

    rsi_status = "nötr"
    if rsi_val > 70:
        rsi_status = "aşırı alım"
    elif rsi_val > 55:
        rsi_status = "pozitif momentum"
    elif rsi_val < 30:
        rsi_status = "aşırı satım"
    elif rsi_val < 45:
        rsi_status = "zayıf momentum"

    entity_type = "endeks" if ticker.startswith('X') else "hisse"
    summary = (
        f"{ticker} {entity_type}i mevcut görünüm itibarıyla {trend_word} safhasındadır. "
        f"Teknik skor {score:.0f}/100 seviyesinde olup {regime_word} rejimi ({trend_dir}) gözlemlenmektedir. "
        f"Momentum göstergeleri {rsi_status} bölgesindedir. "
    )
    if confluence:
        conf = confluence.get("confluence_score", 0)
        if conf >= 2:
            summary += "Göstergeler arasında güçlü pozitif uyum bulunmaktadır. "
        elif conf <= -2:
            summary += "Göstergeler arasında güçlü negatif uyumsuzluk bulunmaktadır. "
        elif conf != 0:
            summary += "Göstergeler arasında kısmi uyum mevcuttur. "
    if divergences:
        dc = divergences.get("divergence_count", 0)
        if dc >= 2:
            summary += f"{dc} göstergede uyumsuzluk (divergence) tespit edilmiştir. "
        elif dc == 1:
            summary += "Bir göstergede uyumsuzluk (divergence) tespit edilmiştir. "
    if candle_patterns:
        bullish = [p for p in candle_patterns if p.get("direction") == "Bullish"]
        bearish = [p for p in candle_patterns if p.get("direction") == "Bearish"]
        if bullish:
            summary += f"Mum formasyonlarında {bullish[0]['name']} gibi pozitif sinyaller bulunmaktadır. "
        if bearish:
            summary += f"Mum formasyonlarında {bearish[0]['name']} gibi negatif sinyaller bulunmaktadır. "
    if chart_patterns:
        summary += f"Teknik formasyon olarak {chart_patterns[0]['name']} tespit edilmiştir. "
    if nearest_sup > 0:
        summary += f"Kritik destek {_fmt_price(nearest_sup, unit)} seviyesindedir. "
    if nearest_res > 0:
        summary += f"Yukarı yönlü hareket için öncelikli teyit noktası {_fmt_price(nearest_res, unit)} seviyesidir. "
    return summary


async def generate_ceo_report(ticker: str) -> Dict[str, Any]:
    try:
        ticker_upper = ticker.upper()
        data = await get_historical_prices(ticker_upper, limit=500)
        if not data:
            return {"error": f"No historical data found for {ticker_upper}"}
        data = _overlay_live_data(ticker_upper, data)

        cols = {
            "open": [float(r.get("open", 0) or 0) for r in data],
            "high": [float(r.get("high", 0) or 0) for r in data],
            "low": [float(r.get("low", 0) or 0) for r in data],
            "close": [float(r.get("close", 0) or 0) for r in data],
            "volume": [float(r.get("volume", 0) or 0) for r in data],
        }
        c = cols["close"]
        h = cols["high"]
        l = cols["low"]
        v = cols["volume"]
        close = c[-1]

        # Indicators
        rsi_vals = indicators.rsi(c)
        rsi_val = rsi_vals[-1] if rsi_vals[-1] is not None else 50
        macd_vals = indicators.macd(c)
        macd_line = [v for v in macd_vals["macd"] if v is not None]
        sig_line = [v for v in macd_vals["signal"] if v is not None]
        hist_line = [v for v in macd_vals["histogram"] if v is not None]
        macd_val = macd_line[-1] if macd_line else 0
        signal_val = sig_line[-1] if sig_line else 0
        hist_val = hist_line[-1] if hist_line else 0

        sma_20 = indicators.sma(c, 20)
        sma_50 = indicators.sma(c, 50)
        sma_200 = indicators.sma(c, 200)
        sma_20_val = sma_20[-1] if sma_20[-1] is not None else close
        sma_50_val = sma_50[-1] if sma_50[-1] is not None else close
        sma_200_val = sma_200[-1] if sma_200[-1] is not None else close
        ema_9_line = indicators.ema(c, 9)
        ema_21_line = indicators.ema(c, 21)
        ema_9_val = ema_9_line[-1] if ema_9_line[-1] is not None else close
        ema_21_val = ema_21_line[-1] if ema_21_line[-1] is not None else close

        atr_vals = indicators.atr(h, l, c)
        atr_val = atr_vals[-1] if atr_vals[-1] is not None else 0

        bb = indicators.bollinger_bands(c)
        obv_vals = indicators.obv(c, v)
        mfi_vals = indicators.mfi(h, l, c, v)
        stoch = indicators.stochastic(h, l, c)
        stoch_k = stoch["k"][-1] if stoch["k"][-1] is not None else 50
        stoch_d = stoch["d"][-1] if stoch["d"][-1] is not None else 50
        st = indicators.supertrend(h, l, c)
        st_val = st["supertrend"][-1] if st["supertrend"][-1] is not None else close
        st_dir = st["trend"][-1] if st["trend"][-1] is not None else 1
        vwap_vals = indicators.vwap(data)
        vwap_val = vwap_vals[-1] if vwap_vals[-1] is not None else close

        # Advanced
        regime = detect_market_regime(data)
        volume_profile = calculate_volume_profile(data[-100:], num_bins=50)
        liquidity_voids = detect_liquidity_voids(data, threshold=2.5)
        sr_zones = calculate_support_resistance_zones(data, lookback=60)
        score_data = enhanced_technical_score(data, regime)

        # Pattern detection
        candle_patterns = detect_candlestick_patterns(data)
        chart_patterns = detect_chart_patterns(data, 120)
        pattern_score = calculate_pattern_score(data)

        # Divergence detection (needs rsi_vals, macd_line)
        try:
            rsi_div = indicators.detect_divergences(c, rsi_vals)
            macd_div = indicators.detect_divergences(c, macd_line) if macd_line else None
            divergences = calculate_divergence_confidence(data, rsi_div=rsi_div, macd_div=macd_div)
        except Exception as de:
            logger.error(f"Divergence error for {ticker}: {de}", exc_info=True)
            divergences = {"rsi": {"bullish": False, "bearish": False}, "macd": {"bullish": False, "bearish": False}, "obv": {"bullish": False, "bearish": False}, "overall_confidence": "Low", "divergence_count": 0}

        # Confluence score (needs regime, score_data)
        confluence = _calculate_confluence_score(
            close, sma_20_val, sma_50_val, sma_200_val,
            rsi_val, hist_val, regime
        )

        trend_data = _trend_interpretation(score_data['score'], close, sma_20_val, sma_50_val, sma_200_val)

        nearest_support = sr_zones.get("nearest_support", {}).get("price", close * 0.95) if "error" not in sr_zones else close * 0.95
        nearest_resistance = sr_zones.get("nearest_resistance", {}).get("price", close * 1.05) if "error" not in sr_zones else close * 1.05

        stop_loss = max(close - (2.0 * atr_val), nearest_support)
        take_profit = nearest_resistance
        rr_ratio = abs(take_profit - close) / abs(close - stop_loss) if abs(close - stop_loss) > 0 else 0

        unit = "puan" if ticker_upper.startswith('X') else "TL"
        executive_summary = _generate_executive_summary(
            ticker_upper, close, score_data['score'], trend_data,
            rsi_val, regime, sr_zones, volume_profile,
            divergences=divergences, confluence=confluence,
            candle_patterns=candle_patterns, chart_patterns=chart_patterns,
            unit=unit
        )

        return {
            "ticker": ticker_upper,
            "report_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "current_price": round(close, 2),
            "unit": unit,
            "executive_summary": executive_summary,
            "overview": {
                "technical_score": score_data['score'],
                "confidence": score_data['confidence'],
                "short_term_trend": trend_data['short'],
                "medium_term_trend": trend_data['medium'],
                "long_term_trend": trend_data['long'],
                "price_character": trend_data['character'],
                "market_regime": _regime_tr(regime.get('regime', 'Unknown')),
                "trend_direction": _trend_dir_tr(regime.get('trend_direction', 'Neutral')),
                "volatility_regime": _volatility_tr(regime.get('volatility_regime', 'Normal')),
                "recommended_strategy": regime.get('recommended_strategy', ''),
                "confluence_score": confluence.get("confluence_score", 0),
                "confluence_label": confluence.get("confluence_label", ""),
                "score_components": {
                    "trend": score_data.get("trend_component", 0),
                    "momentum": score_data.get("momentum_component", 0),
                    "volume": score_data.get("volume_component", 0),
                    "pattern": pattern_score.get("score", 0),
                },
            },
            "key_levels": {
                "support_1": {"price": round(nearest_support, 2), "importance": "Kısa vadeli savunma alanı", "scenario": "Tutunma halinde tepki potansiyeli"},
                "support_2": {"price": round(close * 0.93, 2), "importance": "Ana destek", "scenario": "Kırılım halinde risk artışı"},
                "resistance_1": {"price": round(nearest_resistance, 2), "importance": "İlk engel", "scenario": "Momentum teyidi gerekli"},
                "resistance_2": {"price": round(nearest_resistance * 1.05, 2), "importance": "Trend değişim seviyesi", "scenario": "Yeni fiyat keşfi potansiyeli"},
                "stop_loss": round(stop_loss, 2),
                "take_profit": round(take_profit, 2),
                "risk_reward_ratio": round(rr_ratio, 2),
            },
            "indicators": {
                "rsi": {
                    "value": round(rsi_val, 1),
                    "interpretation": _rsi_interpretation(rsi_val),
                    "status": "Aşırı Alım" if rsi_val > 70 else "Aşırı Satım" if rsi_val < 30 else "Nötr",
                },
                "macd": {
                    "macd_line": round(macd_val, 2),
                    "signal_line": round(signal_val, 2),
                    "histogram": round(hist_val, 2),
                    "interpretation": _macd_interpretation(macd_val, signal_val, hist_val),
                },
                "moving_averages": {
                    "sma_20": round(sma_20_val, 2),
                    "sma_50": round(sma_50_val, 2),
                    "sma_200": round(sma_200_val, 2),
                    "ema_9": round(ema_9_val, 2),
                    "ema_21": round(ema_21_val, 2),
                    "price_vs_sma20": "Üstünde" if close > sma_20_val else "Altında",
                    "price_vs_sma50": "Üstünde" if close > sma_50_val else "Altında",
                    "price_vs_sma200": "Üstünde" if close > sma_200_val else "Altında",
                    "price_vs_ema9": "Üstünde" if close > ema_9_val else "Altında",
                    "price_vs_ema21": "Üstünde" if close > ema_21_val else "Altında",
                    "golden_cross": sma_50_val > sma_200_val,
                },
                "volatility": {
                    "atr": round(atr_val, 2),
                    "atr_percent": round((atr_val / close) * 100, 2) if close > 0 else 0,
                    "bollinger_upper": round(bb["upper"][-1] if bb["upper"][-1] is not None else close * 1.04, 2),
                    "bollinger_lower": round(bb["lower"][-1] if bb["lower"][-1] is not None else close * 0.96, 2),
                },
                "volume": {
                    "obv_trend": "Pozitif" if obv_vals[-1] > 0 else "Negatif",
                    "mfi": round(mfi_vals[-1] if mfi_vals[-1] is not None else 50, 1),
                },
                "stochastic": {
                    "k": round(stoch_k, 1),
                    "d": round(stoch_d, 1),
                    "status": "Aşırı Alım" if stoch_k > 80 else "Aşırı Satım" if stoch_k < 20 else "Nötr",
                },
                "supertrend": {
                    "value": round(st_val, 2),
                    "direction": "Yükseliş" if st_dir == 1 else "Düşüş",
                },
                "vwap": round(vwap_val, 2),
                "adx_details": {
                    "adx": round(regime.get("adx", 0), 1),
                    "efficiency_ratio": round(regime.get("efficiency_ratio", 0), 2),
                },
            },
            "scenarios": {
                "positive": {
                    "name": "Pozitif Senaryo",
                    "conditions": [f"Direnç {_fmt_price(nearest_resistance, unit)} seviyesinin hacim eşliğinde kırılması", "RSI'nin 50 üstünde kalıcı olması"],
                    "target": f"Hedef: {_fmt_price(nearest_resistance * 1.05, unit)} - {_fmt_price(nearest_resistance * 1.10, unit)}",
                    "probability": "Yüksek" if (score_data['score'] > 60 and confluence.get("confluence_score", 0) >= 0) else ("Düşük" if confluence.get("confluence_score", 0) <= -2 else "Orta"),
                },
                "neutral": {
                    "name": "Nötr / Konsolidasyon Senaryosu",
                    "conditions": [f"Fiyatın {_fmt_price(nearest_support, unit)} - {_fmt_price(nearest_resistance, unit)} aralığında hareketi"],
                    "strategy": "Teyit beklenmeli, ani pozisyon değişikliğinden kaçınılmalı",
                    "probability": "Orta",
                },
                "negative": {
                    "name": "Negatif Senaryo",
                    "conditions": [f"Destek {_fmt_price(nearest_support, unit)} seviyesinin kırılması", "RSI'nin 40 altına gerilemesi"],
                    "risk": f"Risk: {_fmt_price(close * 0.90, unit)} - {_fmt_price(close * 0.85, unit)}",
                    "probability": "Yüksek" if (score_data['score'] <= 40 and confluence.get("confluence_score", 0) <= -1) else ("Düşük" if (score_data['score'] > 55 and confluence.get("confluence_score", 0) >= 1) else "Orta"),
                },
            },
            "volume_profile": {
                "poc": volume_profile.get('poc', close),
                "value_area_high": volume_profile.get('value_area_high', close * 1.02),
                "value_area_low": volume_profile.get('value_area_low', close * 0.98),
                "poc_volume": volume_profile.get('poc_volume', 0),
                "total_volume": volume_profile.get('total_volume', 0),
                "interpretation": (
                    f"Hacim profili analizi {_fmt_price(volume_profile.get('poc', close), unit)} seviyesinde "
                    f"en yüksek yoğunluğu göstermektedir."
                ) if "error" not in volume_profile else "Hacim profili verisi yeterli değil",
            },
            "liquidity_voids": [
                {"price": round(v.get("price", 0), 2), "gap_percent": round(v.get("gap_percent", 0), 2), "severity": v.get("severity", "Unknown"), "direction": v.get("direction", "up"), "bars_ago": v.get("bars_ago", 0)}
                for v in liquidity_voids[:3]
            ],
            "divergences": {
                "rsi": divergences.get("rsi", {"bullish": False, "bearish": False}),
                "macd": divergences.get("macd", {"bullish": False, "bearish": False}),
                "obv": divergences.get("obv", {"bullish": False, "bearish": False}),
                "divergence_count": divergences.get("divergence_count", 0),
                "overall_confidence": divergences.get("overall_confidence", "Low"),
                "summary": (
                    f"{divergences.get('divergence_count', 0)} göstergede uyumsuzluk."
                ) if divergences.get("divergence_count", 0) > 0 else "Belirgin uyumsuzluk tespit edilmedi.",
            },
            "patterns": {
                "candlestick": [{"name": p["name"], "direction": p["direction"], "reliability": p["reliability"], "bars_ago": p["bars_ago"]} for p in candle_patterns],
                "chart": [{"name": p["name"], "direction": p["direction"], "confidence": p["confidence"], "entry_price": p.get("entry_price"), "target_price": p.get("target_price"), "volume_confirmed": p.get("volume_confirmed", False)} for p in chart_patterns],
                "pattern_score": pattern_score.get("score", 0),
                "pattern_direction": pattern_score.get("direction", "Neutral"),
                "active_count": pattern_score.get("active_count", 0),
            },
            "risk_assessment": {
                "technical_risks": ["Destek seviyesi kırılımı", "Momentum göstergelerinde bozulma", "Hacim düşüşü ile likidite azalması"],
                "technical_opportunities": ["Aşırı satım bölgelerinden tepki potansiyeli", "Pozitif uyumsuzluk oluşumu", "Formasyon tamamlanması"],
                "beta": None,
                "market_breadth": None,
            },
            "izlenmesi_gerekenler": {
                "not": f"{ticker_upper} için yakından izlenmesi gereken kritik seviye {_fmt_price(nearest_support, unit)} desteği ve {_fmt_price(nearest_resistance, unit)} direncidir. "
                       f"RSI {rsi_val:.1f} seviyesinde olup {_trend_dir_tr(regime.get('trend_direction', 'Neutral'))} yönünde sinyal vermektedir. "
                       f"Hacim gelişmeleri ve momentumdaki olası değişimler takip edilmelidir.",
                "kritik_seviyeler": [
                    f"Destek {_fmt_price(nearest_support, unit)} — kırılırsa satış baskısı artabilir",
                    f"Direnç {_fmt_price(nearest_resistance, unit)} — aşılırsa yükseliş ivmelenebilir",
                ],
                "izlenecek_konular": [
                    "RSI'nin aşırı satım/aşırı alım bölgelerine yaklaşımı",
                    "MACD histogramının yön değiştirmesi",
                    "Hacimde anormal artış/azalış",
                    "Alt/üst trend çizgilerine yaklaşım",
                ],
            },
        }
    except Exception as e:
        logger.error(f"CEO report error for {ticker}: {e}", exc_info=True)
        return {"error": str(e)}
