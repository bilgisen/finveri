# Advanced Technical Analysis - Implementation Guide

## 🎯 Neler Eklendi?

### 1. **Volume Profile Analysis** (`advanced_ta.py`)
```python
calculate_volume_profile(df, num_bins=50)
```
**Dönen Değerler:**
- `poc`: Point of Control (en yüksek hacim seviyesi)
- `value_area_high`: %70 hacmin üst sınırı
- `value_area_low`: %70 hacmin alt sınırı
- `profile_bins`: Fiyat seviyelerine göre hacim dağılımı

**Kullanım Amacı:** Kurumsal alıcı/satıcıların yoğunlaştığı seviyeleri tespit eder.

---

### 2. **Market Regime Detection** (`advanced_ta.py`)
```python
detect_market_regime(df)
```
**Dönen Değerler:**
- `regime`: Strong Trend / Weak Trend / Range Bound / Choppy
- `trend_direction`: Bullish / Bearish / Neutral
- `volatility_regime`: Normal / High Volatility / Low Volatility
- `adx`: Trend gücü (ADX)
- `efficiency_ratio`: Trend kalitesi (Kaufman ER)
- `recommended_strategy`: Önerilen strateji

**Kullanım Amacı:** Piyasa hangi rejimde → hangi strateji kullanılmalı?

---

### 3. **Liquidity Voids Detection** (`advanced_ta.py`)
```python
detect_liquidity_voids(df, threshold=2.5)
```
**Dönen Değerler:**
- `gap_start`, `gap_end`: Gap başlangıç ve bitiş fiyatları
- `direction`: up / down
- `gap_size`: Gap büyüklüğü
- `bars_ago`: Kaç bar önce oluştu

**Kullanım Amacı:** Doldurulmamış fiyat boşlukları (fair value gaps) - fiyat mıknatısları.

---

### 4. **Enhanced Support/Resistance Zones** (`advanced_ta.py`)
```python
calculate_support_resistance_zones(df, lookback=60)
```
**Kombinasyonu:**
- Swing highs/lows
- Volume Profile (POC, VAH, VAL)
- Bollinger Bands
- Psikolojik seviyeler (yuvarlak sayılar)

**Dönen Değerler:**
- `resistance_zones`: Direnç seviyeleri (fiyat, tip, güç skoru)
- `support_zones`: Destek seviyeleri
- `nearest_resistance`, `nearest_support`: En yakın seviyeler

---

### 5. **Enhanced Technical Score** (`advanced_ta.py`)
```python
enhanced_technical_score(df, regime)
```
**Yenilikler:**
- **Regime-aware weighting**: Piyasa rejmine göre ağırlıklar değişir
  - Strong Trend: Trend göstergeleri 1.5x ağırlık
  - Range Bound: Momentum göstergeleri 1.4x ağırlık
- **Signal quality markings**: ✓ (bullish), ✗ (bearish), ⊙ (neutral)
- **Score components**: Trend, Momentum, Volume alt bileşenleri ayrı

---

## 🚀 Yeni API Endpoints

### `/api/v1/ta/advanced/regime/{ticker}`
Market rejimi ve strateji önerisi döner.

**Örnek Response:**
```json
{
  "ticker": "THYAO",
  "regime": "Strong Trend",
  "trend_direction": "Bullish",
  "volatility_regime": "Normal",
  "adx": 32.5,
  "efficiency_ratio": 0.68,
  "confidence": 90,
  "recommended_strategy": "Trend Following: Use MA crossovers, Supertrend, breakout strategies",
  "interpretation": "Strong Trend piyasa rejimi (Bullish yönlü), Normal volatilite ile karakterize ediliyor."
}
```

---

### `/api/v1/ta/advanced/volume-profile/{ticker}`
Volume Profile analizi döner.

**Örnek Response:**
```json
{
  "ticker": "ASELS",
  "poc": 78.45,
  "poc_volume": 15230000,
  "value_area_high": 82.30,
  "value_area_low": 74.20,
  "total_volume": 45600000,
  "value_area_volume_pct": 70
}
```

---

### `/api/v1/ta/advanced/liquidity-voids/{ticker}`
Doldurulmamış gap'leri döner.

**Örnek Response:**
```json
{
  "ticker": "EREGL",
  "voids_found": 3,
  "liquidity_voids": [
    {
      "date": "2024-01-15",
      "gap_start": 45.20,
      "gap_end": 47.80,
      "gap_size": 2.60,
      "gap_pct": 5.75,
      "direction": "up",
      "bars_ago": 12
    }
  ]
}
```

---

### `/api/v1/ta/advanced/sr-zones/{ticker}`
Multi-method destek/direnç seviyeleri döner.

**Örnek Response:**
```json
{
  "ticker": "THYAO",
  "current_price": 385.50,
  "resistance_zones": [
    {"price": 395.00, "type": "Volume VAH", "strength": 90},
    {"price": 400.00, "type": "Psychological", "strength": 60}
  ],
  "support_zones": [
    {"price": 378.20, "type": "Volume POC", "strength": 95},
    {"price": 375.00, "type": "Swing Low", "strength": 85}
  ],
  "nearest_resistance": {"price": 395.00, "type": "Volume VAH", "strength": 90},
  "nearest_support": {"price": 378.20, "type": "Volume POC", "strength": 95}
}
```

---

### `/api/v1/ta/advanced/full-context/{ticker}` ⭐ **CHATBOT İÇİN**
Tüm advanced analizleri tek seferde döner + chatbot için özet metin.

**Örnek Response:**
```json
{
  "ticker": "THYAO",
  "current_price": 385.50,
  "market_regime": { ... },
  "volume_profile": { ... },
  "liquidity_voids": [ ... ],
  "support_resistance_zones": { ... },
  "chatbot_summary": "THYAO Advanced Analysis Summary:\n\nMARKET REGIME: Strong Trend (Bullish)\nStrategy: Trend Following: Use MA crossovers, Supertrend, breakout strategies\n\nKEY LEVELS:\n• Volume POC (strongest level): 378.20 TL\n• Value Area: 375.00 - 395.00 TL\n• Next Support: 378.20 TL (Volume POC)\n• Next Resistance: 395.00 TL (Volume VAH)"
}
```

---

## 📊 Mevcut `/api/v1/ta/summary/{ticker}` Endpoint'ine Eklenenler

**Yeni Alanlar:**
```json
{
  "market_regime": {
    "regime": "Strong Trend",
    "trend_direction": "Bullish",
    "volatility_regime": "Normal",
    "adx": 32.5,
    "recommended_strategy": "..."
  },
  "volume_profile": {
    "poc": 378.20,
    "value_area_high": 395.00,
    "value_area_low": 375.00
  },
  "liquidity_voids": [ ... ],
  "support_resistance_zones": {
    "resistance_zones": [ ... ],
    "support_zones": [ ... ]
  },
  "score_components": {
    "trend": 45,
    "momentum": 18,
    "volume": 7
  },
  "llm_summary_prompt": "=== THYAO TEKNİK ANALİZ RAPORU ===\n\n📊 GENEL GÖRÜNÜM:\nFiyat: 385.50 TL | Teknik Skor: 70/100 (High güven)\n..."
}
```

---

## 🤖 Chatbot Entegrasyonu İçin Kullanım

### Senaryo 1: Kullanıcı "THYAO'yu analiz et" derse

**Backend (Hono):**
```javascript
const response = await fetch('https://finveri-api/api/v1/ta/summary/THYAO');
const data = await response.json();

// Context zenginleştirme
const context = {
  price: data.close,
  score: data.score,
  trend: data.trend,
  regime: data.market_regime.regime,
  strategy: data.market_regime.recommended_strategy,
  key_levels: {
    support: data.support_resistance_zones.nearest_support,
    resistance: data.support_resistance_zones.nearest_resistance,
    poc: data.volume_profile.poc
  },
  signals: data.signals.slice(0, 5),
  summary: data.llm_summary_prompt
};

// LLM'e gönder
const llmPrompt = `
User asked about THYAO stock. Here's the technical analysis context:

${context.summary}

User question: "THYAO'yu analiz et"

Provide a professional Turkish analysis focusing on:
1. Current market regime and what it means
2. Key support/resistance levels
3. Entry/exit strategy based on ${context.strategy}
4. Risk management with stop-loss at ${context.key_levels.support.price}
`;
```

---

### Senaryo 2: Kullanıcı "Hangi hisseler alım fırsatı?" derse

**Backend:**
```javascript
// Birden fazla hisse için batch analiz
const tickers = ['THYAO', 'ASELS', 'EREGL', 'SASA', 'TUPRS'];
const analyses = await Promise.all(
  tickers.map(t => fetch(`/api/v1/ta/advanced/full-context/${t}`))
);

// Filtreleme: Strong Trend + Bullish + Score > 65
const opportunities = analyses
  .filter(a => 
    a.market_regime.regime === 'Strong Trend' &&
    a.market_regime.trend_direction === 'Bullish' &&
    a.score > 65
  )
  .sort((a, b) => b.score - a.score);

// LLM'e özet gönder
const context = opportunities.map(o => `
${o.ticker}: Score ${o.score}/100
Regime: ${o.market_regime.regime}
Entry: ${o.current_price} TL
Target: ${o.support_resistance_zones.nearest_resistance.price} TL
`).join('\n');
```

---

## 🧪 Test Etme

```bash
# Local development
cd c:\Users\ASUS\hp\finveri
python -m uvicorn app.main:app --reload --port 8000

# Test endpoints
curl http://localhost:8000/api/v1/ta/advanced/regime/THYAO
curl http://localhost:8000/api/v1/ta/advanced/volume-profile/ASELS
curl http://localhost:8000/api/v1/ta/advanced/full-context/EREGL

# Test enhanced summary
curl http://localhost:8000/api/v1/ta/summary/THYAO
```

---

## 📈 Performans Optimizasyonu

### Redis Caching
Mevcut yapıda zaten var, ek bir şey yapmanıza gerek yok:
- `/api/v1/ta/summary/{ticker}` → 24 saat cache
- Advanced endpointler → Live calculation (ancak hafif)

### Batch Calculation
`app/worker/historical.py` içinde `batch_calculate_all_ta()` fonksiyonu var.
Her gece 00:05'te tüm hisseler için TA hesaplanıp Redis'e yazılıyor.

---

## 🎨 Frontend Entegrasyonu Önerisi

### Simple Card için:
```typescript
// app/components/TACard.tsx
interface TACardProps {
  ticker: string;
}

export function TACard({ ticker }: TACardProps) {
  const { data } = useSWR(`/api/v1/ta/summary/${ticker}`);
  
  return (
    <Card>
      <CardHeader>
        <Badge variant={data.trend === 'Bullish' ? 'success' : 'destructive'}>
          {data.trend}
        </Badge>
        <Text>{data.score}/100</Text>
      </CardHeader>
      
      <CardBody>
        <Text>Rejim: {data.market_regime.regime}</Text>
        <Text>Destek: {data.support_resistance_zones.nearest_support.price} TL</Text>
        <Text>Direnç: {data.support_resistance_zones.nearest_resistance.price} TL</Text>
        
        <Accordion>
          <AccordionItem title="Detaylı Analiz">
            {data.signals.map(s => <Badge>{s}</Badge>)}
          </AccordionItem>
        </Accordion>
      </CardBody>
    </Card>
  );
}
```

### Chatbot Context Builder:
```typescript
// app/lib/chatbotContext.ts
export async function buildTAContext(ticker: string) {
  const response = await fetch(`/api/v1/ta/advanced/full-context/${ticker}`);
  const data = await response.json();
  
  return {
    shortContext: data.chatbot_summary, // Özet text
    fullContext: data.llm_summary_prompt, // Detaylı prompt
    structuredData: data // JSON olarak
  };
}
```

---

## ✅ Sonraki Adımlar (Öncelik Sırasına Göre)

### ✅ Tamamlandı
1. Volume Profile & POC ✓
2. Market Regime Detection ✓
3. Enhanced Scoring System ✓
4. Advanced API Endpoints ✓

### 🟡 Orta Öncelik (2-4 hafta)
5. **Harmonic Pattern Recognition** (Gartley, Butterfly)
6. **Risk-Adjusted Metrics** (Sharpe, Sortino, Calmar)
7. **Kelly Criterion Position Sizing**

### 🟢 Düşük Öncelik (1-2 ay)
8. **ML Ensemble Predictions** (Random Forest + Gradient Boosting)
9. **Mean Reversion Testing** (ADF test, half-life)
10. **Batch Processing Optimization** (Multiprocessing)

---

## 🐛 Debugging

### Log seviyelerini artır:
```python
# app/main.py
logging.basicConfig(
    level=logging.DEBUG,  # INFO → DEBUG
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
```

### Redis cache kontrolü:
```python
from app.core.redis_client import get_redis
r = get_redis()
keys = r.keys("ta_data:*")
print(f"Cached tickers: {len(keys)}")
```

---

## 📞 Destek

Sorularınız için:
- `/api/v1/ta/advanced/full-context/{ticker}` endpoint'ini inceleyin
- `app/services/advanced_ta.py` kaynak kodunu okuyun
- Test: `test_advanced_ta.py`

**İyi çalışmalar! 🚀**
