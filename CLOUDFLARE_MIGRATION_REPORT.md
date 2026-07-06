# Finveri — Cloudflare Workers Migration Report

## 1. Proje Özeti

FastAPI tabanlı finansal veri API'sı. BIST (Borsa İstanbul) hisseleri, endeksleri ve forex verilerini gerçek zamanlı olarak sunar. 3 katmanlı mimari:

1. **Veri Toplama**: İş Yatırım, Anadolu Ajansı gibi kaynaklardan canlı fiyat çekme
2. **Teknik Analiz**: RSI, MACD, Bollinger, Supertrend vb. 48+ gösterge hesaplama
3. **AI Yorumlama**: Google Gemini ile Türkçe analiz üretme

## 2. Temizlenmiş Bağımlılıklar

### Kalan Paketler (pyproject.toml)
```
fastapi[standard]>=0.136.1
python-dotenv>=1.0.0
httpx>=0.24.1
apscheduler>=3.10.4
pandas>=2.0.0
pandas-ta>=0.3.14
sqlalchemy>=2.0.0
asyncpg>=0.29.0
aiosqlite>=0.20.0
redis>=7.4.0
google-generativeai>=0.8.0
```

### Kaldırılan Paketler
- `upstash-redis` — hiç kullanılmıyordu
- `requests-cache` — hiç kullanılmıyordu
- `requests-ratelimiter` — hiç kullanılmıyordu
- `yfinance` — işe yaramıyordu
- `tvdatafeed` — işe yaramıyordu

## 3. Dosya Yapısı (Güncel)

```
app/
├── main.py                    # FastAPI app, startup/shutdown, health check
├── core/
│   ├── config.py              # Settings (env vars)
│   ├── db.py                  # SQLAlchemy async engine (SQLite + PostgreSQL)
│   ├── redis_client.py        # Redis singleton (OVH Valkey)
│   ├── ticker_store.py        # tickers.json → Redis yükleme
│   ├── index_store.py         # indices.json (in-memory cache)
│   └── yfinance_client.py     # [SİLİNDİ]
├── models/
│   ├── instrument.py          # Pydantic: Instrument, StockQuote, StockDetail vb.
│   └── history.py             # SQLAlchemy: DailyPrice (OHLCV tablosu)
├── routers/
│   ├── instruments.py         # /instruments/* endpointleri
│   ├── ta.py                  # /api/v1/ta/* endpointleri
│   └── ta_advanced.py         # /api/v1/ta/advanced/* endpointleri
├── services/
│   ├── ta_engine.py           # Core TA: 48+ gösterge, pandas-ta ile
│   ├── advanced_ta.py         # Volume profile, S/R zones, market regime
│   ├── ceo_ta_report.py       # CEO/Board-level rapor
│   ├── summary_generator.py   # Türkçe analiz metni üretimi
│   ├── gemini_service.py      # Google Gemini AI entegrasyonu
│   └── fundamental_service.py # P/E ratio, finansal oranlar
├── sources/
│   ├── base.py                # Abstract BaseSource
│   ├── aa.py                  # AA Finans - BIST hisse fiyatları
│   ├── aa_market.py           # AA - Piyasa özeti (endeksler)
│   ├── oyak.py                # Oyak Yatırım - Enstrüman listesi
│   ├── isyatirim.py           # İş Yatırım - Tek sembol detayı
│   ├── frankfurter.py         # Forex EUR/USD/TRY
│   └── pool.py                # DataPool: multi-source + fallback
└── worker/
    ├── scheduler.py           # APScheduler: 30 dk refresh + gece sync
    └── historical.py          # IsYatirim'den tarihsel OHLCV + batch TA
```

## 4. Cloudflare Uyumluluk Analizi

### ✅ Çalışacak (Pyodide Built-in)
| Paket | Pyodide Versiyonu | Kullanım |
|---|---|---|
| `fastapi` | 0.136.1 | API framework |
| `httpx` | 0.28.1 | HTTP client (veri kaynakları) |
| `pandas` | 3.0.2 | Veri işleme |
| `numpy` | 2.4.3 | Sayısal hesaplama |
| `scipy` | 1.18.0 | İstatistik |
| `scikit-learn` | 1.8.0 | ML (beta hesaplama) |
| `sqlalchemy` | 2.0.48 | ORM (sadece core, driver değil) |
| `pydantic` | 2.12.5 | Schema validation |

### ⚠️ Sorunlu / Değişiklik Gerektiren
| Paket | Sorun | Çözüm |
|---|---|---|
| `pandas-ta` | Pyodide'da built-in değil, ama pure Python olabilir | Test edilmeli. Olmazsa: TA gösterge hesaplamalarını numpy/scipy ile yeniden yazmak veya harici servise taşımak |
| `redis` | Pyodide'da yok | KV binding (`self.env.KV`) ile değiştirilmeli |
| `apscheduler` | Threading gerektirir, Workers'da yok | Cloudflare Cron Triggers ile değiştirilmeli |
| `asyncpg` | C extension, Pyodide'da yok | D1 binding (`self.env.DB`) ile değiştirilmeli |
| `aiosqlite` | Pyodide'da yok (ama apsw var) | D1 binding ile değiştirilmeli |
| `google-generativeai` | Pyodide'da yok | Cloudflare Workers AI veya HTTP API ile değiştirilmeli |
| `python-dotenv` | .env dosyası Workers'da çalışmaz | Workers Secrets/Vars ile değiştirilmeli |

### ❌ Çalışmayacak
| Paket | Neden |
|---|---|
| `uvicorn` | Workers kendi HTTP sunucusunu kullanır |
| `threading` | Workers'da thread desteği yok |

## 5. Mimari Sorular

### 5.1 Veri Toplama (Scheduler)
Mevcut sistem: APScheduler arka planda çalışıyor
- Hafta içi 09:00-17:00 her 30 dakika: Canlı fiyatlar (AA, Oyak kaynakları)
- Her gece 00:05: Tarihsel OHLCV senkronizasyonu

**Soru**: Workers'da uzun süren arka plan işi nasıl çalıştırılır?
- Cron Triggers sadece belirli aralıklarla tetikleme yapar
- 610 ticker için tarihsel veri çekimi ~20 dakika sürüyor
- Bu iş Worker time limitini aşabilir

### 5.2 Veri Saklama
Mevcut: Redis (OVH Valkey) + PostgreSQL (OVH)

**Hedef**: Cloudflare KV + D1

**Soru**: KV'nin eventual consistency'i finansal veri için uygun mu?
- Fiyat verisi 30 saniyede bir güncelleniyor
- KV propagation süresi 60 saniye olabiliyor
- Bu gecikme kabul edilebilir mi?

### 5.3 API Endpoint'leri
30+ GET endpoint var. Tümü senkron olmayan (async) FastAPI handler.

**Soru**: FastAPI, Workers'da tam destekleniyor mu?
- Pyodide FastAPI'yı çalıştırabiliyor
- Ama `app.include_router()` ve dependency injection Workers'da nasıl çalışır?

### 5.4 Teknik Analiz Hesaplama
48+ pandas-ta gösterge çağrısı var (RSI, MACD, Bollinger, Supertrend, vb.)

**Soru**: pandas-ta Pyodide'da çalışıyor mu?
- Pure Python paketi,ama Pyodide built-in listesinde değil
- Alternatif: Tüm TA hesaplamalarını harici bir servise taşımak

### 5.5 Gemini AI Entegrasyonu
`google-generativeai` paketi Pyodide'da yok.

**Soru**: En iyi alternatif?
- Seçenek A: Cloudflare Workers AI (kendi modelleri)
- Seçenek B: Gemini HTTP API'ini httpx ile doğrudan çağır
- Seçenek C: Harici AI servisine proxy

## 6. Önerilen Migration Stratejisi

### Faz 1: Minimal Worker (Build hatasını çöz)
- `wrangler.jsonc` + `src/entry.py` oluştur
- `pywrangler` ile deploy
- Basit bir health check endpoint'i

### Faz 2: API Katmanını Taşı
- FastAPI app'i Workers'a uyarla
- Redis → KV, PostgreSQL → D1
- APScheduler → Cron Triggers

### Faz 3: Veri Pipeline'ı
- Canlı veri çekme (AA, Oyak, İş Yatırım) Worker'da kalır
- Tarihsel veri senkronizasyonu ayrı bir Worker veya harici servis

### Faz 4: TA + AI
- pandas-ta uyumluluğunu test et
- Gerekirse TA'yı harici servise taşı
- Gemini → Workers AI veya HTTP API

## 7. Cloudflare AI'dan İstenen Yanıtlar

1. **pandas-ta** Pyodide'da çalıştırılabilir mi? PyEmscripten wheel'i var mı?
2. **FastAPI router** ve dependency injection Workers'da tam destekleniyor mu?
3. 610 ticker için ~20 dakikalık tarihsel veri çekimi, Workers time limitini aşar mı? Aşarsa çözüm nedir?
4. **KV eventual consistency** finansal fiyat verisi için uygun mu? Daha güçlü garanti için Durable Objects gerekir mi?
5. **Cron Triggers** ile aynı Worker hem HTTP request hem scheduled job alabilir mi?
6. **google-generativeai** yerine en iyi alternatif hangisi? HTTP API (httpx ile) mi yoksa Workers AI mı?
7. `sqlalchemy` core (ORM olmadan) + D1 binding birlikte kullanılabilir mi?
