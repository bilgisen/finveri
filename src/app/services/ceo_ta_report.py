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
)

logger = logging.getLogger(__name__)


def _fmt_price(val: float, unit: str = "TL") -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "-"
    return f"{val:,.2f} {unit}"


def _trend_interpretation(score: float, close: float, sma_20: float, sma_50: float, sma_200: float) -> Dict[str, str]:
    interp = {}
    interp["short"] = "Kisa vadeli yapi pozitif" if close > sma_20 else "Kisa vadeli yapida zayiflama"
    interp["medium"] = "Orta vadeli trend yapisi korunuyor" if sma_20 > sma_50 else "Orta vadeli yapida bozulma"
    interp["long"] = "Uzun vadeli ana trend korunuyor" if close > sma_200 else "Uzun vadeli ana trend zayifliyor"
    if score > 65:
        interp["character"] = "Yukselis"
    elif score > 45:
        interp["character"] = "Yatay konsolidasyon"
    elif score > 30:
        interp["character"] = "Duzeltme"
    else:
        interp["character"] = "Trend donusumu riski"
    return interp


def _rsi_interpretation(rsi_val: float, prev_rsi: float = None) -> str:
    if rsi_val > 70:
        return "Asiri alim bolgesinde, kar satisi riski bulunuyor."
    elif rsi_val > 60:
        return "Momentum pozitif ancak asiri alima yaklasiliyor."
    elif rsi_val > 45:
        return "Notr bolge, belirgin bir momentum yonu yok."
    elif rsi_val > 30:
        return "Momentum zayifliyor, ancak asiri satima yaklasim tepki potansiyeli olusturuyor."
    else:
        return "Asiri satim bolgesinde, kisa vadeli tepki potansiyeli yuksek."


def _macd_interpretation(macd_val: float, signal_val: float, hist_val: float) -> str:
    if hist_val > 0 and macd_val > signal_val:
        return "Pozitif momentum devam ediyor, trend guclu."
    elif hist_val > 0:
        return "Histogram pozitife dondu, ancak kesisim henuz kesinlesmedi."
    elif hist_val < 0 and macd_val < signal_val:
        return "Negatif momentum devam ediyor, satis baskisi hakim."
    else:
        return "Histogram negatif bolgede, ancak zayiflama sinyalleri var."


def _generate_executive_summary(ticker: str, close: float, score: float, trend_data: Dict,
                                 rsi_val: float, regime: Dict, sr_zones: Dict,
                                 volume_profile: Dict, unit: str = "TL") -> str:
    trend_word = trend_data.get("character", "yatay")
    regime_word = regime.get("regime", "belirsiz")
    trend_dir = regime.get("trend_direction", "Notr")
    nearest_sup = sr_zones.get("nearest_support", {}).get("price", 0)
    nearest_res = sr_zones.get("nearest_resistance", {}).get("price", 0)

    rsi_status = "notr"
    if rsi_val > 70:
        rsi_status = "asiri alim"
    elif rsi_val > 55:
        rsi_status = "pozitif momentum"
    elif rsi_val < 30:
        rsi_status = "asiri satim"
    elif rsi_val < 45:
        rsi_status = "zayif momentum"

    entity_type = "endeks" if ticker.startswith('X') else "hisse"
    summary = (
        f"{ticker} {entity_type}i mevcut gorunum itibariyla {trend_word} safhasindadir. "
        f"Teknik skor {score:.0f}/100 seviyesinde olup {regime_word} yapisi ({trend_dir}) gozlemlenmektedir. "
        f"Momentum gostergeleri {rsi_status} bolgesindedir. "
    )
    if nearest_sup > 0:
        summary += f"Kritik destek {_fmt_price(nearest_sup, unit)} seviyesindedir. "
    if nearest_res > 0:
        summary += f"Yukari yonlu hareket icin oncelikli teyit noktasi {_fmt_price(nearest_res, unit)} seviyesidir. "
    summary += "Teknik gorunum tek basina yatirim karari icin degil, mevcut piyasa davranisini anlamak icin degerlendirilmelidir."
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

        atr_vals = indicators.atr(h, l, c)
        atr_val = atr_vals[-1] if atr_vals[-1] is not None else 0

        bb = indicators.bollinger_bands(c)
        obv_vals = indicators.obv(c, v)
        mfi_vals = indicators.mfi(h, l, c, v)

        # Advanced
        regime = detect_market_regime(data)
        volume_profile = calculate_volume_profile(data[-100:], num_bins=50)
        liquidity_voids = detect_liquidity_voids(data, threshold=2.5)
        sr_zones = calculate_support_resistance_zones(data, lookback=60)
        score_data = enhanced_technical_score(data, regime)

        trend_data = _trend_interpretation(score_data['score'], close, sma_20_val, sma_50_val, sma_200_val)

        nearest_support = sr_zones.get("nearest_support", {}).get("price", close * 0.95) if "error" not in sr_zones else close * 0.95
        nearest_resistance = sr_zones.get("nearest_resistance", {}).get("price", close * 1.05) if "error" not in sr_zones else close * 1.05

        if score_data['score'] > 55:
            stop_loss = max(close - (1.5 * atr_val), nearest_support)
            take_profit = nearest_resistance
        else:
            stop_loss = min(close + (1.5 * atr_val), nearest_resistance)
            take_profit = nearest_support
        rr_ratio = abs(take_profit - close) / abs(close - stop_loss) if abs(close - stop_loss) > 0 else 0

        unit = "puan" if ticker_upper.startswith('X') else "TL"
        executive_summary = _generate_executive_summary(
            ticker_upper, close, score_data['score'], trend_data,
            rsi_val, regime, sr_zones, volume_profile, unit
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
                "market_regime": regime.get('regime', 'Unknown'),
                "trend_direction": regime.get('trend_direction', 'Neutral'),
                "recommended_strategy": regime.get('recommended_strategy', ''),
            },
            "key_levels": {
                "support_1": {"price": round(nearest_support, 2), "importance": "Kisa vadeli savunma alani", "scenario": "Tutunma halinde tepki potansiyeli"},
                "support_2": {"price": round(close * 0.93, 2), "importance": "Ana destek", "scenario": "Kirilim halinde risk artisi"},
                "resistance_1": {"price": round(nearest_resistance, 2), "importance": "Ilk engel", "scenario": "Momentum teyidi gerekli"},
                "resistance_2": {"price": round(nearest_resistance * 1.05, 2), "importance": "Trend degisim seviyesi", "scenario": "Yeni fiyat kesfi potansiyeli"},
                "stop_loss": round(stop_loss, 2),
                "take_profit": round(take_profit, 2),
                "risk_reward_ratio": round(rr_ratio, 2),
            },
            "indicators": {
                "rsi": {
                    "value": round(rsi_val, 1),
                    "interpretation": _rsi_interpretation(rsi_val),
                    "status": "Asiri Alim" if rsi_val > 70 else "Asiri Satim" if rsi_val < 30 else "Notr",
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
                    "price_vs_sma20": "Ustunde" if close > sma_20_val else "Altinda",
                    "price_vs_sma50": "Ustunde" if close > sma_50_val else "Altinda",
                    "price_vs_sma200": "Ustunde" if close > sma_200_val else "Altinda",
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
            },
            "scenarios": {
                "positive": {
                    "name": "Pozitif Senaryo",
                    "conditions": [f"Direnc {_fmt_price(nearest_resistance, unit)} seviyesinin hacim esliginde kirilmasi", "RSI'nin 50 ustunde kalici olmasi"],
                    "target": f"Hedef: {_fmt_price(nearest_resistance * 1.05, unit)} - {_fmt_price(nearest_resistance * 1.10, unit)}",
                    "probability": "Yuksek" if score_data['score'] > 60 else "Orta",
                },
                "neutral": {
                    "name": "Notr / Konsolidasyon Senaryosu",
                    "conditions": [f"Fiyatin {_fmt_price(nearest_support, unit)} - {_fmt_price(nearest_resistance, unit)} araliginda hareketi"],
                    "strategy": "Teyit beklenmeli, ani pozisyon degisikliginden kacinilmali",
                    "probability": "Orta",
                },
                "negative": {
                    "name": "Negatif Senaryo",
                    "conditions": [f"Destek {_fmt_price(nearest_support, unit)} seviyesinin kirilmasi", "RSI'nin 40 altina gerilemesi"],
                    "risk": f"Risk: {_fmt_price(close * 0.90, unit)} - {_fmt_price(close * 0.85, unit)}",
                    "probability": "Dusuk" if score_data['score'] > 50 else "Orta",
                },
            },
            "volume_profile": {
                "poc": volume_profile.get('poc', close),
                "value_area_high": volume_profile.get('value_area_high', close * 1.02),
                "value_area_low": volume_profile.get('value_area_low', close * 0.98),
                "interpretation": (
                    f"Hacim profili analizi {_fmt_price(volume_profile.get('poc', close), unit)} seviyesinde "
                    f"en yuksek yogunlugu gostermektedir."
                ) if "error" not in volume_profile else "Hacim profili verisi yeterli degil",
            },
            "risk_assessment": {
                "technical_risks": ["Destek seviyesi kirilimi", "Momentum gostergelerinde bozulma", "Hacim dususu ile likidite azalmasi"],
                "technical_opportunities": ["Asiri satim bolgelerinden tepki potansiyeli", "Pozitif uyumsuzluk olusumu", "Formasyon tamamlanmasi"],
                "beta": None,
                "market_breadth": None,
            },
            "watchlist": {
                "daily": ["Fiyat / kritik destek-direnc seviyeleri", "Islem hacmi degisimi", "RSI ve MACD yon takibi"],
                "weekly": ["Haftalik kapanis seviyesi", "Hareketli ortalamalar yonu", "Genel piyasa trendi"],
            },
            "disclaimer": "Bu rapor teknik analiz verilerine dayali olarak hazirlanmis olup yatirim tavsiyesi niteligi tasimamaktadir.",
        }
    except Exception as e:
        logger.error(f"CEO report error for {ticker}: {e}", exc_info=True)
        return {"error": str(e)}
