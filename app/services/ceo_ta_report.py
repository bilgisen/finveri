"""
CEO / Yönetim Kurulu Seviyesi Teknik Analiz Raporu
Profesyonel, aksiyon odaklı, senaryo bazlı raporlama
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.ta_engine import get_historical_dataframe, calculate_beta, get_market_breadth
from app.services.advanced_ta import (
    calculate_volume_profile,
    detect_market_regime,
    detect_liquidity_voids,
    calculate_support_resistance_zones,
    enhanced_technical_score
)

logger = logging.getLogger(__name__)


def _fmt_price(val: float, unit: str = "TL") -> str:
    """Format price with unit"""
    if val is None or pd.isna(val):
        return "-"
    return f"{val:,.2f} {unit}"


def _trend_interpretation(score: float, close: float, sma_20: float, sma_50: float, sma_200: float) -> Dict[str, str]:
    """Generate executive-friendly trend interpretation"""
    interpretations = {}
    
    # Short-term
    if close > sma_20:
        interpretations["short"] = "Kısa vadeli yapı pozitif, fiyat kısa vadeli ortalamanın üzerinde seyrediyor"
    else:
        interpretations["short"] = "Kısa vadeli yapıda zayıflama mevcut, fiyat kısa vadeli ortalamanın altında"
    
    # Medium-term
    if sma_20 > sma_50:
        interpretations["medium"] = "Orta vadeli trend yapısı korunuyor, kısa vadeli ortalama orta vadeli ortalamanın üzerinde"
    else:
        interpretations["medium"] = "Orta vadeli yapıda bozulma sinyalleri var, kısa vadeli ortalama orta vadeli ortalamanın altında"
    
    # Long-term
    if close > sma_200:
        interpretations["long"] = "Uzun vadeli ana trend yapısı korunuyor"
    else:
        interpretations["long"] = "Uzun vadeli ana trend yapısı zayıflama sürecinde"
    
    # Price character
    if score > 65:
        interpretations["character"] = "Yükseliş"
    elif score > 45:
        interpretations["character"] = "Yatay konsolidasyon"
    elif score > 30:
        interpretations["character"] = "Düzeltme"
    else:
        interpretations["character"] = "Trend dönüşümü riski"
    
    return interpretations


def _rsi_interpretation(rsi_val: float, prev_rsi: float = None) -> str:
    """Executive-level RSI interpretation"""
    if rsi_val > 70:
        return "Aşırı alım bölgesinde, kar satışı riski bulunuyor. Yeni alım için geri çekilme beklenmeli."
    elif rsi_val > 60:
        return "Momentum pozitif ancak aşırı alıma yaklaşılıyor. Mevcut pozisyonlar korunabilir."
    elif rsi_val > 45:
        return "Nötr bölge, belirgin bir momentum yönü yok. Kararlı bir hareket için teyit beklenmeli."
    elif rsi_val > 30:
        return "Momentum tarafında zayıflama var, ancak aşırı satım bölgesine yaklaşım tepki potansiyeli oluşturuyor."
    else:
        return "Aşırı satım bölgesinde,短期 tepki hareketi potansiyeli yüksek. Ancak düşüşün devamı için destek kırılımı beklenmeli."


def _macd_interpretation(macd_val: float, signal_val: float, hist_val: float) -> str:
    """Executive-level MACD interpretation"""
    if hist_val > 0 and macd_val > signal_val:
        return "Pozitif momentum devam ediyor, trend güçlü. Alış baskısı hakim."
    elif hist_val > 0:
        return "Histogram pozitife döndü, ancak kesişim henüz kesinleşmedi. Momentum dönüşü için teyit beklenmeli."
    elif hist_val < 0 and macd_val < signal_val:
        return "Negatif momentum devam ediyor, satış baskısı hakim."
    else:
        return "Histogram negatif bölgede, ancak zayıflama sinyalleri var. Trend dönüşü erken safhada olabilir."


def _generate_executive_summary(
    ticker: str,
    close: float,
    score: float,
    trend_data: Dict,
    rsi_val: float,
    regime: Dict,
    sr_zones: Dict,
    volume_profile: Dict
) -> str:
    """1 paragraflık CEO özeti"""
    
    trend_word = trend_data.get("character", "yatay")
    regime_word = regime.get("regime", "belirsiz")
    trend_dir = regime.get("trend_direction", "Nötr")
    
    # Support/resistance info
    nearest_sup = sr_zones.get("nearest_support", {}).get("price", 0)
    nearest_res = sr_zones.get("nearest_resistance", {}).get("price", 0)
    
    # RSI interpretation
    rsi_status = "nötr"
    if rsi_val > 70:
        rsi_status = "aşırı alım"
    elif rsi_val > 55:
        rsi_status = "pozitif momentum"
    elif rsi_val < 30:
        rsi_status = "aşırı satım"
    elif rsi_val < 45:
        rsi_status = "zayıf momentum"
    
    summary = (
        f"{ticker} hissesi mevcut görünüm itibarıyla {trend_word} safhasındadır. "
        f"Teknik skor {score:.0f}/100 seviyesinde olup {regime_word} yapısı ({trend_dir}) gözlemlenmektedir. "
        f"Momentum göstergeleri {rsi_status} bölgesindedir. "
    )
    
    if nearest_sup > 0:
        summary += f"Kritik destek {_fmt_price(nearest_sup)} seviyesinde olup, bu bölge korunursa mevcut trend yapısı savunulabilir. "
    
    if nearest_res > 0:
        summary += f"Yukarı yönlü hareket için öncelikli teyit noktası {_fmt_price(nearest_res)} seviyesidir. "
    
    summary += (
        f"Teknik görünüm tek başına yatırım kararı üretmek için değil, mevcut piyasa davranışını anlamak ve "
        f"kritik eşikleri takip etmek için değerlendirilmelidir."
    )
    
    return summary


def generate_ceo_report(ticker: str) -> Dict[str, Any]:
    """
    CEO / Yönetim Kurulu seviyesinde profesyonel teknik analiz raporu üretir.
    """
    try:
        ticker_upper = ticker.upper()
        
        # Fetch historical data
        df = get_historical_dataframe.__wrapped__(ticker_upper, limit=500) if hasattr(get_historical_dataframe, '__wrapped__') else None
        
        # Use sync wrapper for now
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context
            pass
        
        # Calculate all indicators
        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.adx(length=14, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.supertrend(period=7, multiplier=3, append=True)
        df.ta.stoch(k=14, d=3, smooth_k=3, append=True)
        df.ta.mfi(length=14, append=True)
        df.ta.obv(append=True)
        
        last_row = df.iloc[-1].to_dict()
        close = last_row.get('close', 0)
        
        # Get advanced analysis
        regime = detect_market_regime(df)
        volume_profile = calculate_volume_profile(df.tail(100), num_bins=50)
        liquidity_voids = detect_liquidity_voids(df, threshold=2.5)
        sr_zones = calculate_support_resistance_zones(df, lookback=60)
        score_data = enhanced_technical_score(df, regime)
        
        # Key indicators
        rsi_col = [c for c in last_row.keys() if 'RSI' in c]
        rsi_val = last_row.get(rsi_col[0], 50) if rsi_col else 50
        
        macd_col = [c for c in last_row.keys() if 'MACD_' in c and 's' not in c and 'h' not in c]
        macd_val = last_row.get(macd_col[0], 0) if macd_col else 0
        
        macds_col = [c for c in last_row.keys() if 'MACDs_' in c]
        signal_val = last_row.get(macds_col[0], 0) if macds_col else 0
        
        macdh_col = [c for c in last_row.keys() if 'MACDh_' in c]
        hist_val = last_row.get(macdh_col[0], 0) if macdh_col else 0
        
        sma_20 = last_row.get('SMA_20', close)
        sma_50 = last_row.get('SMA_50', close)
        sma_200 = last_row.get('SMA_200', close)
        
        atr_val = last_row.get('ATRr_14', 0)
        
        # Trend interpretations
        trend_data = _trend_interpretation(score_data['score'], close, sma_20, sma_50, sma_200)
        
        # Support/Resistance
        nearest_support = sr_zones.get('nearest_support', {}).get('price', close * 0.95) if 'error' not in sr_zones else close * 0.95
        nearest_resistance = sr_zones.get('nearest_resistance', {}).get('price', close * 1.05) if 'error' not in sr_zones else close * 1.05
        
        # Stop loss & take profit
        if score_data['score'] > 55:
            stop_loss = max(close - (1.5 * atr_val), nearest_support)
            take_profit = nearest_resistance
        else:
            stop_loss = min(close + (1.5 * atr_val), nearest_resistance)
            take_profit = nearest_support
        
        rr_ratio = abs(take_profit - close) / abs(close - stop_loss) if abs(close - stop_loss) > 0 else 0
        
        # Executive Summary
        executive_summary = _generate_executive_summary(
            ticker_upper, close, score_data['score'], trend_data,
            rsi_val, regime, sr_zones, volume_profile
        )
        
        # Build report
        report = {
            "ticker": ticker_upper,
            "report_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "current_price": round(close, 2),
            
            # Executive Summary
            "executive_summary": executive_summary,
            
            # Section 1: Executive Overview
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
            
            # Section 2: Key Levels
            "key_levels": {
                "support_1": {
                    "price": round(nearest_support, 2),
                    "importance": "Kısa vadeli savunma alanı",
                    "scenario": "Tutunma halinde tepki potansiyeli"
                },
                "support_2": {
                    "price": round(close * 0.93, 2),
                    "importance": "Ana destek",
                    "scenario": "Kırılım halinde risk artışı, trend bozulması"
                },
                "resistance_1": {
                    "price": round(nearest_resistance, 2),
                    "importance": "İlk engel",
                    "scenario": "Momentum teyidi required"
                },
                "resistance_2": {
                    "price": round(nearest_resistance * 1.05, 2),
                    "importance": "Trend değişim seviyesi",
                    "scenario": "Yeni fiyat keşfi potansiyeli"
                },
                "stop_loss": round(stop_loss, 2),
                "take_profit": round(take_profit, 2),
                "risk_reward_ratio": round(rr_ratio, 2),
            },
            
            # Section 3: Technical Indicators
            "indicators": {
                "rsi": {
                    "value": round(rsi_val, 1),
                    "interpretation": _rsi_interpretation(rsi_val),
                    "status": "Aşırı Alım" if rsi_val > 70 else "Aşırı Satım" if rsi_val < 30 else "Nötr"
                },
                "macd": {
                    "macd_line": round(macd_val, 2),
                    "signal_line": round(signal_val, 2),
                    "histogram": round(hist_val, 2),
                    "interpretation": _macd_interpretation(macd_val, signal_val, hist_val)
                },
                "moving_averages": {
                    "sma_20": round(sma_20, 2),
                    "sma_50": round(sma_50, 2),
                    "sma_200": round(sma_200, 2),
                    "price_vs_sma20": "Üstünde" if close > sma_20 else "Altında",
                    "price_vs_sma50": "Üstünde" if close > sma_50 else "Altında",
                    "price_vs_sma200": "Üstünde" if close > sma_200 else "Altında",
                    "golden_cross": sma_50 > sma_200,
                },
                "volatility": {
                    "atr": round(atr_val, 2),
                    "atr_percent": round((atr_val / close) * 100, 2) if close > 0 else 0,
                    "bollinger_upper": round(last_row.get('BBU_20_2.0', close * 1.04), 2),
                    "bollinger_lower": round(last_row.get('BBL_20_2.0', close * 0.96), 2),
                },
                "volume": {
                    "obv_trend": "Pozitif" if last_row.get('OBV', 0) > 0 else "Negatif",
                    "mfi": round(last_row.get('MFI_14', 50), 1),
                }
            },
            
            # Section 4: Scenarios
            "scenarios": {
                "positive": {
                    "name": "Pozitif Senaryo",
                    "conditions": [
                        f"Direnç {_fmt_price(nearest_resistance)} seviyesinin hacim eşliğinde kırılması",
                        "RSI'nin 50 üstünde kalıcı olması",
                        "MACD histogramının pozitif bölgeye geçmesi"
                    ],
                    "target": f"Hedef: {_fmt_price(nearest_resistance * 1.05)} - {_fmt_price(nearest_resistance * 1.10)}",
                    "probability": "Yüksek" if score_data['score'] > 60 else "Orta"
                },
                "neutral": {
                    "name": "Nötr / Konsolidasyon Senaryosu",
                    "conditions": [
                        f"Fiyatın {_fmt_price(nearest_support)} - {_fmt_price(nearest_resistance)} aralığında hareketi",
                        "Momentum göstergelerinin nötr bölgede kalması",
                        "Hacim düşüşü ile birlikte yatay hareket"
                    ],
                    "strategy": "Teyit beklenmeli, ani pozisyon değişikliğinden kaçınılmalı",
                    "probability": "Orta"
                },
                "negative": {
                    "name": "Negatif Senaryo",
                    "conditions": [
                        f"Destek {_fmt_price(nearest_support)} seviyesinin kırılması",
                        "RSI'nin 40 altına gerilemesi",
                        "Hacim artışıyla satış baskısının güçlenmesi"
                    ],
                    "risk": f"Risk: {_fmt_price(close * 0.90)} - {_fmt_price(close * 0.85)} seviyelerine kadar geri çekilme",
                    "probability": "Düşük" if score_data['score'] > 50 else "Orta"
                }
            },
            
            # Section 5: Volume Profile
            "volume_profile": {
                "poc": volume_profile.get('poc', close),
                "value_area_high": volume_profile.get('value_area_high', close * 1.02),
                "value_area_low": volume_profile.get('value_area_low', close * 0.98),
                "interpretation": (
                    f"Hacim profili analizi {_fmt_price(volume_profile.get('poc', close))} seviyesinde "
                    f"en yüksek yoğunluğu göstermektedir. Bu seviye fiyat için önemli bir çekim merkezi konumundadır."
                ) if 'error' not in volume_profile else "Hacim profili verisi yeterli değil"
            },
            
            # Section 6: Risk Assessment
            "risk_assessment": {
                "technical_risks": [
                    "Destek seviyesi kırılımı",
                    "Momentum göstergelerinde bozulma",
                    "Hacim düşüşü ile likidite azalması"
                ],
                "technical_opportunities": [
                    "Aşırı satım bölgelerinden tepki potansiyeli",
                    "Pozitif uyumsuzluk oluşumu",
                    "Formasyon tamamlanması"
                ],
                "beta": None,  # Will be calculated if available
                "market_breadth": None,
            },
            
            # Section 7: Watchlist
            "watchlist": {
                "daily": [
                    "Fiyat / kritik destek-direnç seviyeleri",
                    "İşlem hacmi değişimi",
                    "RSI ve MACD yön takibi",
                    "Formasyon gelişimi"
                ],
                "weekly": [
                    "Haftalık kapanış seviyesi",
                    "Hareketli ortalamalar yönü",
                    "Genel piyasa trendi"
                ]
            },
            
            # Section 8: Disclaimer
            "disclaimer": (
                "Bu rapor teknik analiz verilerine dayalı olarak hazırlanmış olup yatırım tavsiyesi niteliği taşımamaktadır. "
                "Yatırım kararları yalnızca bu rapora dayanarak verilmemeli, temel analiz, şirket performingı ve "
                "piyasa koşulları gibi diğer faktörler de göz önünde bulundurulmalıdır."
            )
        }
        
        return report
        
    except Exception as e:
        logger.error(f"CEO report generation error for {ticker}: {e}", exc_info=True)
        return {"error": str(e)}
