# Hono Orchestrator — TA API Entegrasyon Kılavuzu

> **Hedef:** Hono orkestratörün chatbot context, AI rapor ve screening işlemleri için TA API'yi doğru ve verimli tüketmesi.

---

## 1. Mimari İletişim

```
Hono Orchestrator
    │
    ├── Chatbot (kullanıcı soruları)
    │     └── GET /context/{kod}?query_type=xxx
    │
    ├── AI Rapor (derin analiz üretimi)
    │     └── GET /full/{kod}
    │
    ├── Screening / Tarama
    │     └── POST /batch
    │
    └── Sektör/Endeks sayfaları
          └── GET /sector/{s}/summary
          └── GET /index/{k}/breadth
```

**Base URL:** `https://tapi.paraanaliz.workers.dev/api/v1/ta`

---

## 2. Endpoint Referansı

### 2.1 Chatbot Context — `/context/{kod}`

**Kullanım Senaryosu:** Kullanıcı bir hisse hakkında soru sorduğunda, Hono bu endpoint'ten aldığı yapılandırılmış veriyi LLM prompt'una inject eder.

**İstek:**
```
GET /api/v1/ta/context/THYAO?query_type=general
```

| Param | Değerler | Varsayılan | Açıklama |
|-------|----------|------------|----------|
| `query_type` | `general`, `entry`, `risk`, `comparison` | `general` | Hangi alan setinin döneceğini belirler |

**query_type davranışı:**

| query_type | Dönen Alanlar | Ne zaman kullanılır |
|---|---|---|
| `general` | current_price, trend, regime, key_levels, active_signals, scenarios, risk_metrics, summary_text | Genel sorular ("THYAO'yu analiz et") |
| `entry` | + full scenarios + risk_metrics | Giriş/pozisyon soruları ("Alınır mı?") |
| `risk` | + risk_metrics + volume_metrics | Risk soruları ("Stop nereye?") |
| `comparison` | + mtf_alignment + relative_strength | Karşılaştırma soruları ("Endekse göre durumu nedir?") |

**Response yapısı (general):**
```json
{
  "ticker": "THYAO",
  "current_price": 344.50,
  "trend": "Bullish",
  "regime": {
    "regime": "Strong Trend",
    "trend_direction": "Bullish",
    "volatility_regime": "Normal",
    "adx": 32.5,
    "recommended_strategy": "Trend Following: Use MA crossovers, Supertrend, breakout strategies"
  },
  "key_levels": {
    "nearest_support": { "price": 335.20, "type": "Volume POC", "strength": 95 },
    "nearest_resistance": { "price": 355.00, "type": "Volume VAH", "strength": 90 },
    "support_zones": [ ... ],
    "resistance_zones": [ ... ]
  },
  "active_signals": [
    { "label": "Above SMA 200 (Long-term Bullish)", "direction": "Bullish", "source": "composite_score", "freshness": "Established" }
  ],
  "scenarios": [
    {
      "name": "Bullish",
      "direction": "Bullish",
      "trigger_price": 355.00,
      "target_price": 372.75,
      "invalidation_price": 335.20,
      "supporting_signal_count": 7
    }
  ],
  "risk_metrics": {
    "atr_based_stop_loss": 332.40,
    "volatility_classification": "Normal",
    "atr_pct": 1.82
  },
  "summary_text": "THYAO: 344.50 TL | Skor: 72/100 | Trend: Bullish | Rejim: Strong Trend (Bullish) | Sinyaller: Above SMA 200..., Golden Cross..., Supertrend Bullish..."
}
```

**Chatbot Prompt Injection — Örnek:**

```
Kullanıcı sorusu: "THYAO alınır mı?"

Context:
- Fiyat: 344.50 TL
- Trend: Bullish (Günlük), Bullish (Haftalık)
- Rejim: Strong Trend — Bullish yönlü, Normal volatilite
- Strateji: Trend Following
- Destek (güçlü): 335.20 TL (Volume POC, güven: 95)
- Direnç: 355.00 TL (Volume VAH, güven: 90)
- Skor: 72/100 (Medium güven)
- Stop-Loss: 332.40 TL (ATR bazlı)
- Alış senaryosu: 355.00 TL üstünde aktifleşir, hedef 372.75 TL
- Sinyaller: 7 bull destekli, bearish sinyal yok

Yanıtını Türkçe ver, profesyonel trading analizi formatında.
```

---

### 2.2 AI Rapor — `/full/{kod}`

**Kullanım Senaryosu:** Abone sayfasındaki "Derin Teknik Analiz Raporu" butonuna tıklandığında, Hono bu endpoint'ten full veriyi alır, AI modeline prompt olarak verir.

**İstek:**
```
GET /api/v1/ta/full/THYAO
```

**Cache TTL:** 15 dk (piyasa açık) / 6 saat (piyasa kapalı)

**Response — 60+ field içerir, öne çıkanlar:**

```json
{
  "ticker": "THYAO",
  "price": 344.50,
  "trend": "Bullish",
  "weekly_trend": "Bullish",
  "indicators": {
    "rsi": 62.3,
    "macd": { "value": 2.45, "signal": 1.80, "histogram": 0.65 },
    "sma": { "sma_20": 338.00, "sma_50": 325.00, "sma_200": 290.00 },
    "bbands": { "upper": 358.00, "middle": 338.00, "lower": 318.00 },
    "atr": 6.27,
    "atr_pct": 1.82,
    "supertrend": 330.00,
    "supertrend_direction": "up"
  },
  "golden_cross": {
    "has_golden_cross": true,
    "bars_since_cross": 12,
    "sma_20_minus_sma_50": 13.00
  },
  "mtf_alignment": {
    "alignment_score": 80,
    "alignment_label": "Bullish Alignment"
  },
  "patterns": {
    "candlestick_patterns": [
      { "name": "Bullish Engulfing", "direction": "Bullish", "reliability": 75, "bars_ago": 0 }
    ],
    "chart_patterns": [],
    "total_active": 1
  },
  "divergences": {
    "rsi": { "bullish": false, "bearish": false },
    "macd": { "bullish": false, "bearish": false },
    "overall_confidence": "Low",
    "divergence_count": 0
  },
  "scenarios": [
    {
      "name": "Bullish",
      "direction": "Bullish",
      "trigger_price": 355.00,
      "target_price": 372.75,
      "invalidation_price": 335.20,
      "supporting_signal_count": 7,
      "description": "Bullish scenario activates above 355.00. Target: 372.75. Invalidates below 335.20."
    }
  ],
  "risk_metrics": {
    "atr": 6.27,
    "atr_pct": 1.82,
    "atr_based_stop_loss": 332.40,
    "volatility_classification": "Normal"
  },
  "score": {
    "total": 72,
    "confidence": "Medium",
    "components": { "trend": 35, "momentum": 20, "volume": 12, "pattern": 5 }
  },
  "signals": [ ... ],
  "llm_summary_prompt": "=== THYAO TEKNIK ANALIZ RAPORU ===\n\nGENEL GORUNUM:\nFiyat: 344.50 TL | Skor: 72/100 (Medium guven)\n..."
}
```

**AI Rapor Prompt Tasarımı — Önerilen Yapı:**

```markdown
Sen profesyonel bir teknik analist olarak hareket et. 
Aşağıdaki veriye dayanarak kapsamlı bir Türkçe analiz raporu oluştur.

## HİSSE: THYAO
- Fiyat: 344.50 TL | Trend: Bullish (Günlük+Haftalık uyumlu)
- Skor: 72/100 — Medium güven
- Piyasa Rejimi: Strong Trend (Bullish), Normal volatilite
- Önerilen Strateji: Trend Following

## TEKNİK GÖSTERGELER
- RSI(14): 62.3 (Nötr bölge, aşırı alım/satım yok)
- MACD: Pozitif histogram (+0.65), bull kesişim
- SMA: Fiyat SMA 20 (338) > SMA 50 (325) > SMA 200 (290) → Golden Cross aktif
- Bollinger: Fiyat orta bandın üstünde, üst banda doğru hareket

## DESTEK / DİRENÇ
- En yakın destek: 335.20 TL (Volume POC, güç: 95/100)
- En yakın direnç: 355.00 TL (Volume VAH, güç: 90/100)

## FORMASYONLAR
- Bullish Engulfing (bugün) — yeni oluşum
- Başka aktif formasyon yok

## SENARYOLAR
1. BULL: 355 üstü → Hedef 372.75 (7 sinyal destekli)
2. BASE: 335-355 bandında devam
3. BEAR: 335 altı → Hedef ~320

## RİSK
- Volatilite: Normal (ATR %1.82)
- Stop-Loss: 332.40 TL (ATR bazlı 1.5x)

---

Rapor formatı:
1. **Yönetici Özeti** (2-3 cümle)
2. **Piyasa Rejimi ve Strateji**
3. **Teknik Gösterge Detayı**
4. **Destek/Direnç ve Formasyonlar**
5. **Senaryolar**
6. **Risk Değerlendirmesi**
```

---

### 2.3 Batch Screening — `POST /batch`

**Kullanım Senaryosu:** Hono "Alım fırsatı olan hisseler" gibi sorular için toplu tarama yapar.

**İstek:**
```json
POST /api/v1/ta/batch
{
  "tickers": ["THYAO", "ASELS", "EREGL", "GARAN", "SASA", "TUPRS", "AKBNK"],
  "filters": {
    "score_min": 65,
    "regime": "Strong Trend",
    "trend": "Bullish"
  }
}
```

**Response:**
```json
{
  "results": [
    { "ticker": "ASELS", "score": 78, "confidence": "High", "regime": "Strong Trend", "trend": "Bullish", "price": 62.50, "nearest_support": 60.20, "nearest_resistance": 65.00 },
    { "ticker": "THYAO", "score": 72, "confidence": "Medium", "regime": "Strong Trend", "trend": "Bullish", "price": 344.50, "nearest_support": 335.20, "nearest_resistance": 355.00 }
  ],
  "total": 7,
  "filtered": 2
}
```

**Limits:**
- `tickers` array max 500 eleman
- `filters` opsiyonel — boş gönderilirse sıralı sonuç döner
- Timeout: 30 saniye (500 ticker için ~5-10sn beklenir)

**Hono Tarafında Kullanım:**

```javascript
// Fırsat taraması
const response = await fetch(`${TA_API}/batch`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ 
    tickers: allTickers, 
    filters: { score_min: 65, regime: 'Strong Trend' }
  })
});
const { results } = await response.json();

// LLM prompt'u için özet
const prompt = results.map(r => 
  `${r.ticker}: Score ${r.score}/100, ${r.regime}, ${r.trend}, Destek ${r.nearest_support}, Direnç ${r.nearest_resistance}`
).join('\n');
```

---

### 2.4 Sektör & Endeks

**Sektör Özeti:**
```
GET /api/v1/ta/sector/BANKACILIK/summary
```
```json
{
  "sector": "BANKACILIK",
  "ticker_count": 10,
  "median_score": 62,
  "avg_return": 1.25,
  "above_sma_50_pct": 70.0,
  "top_performers": ["GARAN"],
  "bottom_performers": ["HALKB"],
  "sector_regime": "Bullish"
}
```

**Endeks Genişliği:**
```
GET /api/v1/ta/index/XU100/breadth
```
```json
{
  "index_code": "XU100",
  "constituent_count": 95,
  "above_sma_50_pct": 65.3,
  "advance_decline_ratio": 1.42,
  "status": "Neutral",
  "interpretation": "65.3% of constituents above 50-day MA. Advance/Decline ratio: 1.42. Market breadth is neutral."
}
```

---

### 2.5 Geçmiş Benzer Durum — `/history-lookup`

**Kullanım Senaryosu:** Chatbot'a "Bu durum geçmişte nasıl sonuçlandı?" sorusu gelince.

```
GET /api/v1/ta/THYAO/history-lookup?lookback_bars=20&threshold=5
```
```json
{
  "ticker": "THYAO",
  "current_score": 72,
  "current_regime": "Strong Trend",
  "similar_past_states": [
    { "date": "2024-10-15", "score_approx": 70, "price": 298.50, "forward_return_pct": 8.5, "bars_ago": 180 },
    { "date": "2024-08-20", "score_approx": 68, "price": 275.00, "forward_return_pct": 12.3, "bars_ago": 240 }
  ],
  "average_outcome": 7.2,
  "positive_outcome_pct": 75.0,
  "sample_size": 8
}
```

---

## 3. Cache Stratejisi

| Endpoint | Piyasa Açık TTL | Piyasa Kapalı TTL | Not |
|----------|-----------------|-------------------|-----|
| `/context/*` | 5 dk | 1 saat | Chatbot sorguları sık |
| `/full/*` | 15 dk | 6 saat | AI rapor ağır, az sorgulanır |
| `/public/*` | 5 dk | 1 saat | Yüksek trafik |
| `/member/*` | 5 dk | 1 saat | Üye sayfaları |
| `/sector/*` | 15 dk | 6 saat | Nadiren değişir |
| `/batch` | **Cache'lenmez** | — | Her istek farklı filtre |
| `/history-lookup` | **Cache'lenmez** | — | Canlı veri |

**Öneri:** Hono kendi tarafında `/context` ve `/full` için **in-memory cache** de tutabilir (5-10sn TTL) — böylece aynı ticker'a gelen tekrarlı isteklerde API'ye gitmez.

---

## 4. Hata Yönetimi

**API'den dönen hata formatı:**
```json
// 404—Veri bulunamadı
{ "detail": "No historical data found" }

// 400 — Geçersiz istek
{ "detail": "tickers list required" }
```

**Hono tarafında handling:**
```typescript
async function fetchTA(endpoint: string, fallback: any = null) {
  try {
    const res = await fetch(`${TA_BASE}/${endpoint}`);
    if (res.status === 304) return null; // ETag hit
    if (!res.ok) {
      console.warn(`TA API ${res.status}: ${endpoint}`);
      return fallback;
    }
    return await res.json();
  } catch (err) {
    console.error(`TA API unreachable: ${endpoint}`, err);
    return fallback;
  }
}
```

---

## 5. ETag / 304 Kullanımı

API tüm JSON GET response'larda ETag header'ı döner. Hono bu mekanizmayı kullanarak bant genişliğinden tasarruf edebilir:

```typescript
const res = await fetch(url, {
  headers: { 'If-None-Match': storedEtag }
});
if (res.status === 304) {
  // storedData hala güncel, cache'den kullan
  return storedData;
}
const etag = res.headers.get('ETag');
const data = await res.json();
// data + etag'i cache'le
```

---

## 6. Rate Limiting & Best Practices

- **Aynı ticker'a saniyede max 1 istek** — cache TTL zaten 5dk, aynı anda 5 farklı query_type gerekirse bile tek istek yeter
- **Batch isteklerinde max 500 ticker** — ama 100'erlik chunk'lar halinde göndermek daha hızlı
- **AI rapor için `/full` kullan, `/context` kullanma** — `/context` chatbot için lightweight, AI rapor prompt'u için yetersiz kalır
- **Piyasa saatleri dışında** cache TTL'leri uzar, veri güncellenmez — Hono bu durumu `{"market_open": false}` gibi bir kontrolle yönetebilir
