# finveri

**Professional-Grade Financial Data & Technical Analysis API**

A FastAPI-powered real-time financial data service featuring institutional-level technical analysis for Turkish markets (BIST), commodities, and forex.

## 🎯 Features

### Core Capabilities
- **Real-time Market Data**: BIST stocks, indices, commodities, forex
- **Multi-Source Fallback**: tvdatafeed → isyatirim → yfinance
- **Historical OHLCV**: 2-year daily data with automatic nightly sync
- **Redis Caching**: High-performance caching layer (Upstash + OVH)
- **PostgreSQL Storage**: Scalable historical data persistence

### 🚀 Advanced Technical Analysis (v2.0)

#### **Volume Profile Analysis**
- POC (Point of Control) - Highest volume price level
- Value Area (70% volume concentration)
- Institutional support/resistance identification

#### **Market Regime Detection**
- Strong Trend / Weak Trend / Range Bound / Choppy classification
- Automatic strategy recommendations (Trend Following vs Mean Reversion)
- Volatility regime analysis (High / Normal / Low)

#### **Liquidity Voids (Fair Value Gaps)**
- Unfilled price gaps detection
- Price magnet analysis
- Historical gap tracking

#### **Multi-Method Support/Resistance**
- Swing highs/lows
- Volume Profile levels (POC, VAH, VAL)
- Bollinger Bands
- Psychological levels (round numbers)
- Strength scoring (0-100) for each level

#### **Enhanced Technical Scoring**
- Regime-aware dynamic weighting
- Score components: Trend, Momentum, Volume
- Signal quality indicators (✓ Bullish, ✗ Bearish, ⊙ Neutral)
- Confidence levels (High / Medium / Low)

### 📊 Comprehensive Indicators
RSI, MACD, Stochastic, Bollinger Bands, ADX, ATR, Supertrend, Ichimoku Cloud, Parabolic SAR, MFI, OBV, VWAP, EMA, SMA

### 🔥 Real-time Indicator Overlay
Seamlessly merges live BIST data with historical OHLCV for up-to-the-second analysis

## 🚀 Quick Start

### Start the development server

```bash
uv run fastapi dev
```

Visit http://localhost:8000/docs for interactive API documentation

## 📡 API Endpoints

### Basic Technical Analysis
- `GET /api/v1/ta/{ticker}` - Calculate specific indicators
- `GET /api/v1/ta/summary/{ticker}` - **Complete TA summary with chatbot-ready context**

### Advanced Technical Analysis (NEW)
- `GET /api/v1/ta/advanced/regime/{ticker}` - Market regime & strategy
- `GET /api/v1/ta/advanced/volume-profile/{ticker}` - Volume Profile (POC, VAH, VAL)
- `GET /api/v1/ta/advanced/liquidity-voids/{ticker}` - Unfilled gaps
- `GET /api/v1/ta/advanced/sr-zones/{ticker}` - Multi-method support/resistance
- `GET /api/v1/ta/advanced/full-context/{ticker}` - **All analyses in one call (optimized for chatbots)**

### System
- `GET /health` - Health check with Redis & source status
- `POST /admin/refresh` - Manual data refresh
- `POST /admin/reload-tickers` - Reload ticker configuration

## 🤖 Chatbot Integration

The `/api/v1/ta/summary/{ticker}` and `/api/v1/ta/advanced/full-context/{ticker}` endpoints return rich, multi-layered context perfect for LLM integration:

```json
{
  "ticker": "THYAO",
  "close": 385.50,
  "score": 70,
  "confidence": "High",
  "market_regime": {
    "regime": "Strong Trend",
    "trend_direction": "Bullish",
    "recommended_strategy": "Trend Following: Use MA crossovers..."
  },
  "volume_profile": {
    "poc": 378.20,
    "value_area_high": 395.00,
    "value_area_low": 375.00
  },
  "support_resistance_zones": { ... },
  "liquidity_voids": [ ... ],
  "llm_summary_prompt": "=== THYAO TEKNİK ANALİZ RAPORU ===\n\n📊 GENEL GÖRÜNÜM:\n..."
}
```

See `ADVANCED_TA_IMPLEMENTATION.md` for complete integration guide.

## 📁 Project Structure

```
finveri/
├── app/
│   ├── core/              # Configuration, DB, Redis, caching
│   ├── models/            # SQLAlchemy models
│   ├── routers/           # API endpoints
│   │   ├── instruments.py # Market data endpoints
│   │   ├── ta.py          # Basic TA endpoints
│   │   └── ta_advanced.py # Advanced TA endpoints (NEW)
│   ├── services/          # Business logic
│   │   ├── ta_engine.py   # Core TA calculations
│   │   ├── advanced_ta.py # Advanced TA algorithms (NEW)
│   │   └── summary_generator.py
│   ├── sources/           # Data source adapters
│   └── worker/            # Background tasks & schedulers
├── data/                  # Static data (tickers, indices)
├── main.py                # Application entry point
└── pyproject.toml         # Dependencies
```

## 🔧 Configuration

Environment variables (`.env`):
```env
# Redis (Upstash)
UPSTASH_REDIS_REST_URL=your_url
UPSTASH_REDIS_REST_TOKEN=your_token

# Database (PostgreSQL recommended, SQLite fallback)
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
OVH_SSL_CERT=ca.pem

# Gemini API (optional for AI-powered summaries)
GEMINI_API_KEY=your_key

# Worker Settings
FETCH_INTERVAL_SECONDS=300
CACHE_TTL_SECONDS=345600
```

## 🧪 Testing

```bash
# Test advanced TA features
python test_advanced_ta.py

# Test specific ticker
python -c "import asyncio; from app.services.ta_engine import generate_llm_summary; asyncio.run(generate_llm_summary('THYAO'))"
```

## 📊 Performance

- **Volume Profile Calculation**: ~50ms per ticker
- **Market Regime Detection**: ~30ms per ticker
- **Full Context Endpoint**: ~200ms per ticker
- **Redis Caching**: 24 hours TTL with automatic nightly refresh
- **Batch TA Calculation**: All tickers processed nightly at 00:05

## 📚 Documentation

- `ADVANCED_TA_IMPLEMENTATION.md` - Complete feature guide & usage examples
- `CHANGELOG_ADVANCED_TA.md` - Detailed changelog for v2.0
- Interactive API docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🔜 Roadmap

### Phase 2 (2-4 weeks)
- Harmonic Pattern Recognition (Gartley, Butterfly, Bat, Crab)
- Risk-Adjusted Metrics (Sharpe, Sortino, Calmar ratios)
- Kelly Criterion Position Sizing
- Correlation Matrix

### Phase 3 (1-2 months)
- ML Ensemble Predictions (Random Forest + Gradient Boosting)
- Mean Reversion Testing (ADF, Half-life)
- Batch Processing Optimization (Multiprocessing)
- WebSocket Real-time Updates

## 📝 Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [pandas-ta Documentation](https://github.com/twopirllc/pandas-ta)
- [Technical Analysis Theory](https://www.investopedia.com/technical-analysis-4689657)
