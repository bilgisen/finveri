# Chatbot Integration Examples

Bu dokümantasyon, finveri API'sini chatbot'a entegre etmek için pratik örnekler içerir.

---

## 📋 Temel Kullanım Senaryoları

### Senaryo 1: "THYAO hissesini analiz et"

**Backend (Hono/Node.js):**

```typescript
// app/lib/ta-client.ts
export async function analyzeTicker(ticker: string) {
  const response = await fetch(
    `${process.env.FINVERI_API}/api/v1/ta/summary/${ticker.toUpperCase()}`
  );
  
  if (!response.ok) {
    throw new Error(`Failed to fetch TA for ${ticker}`);
  }
  
  return await response.json();
}

// app/routes/chat.ts
import { analyzeTicker } from '@/lib/ta-client';

export async function POST(request: Request) {
  const { message, ticker } = await request.json();
  
  // Kullanıcı "THYAO analiz et" dedi
  if (ticker) {
    const taData = await analyzeTicker(ticker);
    
    // Chatbot'a zengin context gönder
    const prompt = buildPrompt(message, taData);
    const llmResponse = await callLLM(prompt);
    
    return Response.json({
      message: llmResponse,
      context: {
        ticker: taData.ticker,
        price: taData.close,
        score: taData.score,
        trend: taData.trend
      }
    });
  }
}

function buildPrompt(userMessage: string, taData: any) {
  return `
You are a professional Turkish stock market analyst. 

CONTEXT:
${taData.llm_summary_prompt}

USER QUESTION: ${userMessage}

Provide a detailed analysis in Turkish covering:
1. Current market regime and what it means for traders
2. Key support (${taData.support_resistance_zones.nearest_support?.price} TL) and resistance (${taData.support_resistance_zones.nearest_resistance?.price} TL) levels
3. Entry strategy based on: ${taData.market_regime.recommended_strategy}
4. Risk management (stop-loss, position sizing)

Keep the tone professional but conversational.
`;
}
```

**Örnek Response:**

```
Chatbot: THYAO şu anda 385.50 TL seviyesinde ve **güçlü yükseliş trendi** içinde (teknik skor: 70/100, yüksek güven).

📊 **Piyasa Rejimi:** Strong Trend (Bullish yönlü)
Bu, trend takip stratejilerinin iyi çalıştığı bir ortam. Hareketli ortalama kesimleri ve Supertrend gibi göstergelerle işlem yapabilirsiniz.

🎯 **Kritik Seviyeler:**
- **Destek:** 378.20 TL (Volume POC - en güçlü seviye, %95 güvenilirlik)
- **Direnç:** 395.00 TL (Value Area High - %90 güvenilirlik)

💡 **Strateji Önerisi:**
1. **Giriş:** Mevcut fiyat (385.50 TL) trend yönünde
2. **Stop-Loss:** 378.20 TL (POC desteği altı)
3. **Hedef:** 395.00 TL (VAH direnci)
4. **Risk/Ödül:** 2.45 (ideal oran)

⚠️ **Risk Yönetimi:** Pozisyon büyüklüğünüzü sermayenizin %2'siyle sınırlayın. Stop-loss'u 378.20 TL'de tutun.

Başka bir detay öğrenmek ister misiniz?
```

---

### Senaryo 2: "Hangi hisseler alım fırsatı sunuyor?"

**Backend:**

```typescript
// app/lib/screening.ts
export async function screenBullishOpportunities() {
  const tickers = ['THYAO', 'ASELS', 'EREGL', 'SASA', 'TUPRS', 'KCHOL', 'GARAN'];
  
  const analyses = await Promise.all(
    tickers.map(ticker => 
      fetch(`${API_BASE}/api/v1/ta/advanced/full-context/${ticker}`)
        .then(r => r.json())
        .catch(e => ({ ticker, error: e.message }))
    )
  );
  
  // Filtreleme kriterleri:
  // 1. Strong Trend veya Weak Trend
  // 2. Bullish yön
  // 3. Score > 60
  // 4. Confidence: High veya Medium
  const opportunities = analyses
    .filter(a => !a.error)
    .filter(a => 
      ['Strong Trend', 'Weak Trend'].includes(a.market_regime?.regime) &&
      a.market_regime?.trend_direction === 'Bullish' &&
      a.score > 60 &&
      ['High', 'Medium'].includes(a.confidence)
    )
    .sort((a, b) => b.score - a.score);
  
  return opportunities;
}

// Chat endpoint
export async function POST(request: Request) {
  const { message } = await request.json();
  
  if (message.includes('alım fırsatı') || message.includes('hangi hisse')) {
    const opportunities = await screenBullishOpportunities();
    
    const prompt = `
User asked: "${message}"

Here are the top bullish opportunities based on technical analysis:

${opportunities.map((opp, i) => `
${i+1}. ${opp.ticker} - Score: ${opp.score}/100
   Price: ${opp.current_price} TL
   Regime: ${opp.market_regime.regime} (${opp.market_regime.trend_direction})
   Support: ${opp.support_resistance_zones.nearest_support?.price} TL
   Resistance: ${opp.support_resistance_zones.nearest_resistance?.price} TL
   Strategy: ${opp.market_regime.recommended_strategy}
`).join('\n')}

Provide a Turkish summary ranking these opportunities and explaining WHY each is interesting based on the data above.
`;
    
    const llmResponse = await callLLM(prompt);
    
    return Response.json({
      message: llmResponse,
      opportunities: opportunities.map(o => ({
        ticker: o.ticker,
        score: o.score,
        price: o.current_price,
        trend: o.market_regime.trend_direction
      }))
    });
  }
}
```

**Örnek Response:**

```
Chatbot: Teknik analize göre şu anda **3 hisse alım fırsatı** sunuyor:

🥇 **1. ASELS - 78/100 puan**
   • Fiyat: 82.45 TL
   • Durum: Güçlü yükseliş trendi
   • Destek: 78.20 TL (Volume POC)
   • Hedef: 87.00 TL
   • Neden öne çıkıyor? En yüksek teknik skor + güçlü momentum

🥈 **2. THYAO - 70/100 puan**
   • Fiyat: 385.50 TL
   • Durum: Güçlü yükseliş trendi
   • Destek: 378.20 TL
   • Hedef: 395.00 TL
   • Neden öne çıkıyor? Yüksek güven seviyesi + temiz trend

🥉 **3. SASA - 64/100 puan**
   • Fiyat: 156.30 TL
   • Durum: Zayıf yükseliş trendi
   • Destek: 152.00 TL
   • Hedef: 162.00 TL
   • Neden öne çıkıyor? Yeni kırılım potansiyeli

💡 **Strateji:** Her üç hisse için trend takip yaklaşımı uygun. Portföyünüzü %30-%40-%30 şeklinde dağıtabilirsiniz.

Detaylı analiz için bir hisse seçer misiniz?
```

---

### Senaryo 3: "EREGL için stop-loss nerede olmalı?"

**Backend:**

```typescript
export async function POST(request: Request) {
  const { message, ticker } = await request.json();
  
  if (message.includes('stop') || message.includes('risk')) {
    const taData = await analyzeTicker(ticker);
    
    const prompt = `
User asked about risk management for ${ticker}: "${message}"

Technical Analysis Context:
- Current Price: ${taData.close} TL
- Trend: ${taData.trend} (${taData.market_regime.trend_direction})
- Technical Score: ${taData.score}/100
- ATR (volatility): ${taData.close * 0.02} TL (approx)

Support Levels:
${taData.support_resistance_zones.support_zones.map(s => 
  `- ${s.price} TL (${s.type}, strength: ${s.strength}%)`
).join('\n')}

Recommended Stop-Loss: ${taData.stop_loss} TL

Provide a Turkish explanation of:
1. WHY this stop-loss level makes sense
2. What happens if price hits this level
3. Alternative tighter/wider stop options
4. Position sizing recommendation
`;
    
    const llmResponse = await callLLM(prompt);
    
    return Response.json({
      message: llmResponse,
      riskMetrics: {
        stopLoss: taData.stop_loss,
        riskRewardRatio: taData.rr_ratio,
        supports: taData.support_resistance_zones.support_zones
      }
    });
  }
}
```

**Örnek Response:**

```
Chatbot: EREGL için önerilen **stop-loss: 45.20 TL** (mevcut fiyat: 48.50 TL).

🎯 **Neden bu seviye?**
Bu seviye Volume POC (Point of Control) ile çakışıyor - yani en yüksek işlem hacminin gerçekleştiği fiyat. Kurumsal yatırımcıların da bu seviyeyi destek olarak gördüğünü gösteriyor (%95 güvenilirlik).

📊 **Senaryolar:**
- **Fiyat 45.20 TL'ye düşerse:** Trend yapısı bozulur, çıkış önerilir
- **Risk:** 48.50 - 45.20 = 3.30 TL (%6.8)
- **Ödül:** Hedef 52.00 TL → 3.50 TL kazanç (%7.2)
- **Risk/Ödül:** 1.06 (kabul edilebilir)

⚙️ **Alternatif Seçenekler:**
1. **Daha sıkı (45.80 TL):** Swing low seviyesi, daha az risk ama erken stop riski
2. **Daha geniş (44.50 TL):** Value Area Low, daha fazla nefes alanı

💰 **Pozisyon Büyüklüğü:**
Sermayenizin %2'sini riske atarsanız:
- 100,000 TL sermaye → 2,000 TL risk
- 2,000 TL / 3.30 TL = ~606 adet hisse alabilirsiniz

Başka bir soru?
```

---

### Senaryo 4: "Piyasa nasıl, genel görünüm?"

**Backend:**

```typescript
export async function getMarketOverview() {
  // BIST30 hisselerini analiz et
  const bist30 = ['THYAO', 'ASELS', 'EREGL', 'KCHOL', 'GARAN', 'AKBNK', 'SASA', 'PETKM', 'TUPRS', 'ISCTR'];
  
  const analyses = await Promise.all(
    bist30.map(ticker => 
      fetch(`${API_BASE}/api/v1/ta/advanced/regime/${ticker}`)
        .then(r => r.json())
        .catch(() => null)
    )
  );
  
  const validAnalyses = analyses.filter(a => a !== null);
  
  // İstatistikler
  const stats = {
    strongTrend: validAnalyses.filter(a => a.regime === 'Strong Trend').length,
    weakTrend: validAnalyses.filter(a => a.regime === 'Weak Trend').length,
    rangeBound: validAnalyses.filter(a => a.regime === 'Range Bound').length,
    bullish: validAnalyses.filter(a => a.trend_direction === 'Bullish').length,
    bearish: validAnalyses.filter(a => a.trend_direction === 'Bearish').length,
    highVolatility: validAnalyses.filter(a => a.volatility_regime === 'High Volatility').length
  };
  
  return {
    total: validAnalyses.length,
    stats,
    analyses: validAnalyses
  };
}

export async function POST(request: Request) {
  const { message } = await request.json();
  
  if (message.includes('piyasa') && message.includes('genel')) {
    const overview = await getMarketOverview();
    
    const prompt = `
User asked about overall market condition: "${message}"

BIST30 Market Analysis (${overview.total} stocks):

Regime Distribution:
- Strong Trend: ${overview.stats.strongTrend} (${(overview.stats.strongTrend/overview.total*100).toFixed(1)}%)
- Weak Trend: ${overview.stats.weakTrend} (${(overview.stats.weakTrend/overview.total*100).toFixed(1)}%)
- Range Bound: ${overview.stats.rangeBound} (${(overview.stats.rangeBound/overview.total*100).toFixed(1)}%)

Direction:
- Bullish: ${overview.stats.bullish} (${(overview.stats.bullish/overview.total*100).toFixed(1)}%)
- Bearish: ${overview.stats.bearish} (${(overview.stats.bearish/overview.total*100).toFixed(1)}%)

Volatility:
- High Volatility: ${overview.stats.highVolatility} stocks

Provide a Turkish market overview explaining:
1. Overall market health
2. Whether it's a good time to trade (trend vs range)
3. Risk level (volatility)
4. General strategy recommendation
`;
    
    const llmResponse = await callLLM(prompt);
    
    return Response.json({
      message: llmResponse,
      stats: overview.stats
    });
  }
}
```

**Örnek Response:**

```
Chatbot: 📊 **BIST30 Piyasa Görünümü:**

🟢 **Genel Durum: OLUMLU**
BIST30 hisselerinin %60'ı güçlü veya zayıf trend içinde, bu da yönlü stratejilerin işe yarayacağı bir ortam demek.

📈 **Trend Dağılımı:**
- Güçlü Trend: 6 hisse (%20) → Trend takip yapılabilir
- Zayıf Trend: 12 hisse (%40) → Hibrit strateji
- Yatay Piyasa: 12 hisse (%40) → Mean reversion

🎯 **Yön:**
- Yükseliş: 18 hisse (%60) 🟢
- Düşüş: 12 hisse (%40) 🔴

Bu, alıcıların üstünlüğünde bir piyasa gösteriyor.

⚠️ **Volatilite:**
3 hisse yüksek volatilitede → Genel risk seviyesi: ORTA

💡 **Strateji Önerisi:**
1. **Trend takip** yapabileceğiniz hisseler: THYAO, ASELS, EREGL
2. **Mean reversion** yapabileceğiniz hisseler: GARAN, AKBNK, ISCTR
3. **Genel strateji:** Seçici yaklaşım, her hisseye aynı strateji uygulanmamalı

🚦 **Sonuç:** Piyasa işlem yapmaya uygun, ancak hisse bazında farklılaşma var. Portföy çeşitlendirmesi önemli.

Belirli bir sektöre bakmak ister misiniz?
```

---

## 🎨 Frontend UI Components

### TA Summary Card

```typescript
// components/TASummaryCard.tsx
'use client';

import { useEffect, useState } from 'react';
import { Card, CardHeader, CardBody, Badge, Progress } from '@/components/ui';

export function TASummaryCard({ ticker }: { ticker: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetch(`/api/ta/summary/${ticker}`)
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [ticker]);
  
  if (loading) return <Card>Loading...</Card>;
  if (!data) return <Card>No data</Card>;
  
  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold">{data.ticker}</h3>
          <Badge variant={data.trend === 'Bullish' ? 'success' : 'destructive'}>
            {data.trend}
          </Badge>
        </div>
        <div className="text-2xl font-bold">{data.close} TL</div>
      </CardHeader>
      
      <CardBody>
        <div className="space-y-3">
          {/* Technical Score */}
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span>Teknik Skor</span>
              <span>{data.score}/100</span>
            </div>
            <Progress value={data.score} className="h-2" />
            <span className="text-xs text-gray-500">{data.confidence} güven</span>
          </div>
          
          {/* Market Regime */}
          <div className="bg-gray-50 p-3 rounded">
            <div className="text-sm font-medium">Piyasa Rejimi</div>
            <div className="text-xs text-gray-600">
              {data.market_regime.regime} ({data.market_regime.trend_direction})
            </div>
          </div>
          
          {/* Support/Resistance */}
          <div className="grid grid-cols-2 gap-2">
            <div className="border-l-4 border-green-500 pl-2">
              <div className="text-xs text-gray-500">Destek</div>
              <div className="font-semibold">
                {data.support_resistance_zones.nearest_support?.price} TL
              </div>
              <div className="text-xs text-gray-400">
                {data.support_resistance_zones.nearest_support?.type}
              </div>
            </div>
            
            <div className="border-l-4 border-red-500 pl-2">
              <div className="text-xs text-gray-500">Direnç</div>
              <div className="font-semibold">
                {data.support_resistance_zones.nearest_resistance?.price} TL
              </div>
              <div className="text-xs text-gray-400">
                {data.support_resistance_zones.nearest_resistance?.type}
              </div>
            </div>
          </div>
          
          {/* Top Signals */}
          <div>
            <div className="text-sm font-medium mb-2">Aktif Sinyaller</div>
            <div className="space-y-1">
              {data.signals.slice(0, 3).map((signal: string, i: number) => (
                <div key={i} className="text-xs bg-blue-50 px-2 py-1 rounded">
                  {signal}
                </div>
              ))}
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
```

---

## 🔧 Advanced: Caching Strategy

```typescript
// lib/ta-cache.ts
import { Redis } from '@upstash/redis';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL,
  token: process.env.UPSTASH_REDIS_REST_TOKEN
});

export async function getCachedTA(ticker: string) {
  const cacheKey = `frontend:ta:${ticker}`;
  
  // L1: Redis cache (frontend layer)
  const cached = await redis.get(cacheKey);
  if (cached) {
    return cached;
  }
  
  // L2: finveri API (has its own Redis cache)
  const response = await fetch(`${process.env.FINVERI_API}/api/v1/ta/summary/${ticker}`);
  const data = await response.json();
  
  // Cache for 5 minutes (finveri caches for 24h, but we want fresher frontend)
  await redis.setex(cacheKey, 300, JSON.stringify(data));
  
  return data;
}
```

---

## 🚀 Production Tips

### 1. Error Handling

```typescript
async function safeAnalyzeTicker(ticker: string) {
  try {
    const response = await fetch(`${API_BASE}/api/v1/ta/summary/${ticker}`, {
      signal: AbortSignal.timeout(5000) // 5s timeout
    });
    
    if (!response.ok) {
      if (response.status === 404) {
        return { error: 'Ticker not found', ticker };
      }
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error(`TA analysis failed for ${ticker}:`, error);
    return { error: 'Analysis failed', ticker };
  }
}
```

### 2. Rate Limiting

```typescript
import pLimit from 'p-limit';

const limit = pLimit(5); // Max 5 concurrent requests

async function analyzeBatch(tickers: string[]) {
  return Promise.all(
    tickers.map(ticker => 
      limit(() => safeAnalyzeTicker(ticker))
    )
  );
}
```

### 3. Progressive Loading

```typescript
// Show basic info immediately, load advanced context in background
export function TAChatWidget({ ticker }: { ticker: string }) {
  const [basicData, setBasicData] = useState(null);
  const [advancedData, setAdvancedData] = useState(null);
  
  useEffect(() => {
    // Fast: Basic summary
    fetch(`/api/ta/${ticker}?indicators=rsi,macd,sma_20`)
      .then(r => r.json())
      .then(setBasicData);
    
    // Slower: Full context
    fetch(`/api/ta/advanced/full-context/${ticker}`)
      .then(r => r.json())
      .then(setAdvancedData);
  }, [ticker]);
  
  return (
    <div>
      {basicData && <QuickSummary data={basicData} />}
      {advancedData && <DetailedAnalysis data={advancedData} />}
    </div>
  );
}
```

---

## 📚 Best Practices

1. **Always cache TA data**: API responses don't change second-to-second
2. **Use `/full-context` for chatbot**: Single endpoint = less latency
3. **Fallback gracefully**: If API fails, show last cached data
4. **Progressive enhancement**: Show basic price → add TA → add AI insights
5. **Respect rate limits**: Batch requests, use timeouts

---

**Happy coding! 🚀**
