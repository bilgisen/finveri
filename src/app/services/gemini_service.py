"""
Gemini AI analysis via HTTP API (SDK not available in Workers).
"""
import json
import logging
from typing import Dict, Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


async def generate_pro_analysis(ticker: str, ta_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not settings.GEMINI_API_KEY:
        return None

    prompt = f"""
Sen deneyimli bir finansal analistsin. Asagidaki teknik analiz verilerini kullanarak {ticker} icin profesyonel, objektif ve yatirimci dostu bir Turkce analiz raporu hazirla.

### Teknik Veriler:
- Fiyat: {ta_data.get('close')} TL
- Teknik Skor: {ta_data.get('score')}/100
- Trend: {ta_data.get('trend')}
- RSI: {ta_data.get('rsi', {}).get('value')}
- Aktif Sinyaller: {', '.join(ta_data.get('signals', []))}
- Destek: {ta_data.get('support_resistance', {}).get('support')} TL
- Direnc: {ta_data.get('support_resistance', {}).get('resistance')} TL
- Stop-Loss: {ta_data.get('atr_stop_loss')} TL

### Talimatlar:
1. Analiz metni tek bir paragraf olsun.
2. Piyasadaki arz-talep dengesini ve momentumun gucunu yorumla.
3. Kritik seviyeleri ve risk yonetimini vurgula.
4. Profesyonel bir dil kullan.
5. Raporun sonunda chatbot'a sorulabilecek 3-4 stratejik soru ekle.

Yanitini JSON formatinda ver:
{{"analysis": "...", "questions": ["...", "..."]}}
"""

    model = settings.GEMINI_MODEL
    url = f"{_GEMINI_API_BASE}/{model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{url}?key={settings.GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt.strip()}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "responseMimeType": "application/json",
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
            return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini analysis failed for {ticker}: {e}")
        return None
