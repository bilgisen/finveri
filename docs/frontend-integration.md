# TanStack Frontend — TA API Entegrasyon Kılavuzu

> **Hedef:** TanStack Start (React) frontend uygulamasının endeks, şirket, chatbot ve AI rapor sayfaları için TA API'yi doğru tüketmesi.

---

## 1. API Taban URL

```typescript
const TA_API = 'https://tapi.paraanaliz.workers.dev/api/v1/ta';
const INSTRUMENTS_API = 'https://tapi.paraanaliz.workers.dev/instruments';
```

---

## 2. TypeScript Type Definitions

Aşağıdaki type'ları frontend codebase'inize ekleyin:

```typescript
// src/types/technical.ts

// ── PUBLIC SUMMARY ─────────────────────────────────────────
export interface TAPublicSummary {
  ticker: string;
  price: number;
  change_pct: number | null;
  date: string;
  trend: 'Bullish' | 'Bearish' | 'Neutral';
  regime: string | null;
  score: number;
  confidence: 'High' | 'Medium' | 'Low';
  sma: {
    sma_20: number | null;
    sma_50: number | null;
    sma_200: number | null;
  };
  rsi: number | null;
  macd_status: 'Bullish' | 'Bearish';
  nearest_support: number | null;
  nearest_resistance: number | null;
  summary_text: string;
}

// ── MEMBER SUMMARY ─────────────────────────────────────────
export interface TAMemberSummary {
  ticker: string;
  price: number;
  change_pct: number | null;
  indicators: IndicatorSummary;
  trend: string;
  weekly_trend: string;
  regime: MarketRegime;
  volume_profile: VolumeProfile;
  liquidity_voids: LiquidityVoid[];
  sr_zones: SupportResistance;
  score: number;
  confidence: string;
  score_components: { trend: number; momentum: number; volume: number };
  signals: string[];
  divergences: DivergenceAnalysis;
  golden_cross: GoldenCrossInfo;
  mtf_alignment: MTFAlignment;
  summary_text: string;
}

export interface IndicatorSummary {
  rsi: number | null;
  macd: MACD | null;
  sma: SMA;
  ema_9: number | null;
  ema_21: number | null;
  bbands: BollingerBands;
  atr: number | null;
  atr_pct: number | null;
  stoch: StochData;
  adx: ADXData;
  obv: number | null;
  mfi: number | null;
  supertrend: number | null;
  supertrend_direction: 'up' | 'down' | null;
  vwap: number | null;
}

export interface MACD {
  value: number | null;
  signal: number | null;
  histogram: number | null;
}
export interface BollingerBands {
  upper: number | null;
  middle: number | null;
  lower: number | null;
}
export interface StochData { k: number | null; d: number | null; }
export interface ADXData { adx: number | null; plus_di: number | null; minus_di: number | null; }
export interface SMA { sma_20: number | null; sma_50: number | null; sma_200: number | null; }

export interface MarketRegime {
  regime: string;
  trend_direction: string;
  volatility_regime: string;
  adx: number | null;
  efficiency_ratio: number | null;
  volatility_pct: number | null;
  confidence: number;
  recommended_strategy: string;
  interpretation: string;
}

export interface VolumeProfile {
  poc: number | null;
  poc_volume: number | null;
  value_area_high: number | null;
  value_area_low: number | null;
  total_volume: number | null;
}

export interface LiquidityVoid {
  date: string;
  gap_start: number;
  gap_end: number;
  gap_size: number;
  gap_pct: number;
  direction: 'up' | 'down';
  bars_ago: number;
}

export interface SRLevel {
  price: number;
  type: string;
  strength: number;
}

export interface SupportResistance {
  current_price: number;
  resistance_zones: SRLevel[];
  support_zones: SRLevel[];
  nearest_resistance: SRLevel | null;
  nearest_support: SRLevel | null;
}

export interface DivergenceAnalysis {
  rsi: { bullish: boolean; bearish: boolean };
  macd: { bullish: boolean; bearish: boolean };
  obv: { bullish: boolean; bearish: boolean };
  overall_confidence: string;
  divergence_count: number;
}

export interface GoldenCrossInfo {
  has_golden_cross: boolean;
  has_death_cross: boolean;
  bars_since_cross: number | null;
  sma_20_minus_sma_50: number | null;
}

export interface MTFAlignment {
  daily_trend: string;
  weekly_trend: string;
  monthly_trend: string;
  alignment_score: number;
  alignment_label: string;
}

// ── FULL ANALYSIS (Abone) ──────────────────────────────────
export interface TAFullAnalysis {
  ticker: string;
  price: number;
  change_pct: number | null;
  trend: string;
  weekly_trend: string;
  indicators: IndicatorSummary;
  golden_cross: GoldenCrossInfo;
  trend_age: { daily_direction: string; daily_bars: number };
  mtf_alignment: MTFAlignment;
  volume_metrics: VolumeMetrics;
  regime: MarketRegime;
  volume_profile: VolumeProfile;
  liquidity_voids: LiquidityVoid[];
  sr_zones: SupportResistance;
  patterns: PatternAnalysis;
  divergences: DivergenceAnalysis;
  scenarios: Scenario[];
  risk_metrics: RiskMetrics;
  score: CompositeScore;
  signals: ActiveSignal[];
  llm_summary_prompt: string;
}

export interface VolumeMetrics {
  obv_trend: string;
  relative_volume: number | null;
  volume_confirmation: string;
}

export interface PatternAnalysis {
  candlestick_patterns: CandlestickPattern[];
  chart_patterns: ChartPattern[];
  total_active: number;
}

export interface CandlestickPattern {
  name: string;
  direction: string;
  reliability: number;
  bars_ago: number;
  confirmation_volume: boolean;
}

export interface ChartPattern {
  name: string;
  direction: string;
  entry_price: number | null;
  target_price: number | null;
  confidence: number;
}

export interface Scenario {
  name: string;
  direction: string;
  trigger_price: number | null;
  target_price: number | null;
  invalidation_price: number | null;
  supporting_signal_count: number;
  description: string;
}

export interface RiskMetrics {
  atr_based_stop_loss: number | null;
  atr_pct: number | null;
  volatility_classification: string;
}

export interface CompositeScore {
  total: number;
  confidence: string;
  components: { trend: number; momentum: number; volume: number; pattern: number };
}

export interface ActiveSignal {
  label: string;
  direction: string;
  source: string;
  freshness: string;
}

// ── CHATBOT CONTEXT ────────────────────────────────────────
export interface TAContext {
  ticker: string;
  current_price: number;
  trend: string;
  regime: MarketRegime;
  key_levels: {
    nearest_support: SRLevel | null;
    nearest_resistance: SRLevel | null;
    support_zones: SRLevel[];
    resistance_zones: SRLevel[];
  };
  active_signals: ActiveSignal[];
  scenarios: Scenario[];
  risk_metrics: RiskMetrics;
  summary_text: string;
}

// ── BATCH SCREENING ────────────────────────────────────────
export interface BatchResult {
  ticker: string;
  score: number;
  confidence: string;
  regime: string | null;
  trend: string;
  price: number | null;
  nearest_support: number | null;
  nearest_resistance: number | null;
}

export interface BatchResponse {
  results: BatchResult[];
  total: number;
  filtered: number;
}

// ── SECTOR & INDEX ─────────────────────────────────────────
export interface SectorSummary {
  sector: string;
  ticker_count: number;
  median_score: number;
  avg_return: number | null;
  above_sma_50_pct: number;
  top_performers: string[];
  bottom_performers: string[];
  sector_regime: string;
}

export interface IndexBreadth {
  index_code: string;
  constituent_count: number;
  above_sma_20_pct: number;
  above_sma_50_pct: number;
  above_sma_200_pct: number;
  advancing_count: number;
  declining_count: number;
  advance_decline_ratio: number | null;
  status: string;
  interpretation: string;
}

// ── STOCK PRICE ────────────────────────────────────────────
export interface StockQuote {
  code: string;
  name: string;
  last_price: number;
  diff_percent: number;
  volume: number;
  high_price: number;
  low_price: number;
}
```

---

## 3. React Query / Fetch Hook'ları

### 3.1 Public Summary (Herkes — Endeks/Şirket sayfası)

```typescript
// src/hooks/useTAPublicSummary.ts
import { useQuery } from '@tanstack/react-query';

const fetchPublicSummary = async (ticker: string): Promise<TAPublicSummary> => {
  const res = await fetch(`${TA_API}/public/${ticker}/summary`);
  if (!res.ok) throw new Error(`TA API ${res.status}: ${ticker}`);
  return res.json();
};

export function useTAPublicSummary(ticker: string) {
  return useQuery({
    queryKey: ['ta', 'public', ticker],
    queryFn: () => fetchPublicSummary(ticker),
    staleTime: 5 * 60 * 1000,      // 5 dk taze
    gcTime: 30 * 60 * 1000,         // 30 dk cache'te tut
    retry: 2,
    enabled: !!ticker,
  });
}
```

**Sayfada kullanım:**
```tsx
function TACard({ ticker }: { ticker: string }) {
  const { data, isLoading, isError } = useTAPublicSummary(ticker);

  if (isLoading) return <Skeleton />;
  if (isError) return <ErrorState />;

  return (
    <div className="rounded-xl border p-4">
      <div className="flex items-center gap-2">
        <h3 className="text-lg font-bold">{data.ticker}</h3>
        <Badge variant={data.trend === 'Bullish' ? 'success' : 'destructive'}>
          {data.trend}
        </Badge>
        <span className="text-sm text-muted">{data.score}/100</span>
      </div>
      <div className="mt-2 text-2xl font-mono">
        {data.price.toFixed(2)} TL
        {data.change_pct != null && (
          <span className={`ml-2 text-sm ${data.change_pct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {data.change_pct > 0 ? '+' : ''}{data.change_pct}%
          </span>
        )}
      </div>
      {data.regime && <p className="text-sm text-muted mt-1">Piyasa: {data.regime}</p>}
      {data.nearest_support && data.nearest_resistance && (
        <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
          <div>Destek: <span className="font-mono">{data.nearest_support.toFixed(2)}</span></div>
          <div>Direnç: <span className="font-mono">{data.nearest_resistance.toFixed(2)}</span></div>
        </div>
      )}
      <p className="mt-2 text-xs text-muted">{data.summary_text}</p>
    </div>
  );
}
```

### 3.2 Member Summary (Üye sayfası)

```typescript
export function useTAMemberSummary(ticker: string) {
  return useQuery({
    queryKey: ['ta', 'member', ticker],
    queryFn: async () => {
      const res = await fetch(`${TA_API}/member/${ticker}/summary`);
      if (!res.ok) throw new Error(`TA API ${res.status}`);
      return res.json() as Promise<TAMemberSummary>;
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!ticker,
  });
}
```

**Dashboard kullanımı:**
```tsx
function TechnicalDashboard({ ticker }: { ticker: string }) {
  const { data } = useTAMemberSummary(ticker);
  if (!data) return null;

  return (
    <div className="grid grid-cols-3 gap-4">
      {/* Rejim Kartı */}
      <Card>
        <CardHeader>Piyasa Rejimi</CardHeader>
        <CardBody>
          <div className="text-xl font-bold">{data.regime.regime}</div>
          <div className={data.regime.trend_direction === 'Bullish' ? 'text-green' : 'text-red'}>
            {data.regime.trend_direction}
          </div>
          <p className="text-sm text-muted mt-1">{data.regime.recommended_strategy}</p>
          <Progress value={data.regime.adx} max={60} label={`ADX: ${data.regime.adx}`} />
        </CardBody>
      </Card>

      {/* Gösterge Kartı */}
      <Card>
        <CardHeader>Göstergeler</CardHeader>
        <CardBody>
          <Gauge value={data.rsi} label="RSI" min={0} max={100} />
          <Gauge value={data.macd.histogram} label="MACD" min={-5} max={5} />
          <Gauge value={data.score} label="Skor" min={0} max={100} />
        </CardBody>
      </Card>

      {/* Sinyal Kartı */}
      <Card>
        <CardHeader>Sinyaller</CardHeader>
        <CardBody>
          {data.signals.slice(0, 5).map((s, i) => (
            <div key={i} className="flex items-center gap-1 text-sm">
              <span>{s.startsWith('✓') ? '🟢' : s.startsWith('✗') ? '🔴' : '⚪'}</span>
              <span>{s.replace(/^[✓✗⊙]\s*/, '')}</span>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
```

### 3.3 Full Analysis (Abone sayfası — AI Rapor)

```typescript
export function useTAFullAnalysis(ticker: string) {
  return useQuery({
    queryKey: ['ta', 'full', ticker],
    queryFn: async () => {
      const res = await fetch(`${TA_API}/full/${ticker}`);
      if (!res.ok) throw new Error(`TA API ${res.status}`);
      return res.json() as Promise<TAFullAnalysis>;
    },
    staleTime: 15 * 60 * 1000,  // 15 dk — AI rapor sık sorgulanmaz
    enabled: !!ticker,
  });
}
```

**AI Rapor Sayfası:**
```tsx
function AIRreportPage({ ticker }: { ticker: string }) {
  const { data, isLoading } = useTAFullAnalysis(ticker);

  if (isLoading) return <FullPageSkeleton />;

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">{data.ticker}</h1>
        <span className="text-2xl font-mono">{data.price.toFixed(2)} TL</span>
      </div>

      {/* Score Ring */}
      <ScoreRing value={data.score.total} max={100} confidence={data.score.confidence} />

      {/* Detaylı Tablo */}
      <DetailTable indicators={data.indicators} />

      {/* Destek/Direnç Grafik */}
      <SRChart support={data.sr_zones} price={data.price} />

      {/* Senaryolar */}
      <ScenarioCards scenarios={data.scenarios} />

      {/* Formasyon Listesi */}
      <PatternList patterns={data.patterns} />

      {/* AI Prompt (debug için veya LLM API'ye göndermek için) */}
      <pre className="bg-muted p-4 rounded text-sm mt-6">
        {data.llm_summary_prompt}
      </pre>
    </div>
  );
}
```

### 3.4 Chatbot Context

```typescript
export function useTAContext(ticker: string, queryType: string = 'general') {
  return useQuery({
    queryKey: ['ta', 'context', ticker, queryType],
    queryFn: async () => {
      const res = await fetch(`${TA_API}/context/${ticker}?query_type=${queryType}`);
      if (!res.ok) throw new Error(`TA API ${res.status}`);
      return res.json() as Promise<TAContext>;
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!ticker,
  });
}
```

---

### 3.5 Batch Screening

```typescript
export function useTABatch(tickers: string[], filters?: Record<string, any>) {
  return useQuery({
    queryKey: ['ta', 'batch', tickers.join(','), filters],
    queryFn: async () => {
      const res = await fetch(`${TA_API}/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers, filters }),
      });
      if (!res.ok) throw new Error(`TA API ${res.status}`);
      return res.json() as Promise<BatchResponse>;
    },
    enabled: tickers.length > 0,
    staleTime: 5 * 60 * 1000,
  });
}
```

### 3.6 Sektör & Endeks

```typescript
export function useSectorSummary(sector: string) {
  return useQuery({
    queryKey: ['ta', 'sector', sector],
    queryFn: async () => {
      const res = await fetch(`${TA_API}/sector/${sector}/summary`);
      if (!res.ok) throw new Error(`TA API ${res.status}`);
      return res.json() as Promise<SectorSummary>;
    },
    staleTime: 15 * 60 * 1000,
    enabled: !!sector,
  });
}

export function useIndexBreadth(indexCode: string) {
  return useQuery({
    queryKey: ['ta', 'index', indexCode],
    queryFn: async () => {
      const res = await fetch(`${TA_API}/index/${indexCode}/breadth`);
      if (!res.ok) throw new Error(`TA API ${res.status}`);
      return res.json() as Promise<IndexBreadth>;
    },
    staleTime: 15 * 60 * 1000,
    enabled: !!indexCode,
  });
}
```

---

## 4. Sayfa-API Eşleme Matrisi

| Sayfa | Endpoint | Hook | Cache TTL | Erişim |
|-------|----------|------|-----------|--------|
| **Endeks Ana Sayfa** | `GET /index/XU100/breadth` | `useIndexBreadth` | 15 dk | Herkes |
| **Şirket Sayfası (kart)** | `GET /public/{kod}/summary` | `useTAPublicSummary` | 5 dk | Herkes |
| **Şirket Sayfası (detay)** | `GET /member/{kod}/summary` | `useTAMemberSummary` | 5 dk | Üye+ |
| **Sektör Sayfası** | `GET /sector/{s}/summary` | `useSectorSummary` | 15 dk | Herkes |
| **AI Rapor Sayfası** | `GET /full/{kod}` | `useTAFullAnalysis` | 15 dk | Abone |
| **Chatbot (genel)** | `GET /context/{kod}?query_type=general` | `useTAContext` | 5 dk | Üye+ |
| **Chatbot (pozisyon)** | `GET /context/{kod}?query_type=entry` | `useTAContext(t, 'entry')` | 5 dk | Üye+ |
| **Chatbot (risk)** | `GET /context/{kod}?query_type=risk` | `useTAContext(t, 'risk')` | 5 dk | Üye+ |
| **Tarama/Screening** | `POST /batch` | `useTABatch` | 5 dk | Abone |

---

## 5. Error & Loading State Yönetimi

```tsx
// Generic TA endpoint wrapper
function TAEndpoint<T>({ 
  hook, 
  params, 
  children,
  fallback 
}: { 
  hook: (...args: any[]) => UseQueryResult<T>; 
  params: any[]; 
  children: (data: T) => ReactNode;
  fallback?: ReactNode;
}) {
  const { data, isLoading, isError, error } = hook(...params);

  if (isLoading) return <Skeleton className="h-48 w-full" />;
  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Veri alınamadı</AlertTitle>
        <AlertDescription>{(error as Error).message}</AlertDescription>
        <Button variant="outline" size="sm" onClick={() => refetch()}>Tekrar Dene</Button>
      </Alert>
    );
  }
  if (!data) return fallback ?? <EmptyState />;
  return <>{children(data)}</>;
}

// Kullanım
<TAEndpoint hook={useTAPublicSummary} params={['THYAO']}>
  {(data) => <TACard {...data} />}
</TAEndpoint>
```

---

## 6. Piyasa Saati Kontrolü

```typescript
function useMarketStatus() {
  return useQuery({
    queryKey: ['market', 'status'],
    queryFn: async () => {
      const now = new Date();
      const istOffset = 3 * 60;
      const ist = new Date(now.getTime() + istOffset * 60 * 1000);
      const hour = ist.getUTCHours();
      const day = ist.getUTCDay();
      return {
        open: day >= 1 && day <= 5 && hour >= 9 && hour < 17,
        timezone: 'Europe/Istanbul',
        localTime: ist.toLocaleTimeString('tr-TR', { timeZone: 'Europe/Istanbul' }),
      };
    },
    staleTime: 60 * 1000, // 1dk güncelle
  });
}

// Kullanım: Cache TTL'yi duruma göre ayarla
function useAdaptiveStaleTime(baseMinutes: number) {
  const { data: market } = useMarketStatus();
  return market?.open ? baseMinutes * 60 * 1000 : baseMinutes * 4 * 60 * 1000;
}
```

---

## 7. Performans İpuçları

1. **Query key'leri normalize edin:** `['ta', 'public', ticker.toUpperCase()]` — aynı ticker farklı case'lerde cache hit alsın
2. **Prefetch kullanın:** Şirket sayfasına hover'da `/public/{kod}/summary`'i prefetch'leyin
3. **`staleTime` > `gcTime`** tutun — veri eskiyse bile önce göster, arka planda güncelle (stale-while-revalidate)
4. **Batch isteklerini throttle'layın:** Screening sayfasında `useTABatch`'i her input change'de değil, 500ms debounce ile çağırın
5. **Abone sayfasında `/full` endpoint'ini sadece sayfaya girildiğinde çağırın** — AI rapor ağır bir hesaplama
6. **Chart verisi** için `GET /instruments/{kod}/history` endpoint'ini kullanın (TA endpoint'lerinden bağımsız)

```typescript
// Prefetch örneği
const queryClient = useQueryClient();
const prefetch = (ticker: string) => {
  queryClient.prefetchQuery({
    queryKey: ['ta', 'public', ticker],
    queryFn: () => fetch(`${TA_API}/public/${ticker}/summary`).then(r => r.json()),
    staleTime: 5 * 60 * 1000,
  });
};

return (
  <Link 
    to={`/hisse/${ticker}`} 
    onMouseEnter={() => prefetch(ticker)}
  >
    {ticker}
  </Link>
);
```

---

## 8. Örnek: Endeks Sayfası (Komple)

```tsx
function IndexPage({ indexCode }: { indexCode: string }) {
  const breadth = useIndexBreadth(indexCode);
  const stocks = useQuery({
    queryKey: ['instruments', 'stocks'],
    queryFn: async () => {
      const res = await fetch(`${INSTRUMENTS_API}/stocks`);
      return res.json();
    },
  });

  if (breadth.isLoading) return <PageSkeleton />;

  return (
    <div className="p-6">
      {/* Breadth Header */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="SMA 50 Üstü" value={`${breadth.data?.above_sma_50_pct}%`} />
        <StatCard label="A/D Ratio" value={breadth.data?.advance_decline_ratio} />
        <StatCard label="Yükselen" value={breadth.data?.advancing_count} />
        <StatCard label="Düşen" value={breadth.data?.declining_count} />
      </div>

      {/* Breadth Status */}
      <Alert variant={breadth.data?.status === 'Bullish' ? 'default' : 'destructive'}>
        {breadth.data?.interpretation}
      </Alert>

      {/* Hisse Listesi */}
      <StockTable 
        data={stocks.data?.data} 
        onRowHover={(code) => prefetchTA(code)}
      />
    </div>
  );
}
```
