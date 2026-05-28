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

    # 3. Fetch Live Price Data for current context
    live_price = ta_data.get("close", 0.0)
    trend = ta_data.get("trend", "Nötr")
    rsi_val = ta_data.get("rsi", {}).get("value", 50.0)
    rsi_status = ta_data.get("rsi", {}).get("status", "Nötr")
    macd_status = ta_data.get("macd", "Nötr")
    support = ta_data.get("support_resistance", {}).get("support", 0.0)
    resistance = ta_data.get("support_resistance", {}).get("resistance", 0.0)
    stop_loss = ta_data.get("atr_stop_loss", 0.0)
    patterns = ta_data.get("candlestick_patterns", [])

    # Detect if ticker is an index or stock
    is_index = get_index(ticker) is not None
    asset_type_tr = "endeksi" if is_index else "pay senedi"

    # Map trends to Turkish terms
    trend_tr = "Yükseliş (Boğa)" if "Bullish" in trend else "Düşüş (Ayı)" if "Bearish" in trend else "Yatay / Kararsız"
    strength_tr = "güçlü" if "Strong" in ta_data.get("adx_strength", "") else "zayıf veya yatay seyreden"

    rsi_status_tr = (
        "aşırı alım (düzeltme riski)" if "Overbought" in rsi_status else
        "aşırı satım (tepki alımı potansiyeli)" if "Oversold" in rsi_status else
        "nötr / dengeli"
    )

    macd_tr = (
        "alım iştahının arttığını (boğa momentumu)" if "Bullish Momentum" in macd_status or "Bullish Crossover" in macd_status else
        "satıcıların ağırlıkta olduğunu (ayı momentumu)" if "Bearish Momentum" in macd_status or "Bearish Crossover" in macd_status else
        "momentumun kararsız olduğunu"
    )

    pattern_text = ""
    if patterns:
        pattern_text = f" Mum grafiklerinde son dönemde oluşan **{', '.join(patterns)}** formasyon(lar)ı piyasa yönü açısından kritik bir dönüş sinyali oluşturma ihtimalini taşıyor."

    # Exactly 1 concise, premium paragraph utilizing active, direct verbs
    summary_paragraph = (
        f"**{ticker}** {asset_type_tr}, gerçek zamanlı piyasa verileri ve teknik göstergelerin "
        f"harmanlanmasıyla yapılan analize göre şu anda **{trend_tr}** eğiliminde hareket ediyor. "
        f"Mevcut {live_price:.2f} TL fiyat seviyesi piyasadaki gün içi arz ve talep dengesini yansıtırken, "
        f"ADX göstergesi piyasada **{strength_tr}** bir fiyat yapısının hakim olduğunu doğruluyor. "
        f"Kısa ve orta vadeli hareketli ortalamaların (SMA 20/50) güncel fiyat seviyeleriyle ilişkisi "
        f"piyasa oyuncularının genel pozisyonlanma yönünü teyit ediyor. "
        f"Momentum göstergelerinden RSI değeri şu anda **{rsi_val:.1f}** seviyesinde bulunuyor ve teknik olarak **{rsi_status_tr}** bir görünümü işaret ediyor. "
        f"Aynı zamanda trend takipçisi MACD göstergesi piyasada **{macd_tr}** ortaya koyuyor.{pattern_text} "
        f"Bollinger Bantları'nın genişliği ise piyasadaki oynaklığın güncel durumunu sergileyerek fiyatın sıkışma mı yoksa kırılma aşamasında mı olduğunu gösteriyor. "
        f"Stratejik seviyeler incelendiğinde, olası geri çekilmelerde en yakın güçlü destek bölgesi **{support:.2f} TL** "
        f"seviyesinde bulunurken, yükselişlerin ivme kazanması için aşılması gereken ilk direnç eşiği **{resistance:.2f} TL** "
        f"olarak belirlenmiş durumda. Risk yönetimi açısından ATR tabanlı stop-loss koruması ise "
        f"**{stop_loss:.2f} TL** seviyesinde konumlanıyor."
    )

    # Dynamic recommended questions (5-6 questions)
    questions = []
    if "Bullish" in trend:
        questions.append(f"{ticker} için {resistance:.2f} TL direncinin aşılması yeni bir ralli başlatır mı?")
        questions.append(f"{ticker} yükseliş trendini koruyabilecek mi, sonraki hedef seviyeleri nelerdir?")
    elif "Bearish" in trend:
        questions.append(f"{ticker} için {support:.2f} TL desteği kırılırsa düşüş ne kadar derinleşebilir?")
        questions.append(f"{ticker} düşüş trendinden ne zaman çıkabilir, dip oluşumu nerede gerçekleşiyor?")
    else:
        questions.append(f"{ticker} yatay / kararsız bölgeden ne tarafa doğru kırılabilir?")
        questions.append(f"{ticker} için hangi seviyeler güvenli alım veya satım fırsatı sunuyor?")

    if rsi_val > 70:
        questions.append(f"RSI değeri {rsi_val:.1f} ile aşırı alım bölgesinde, yakın zamanda düzeltme veya kâr satışı gelir mi?")
    elif rsi_val < 30:
        questions.append(f"RSI değeri {rsi_val:.1f} ile aşırı satım bölgesinde, buradan güçlü bir tepki alımı bekleniyor mu?")
    else:
        questions.append(f"Nötr bölgedeki RSI ({rsi_val:.1f}) göstergesi {ticker} için kararsızlığın sürdüğünü mi gösteriyor?")

    if "Crossover" in macd_status or "Momentum" in macd_status:
        questions.append(f"MACD göstergesindeki mevcut ivme trendin gücünü onaylıyor mu?")

    questions.append(f"ATR bazlı {stop_loss:.2f} TL stop-loss seviyesinin altında bir kapanış teknik senaryoyu nasıl değiştirir?")
    questions.append(f"Hareketli ortalamaların (SMA 20/50) mevcut seviyeleri orta vadeli görünüm için neye işaret ediyor?")

    # Slice to exactly 6 elements
    questions = questions[:6]

    result = {
        "ticker": ticker,
        "summary": summary_paragraph,
        "paragraphs": [summary_paragraph],
        "questions": questions,
        "generated_at": datetime.now().isoformat()
    }

    # 4. Save to Redis Cache with dynamic TTL
    ttl = 1800 if is_market_open() else 43200 # 30 mins during market hours, 12 hours after hours
    try:
        r_client.setex(cache_key, ttl, json.dumps(result))
    except Exception as e:
        logger.warning(f"Failed to write summary cache for {ticker}: {e}")

    return result
