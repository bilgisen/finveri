"""
Summary Generator — borsa ve endeks detay sayfaları için dinamik Türkçe analiz metinleri üretir.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any

from app.core.redis_client import get_redis
from app.services.ta_engine import generate_llm_summary
from app.core.index_store import get_index

logger = logging.getLogger(__name__)

CACHE_KEY_SUMMARY = "summary:text:{ticker}"

def is_market_open() -> bool:
    """Borsa İstanbul işlem saatleri içinde mi? (Hafta içi 09:00 - 18:00)"""
    now = datetime.now()
    if now.weekday() >= 5: # Cumartesi, Pazar kapalı
        return False
    # 09:00 - 18:00 arası açık kabul edilir
    return 9 <= now.hour < 18

async def generate_header_summary(ticker: str) -> Dict[str, Any]:
    """
    Şirket veya endeks için 1 paragraflık dinamik analiz raporu ve 5-6 önerilen soru döner.
    Hafta içi borsa açıkken 30 dk cache'lenir, borsa kapalıyken 12 saat cache'lenir.
    """
    ticker = ticker.upper()
    r_client = get_redis()
    cache_key = CACHE_KEY_SUMMARY.format(ticker=ticker)

    # 1. Check Redis Cache
    try:
        cached = r_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Failed to read summary cache for {ticker}: {e}")

    # 2. Fetch TA Data via Real-time Indicator Overlay
    ta_data = await generate_llm_summary(ticker)
    if "error" in ta_data:
        return {"error": f"Analiz verisi alınamadı: {ta_data['error']}"}

    # 3. Try Gemini Pro Analysis
    from app.services.gemini_service import generate_pro_analysis
    gemini_result = await generate_pro_analysis(ticker, ta_data)
    
    if gemini_result:
        result = {
            "ticker": ticker,
            "summary": gemini_result["analysis"],
            "paragraphs": [gemini_result["analysis"]],
            "questions": gemini_result["questions"],
            "generated_at": datetime.now().isoformat(),
            "source": "gemini"
        }
    else:
        # Fallback to Template-based summary
        result = await _generate_template_summary(ticker, ta_data)
        result["source"] = "template"

    # 4. Save to Redis Cache with dynamic TTL
    ttl = 1800 if is_market_open() else 43200 # 30 mins during market hours, 12 hours after hours
    try:
        r_client.setex(cache_key, ttl, json.dumps(result))
    except Exception as e:
        logger.warning(f"Failed to write summary cache for {ticker}: {e}")

    return result

async def _generate_template_summary(ticker: str, ta_data: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback template-based summary generation."""
    live_price = ta_data.get("close", 0.0)
    trend = ta_data.get("trend", "Nötr")
    rsi_val = ta_data.get("rsi", {}).get("value", 50.0)
    support = ta_data.get("support_resistance", {}).get("support", 0.0)
    resistance = ta_data.get("support_resistance", {}).get("resistance", 0.0)
    stop_loss = ta_data.get("atr_stop_loss", 0.0)
    patterns = ta_data.get("candlestick_patterns", [])
    score = ta_data.get("score", 50)
    signals = ta_data.get("signals", [])

    # Map trends to Turkish terms
    trend_tr = "Yükseliş (Boğa)" if "Bullish" in trend else "Düşüş (Ayı)" if "Bearish" in trend else "Yatay / Kararsız"
    
    pattern_text = f" Mum formasyonlarında **{', '.join(patterns)}** görülüyor." if patterns else ""

    # Determine unit based on ticker type (Index starts with 'X')
    unit = "puan" if ticker.upper().startswith("X") else "TL"

    summary_paragraph = (
        f"**{ticker}** şu anda **{trend_tr}** eğiliminde (Teknik Skor: {score}/100). "
        f"Mevcut {live_price:.2f} {unit} seviyesi üzerinden yapılan analizde, RSI değeri {rsi_val:.1f} olarak ölçüldü. "
        f"Aktif sinyaller arasında {', '.join(signals[:3])} öne çıkıyor.{pattern_text} "
        f"Stratejik olarak **{support:.2f} {unit}** destek, **{resistance:.2f} {unit}** direnç konumunda. "
        f"Risk yönetimi için stop-loss seviyesi **{stop_loss:.2f} {unit}** olarak takip edilebilir."
    )

    questions = [
        f"{ticker} için {resistance:.2f} {unit} direnci ne zaman test edilebilir?",
        f"{ticker} teknik skoru {score}/100 ile alım fırsatı sunuyor mu?" if unit == "TL" else f"{ticker} teknik skoru {score}/100 ile endeksin yönünü teyit ediyor mu?",
        f"Mevcut stop-loss ({stop_loss:.2f} {unit}) seviyesi güvenli mi?"
    ]

    return {
        "ticker": ticker,
        "summary": summary_paragraph,
        "paragraphs": [summary_paragraph],
        "questions": questions,
        "generated_at": datetime.now().isoformat()
    }
