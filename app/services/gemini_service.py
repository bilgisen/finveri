import logging
import google.generativeai as genai
from typing import Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not found in settings. Gemini features will be disabled.")

async def generate_pro_analysis(ticker: str, ta_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Generates a professional financial analysis using Gemini AI.
    """
    if not settings.GEMINI_API_KEY:
        return None

    try:
        # Construct the prompt
        prompt = f"""
Sen deneyimli bir finansal analistsin. Aşağıdaki teknik analiz verilerini kullanarak {ticker} için profesyonel, objektif ve yatırımcı dostu bir Türkçe analiz raporu hazırla.

### Teknik Veriler:
- Fiyat: {ta_data.get('close')} TL
- Teknik Skor: {ta_data.get('score')}/100
- Trend: {ta_data.get('trend')} ({ta_data.get('adx_strength')})
- RSI: {ta_data.get('rsi', {}).get('value')}
- Aktif Sinyaller: {', '.join(ta_data.get('signals', []))}
- Mum Formasyonları: {', '.join(ta_data.get('candlestick_patterns', []))}
- Destek: {ta_data.get('support_resistance', {}).get('support')} TL
- Direnç: {ta_data.get('support_resistance', {}).get('resistance')} TL
- Stop-Loss: {ta_data.get('atr_stop_loss')} TL

### Talimatlar:
1. Analiz metni tek bir paragraf olsun, ancak yoğun bilgi içersin.
2. Piyasadaki mevcut arz-talep dengesini ve momentumun gücünü yorumla.
3. Yatırımcılar için kritik seviyeleri (destek/direnç) ve risk yönetimini (stop-loss) vurgula.
4. Profesyonel bir dil kullan (örn: "tepki alımı beklenen bölge", "ivme kaybı", "konsolidasyon").
5. Raporun sonunda yatırımcıların chatbot'a sorabileceği 3-4 adet keskin ve stratejik soru önerisi ekle.

Yanıtını şu JSON formatında ver:
{{
  "analysis": "Analiz metni buraya",
  "questions": ["Soru 1", "Soru 2", "Soru 3"]
}}
"""

        model = genai.GenerativeModel('gemini-2.5-flash')
        # We use sync generate_content in a thread if needed, but for simplicity:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                candidate_count=1,
                temperature=0.7,
                response_mime_type="application/json"
            )
        )

        import json
        result = json.loads(response.text)
        return result

    except Exception as e:
        logger.error(f"Gemini analysis generation failed for {ticker}: {e}")
        return None
