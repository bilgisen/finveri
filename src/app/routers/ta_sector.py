"""
Sector & Index Analysis Router.
Endpoints:
  GET /api/v1/ta/sector/{sector}/summary  → Sector performance summary
  GET /api/v1/ta/index/{code}/breadth     → Index breadth analysis
"""
import json
import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ta", tags=["Technical Analysis - Sector/Index"])


@router.get("/sector/{sector}/summary")
async def get_sector_summary(sector: str):
    """
    Layer: Public/Member | Role: Herkes
    Sector performance: median score, breadth, top/bottom performers.
    """
    try:
        from app.core.redis_client import get_redis
        from app.services.market_breadth import calculate_sector_performance

        r = get_redis()
        sector_key = sector.upper()

        # Build tickers_by_sector from tickers data
        raw_tickers = r.get("tickers:all")
        if not raw_tickers:
            raise HTTPException(status_code=503, detail="Ticker data not loaded")

        all_tickers = json.loads(raw_tickers)
        sector_tickers = []

        for code, info in all_tickers.items():
            if info.get("sector", "").upper() == sector_key:
                stock_raw = r.get(f"pool:bist_stocks:data")
                if stock_raw:
                    stocks = json.loads(stock_raw)
                    live = next(
                        (s for s in stocks if s.get("code", "").upper() == code),
                        None,
                    )
                    change = live.get("diff_percent") if live else None
                else:
                    change = None

                sector_tickers.append({
                    "code": code,
                    "change_pct": change,
                    "score": 50,
                    "above_sma_50": False,
                })

        if not sector_tickers:
            raise HTTPException(status_code=404, detail=f"No tickers found for sector: {sector}")

        sectors = calculate_sector_performance({sector_key: sector_tickers})
        result = sectors[0] if sectors else {}

        return {
            "sector": sector_key,
            "ticker_count": result.get("ticker_count", 0),
            "median_score": result.get("median_score", 50),
            "avg_return": result.get("mean_return"),
            "advancing_count": result.get("advancing_count", 0),
            "declining_count": result.get("declining_count", 0),
            "above_sma_50_pct": result.get("above_sma_50_pct", 50.0),
            "top_performers": [result.get("top_ticker")] if result.get("top_ticker") else [],
            "bottom_performers": [result.get("bottom_ticker")] if result.get("bottom_ticker") else [],
            "sector_regime": "Bullish" if (result.get("mean_return") or 0) > 0.5 else "Bearish" if (result.get("mean_return") or 0) < -0.5 else "Neutral",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Sector summary error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/index/{code}/breadth")
async def get_index_breadth(code: str):
    """
    Layer: Public/Member | Role: Herkes
    Index breadth: % above MAs, advance/decline, new highs/lows.
    Works with XU100, XU030, XBANK, XUSIN, etc.
    """
    try:
        from app.core.redis_client import get_redis
        from app.core.d1 import get_db, D1Repository
        from app.services.market_breadth import calculate_index_breadth

        index_code = code.upper()

        # Get index constituents from indices.json
        from app.core.index_store import get_index
        index_data = get_index(index_code)
        if not index_data:
            raise HTTPException(status_code=404, detail=f"Index not found: {index_code}")

        constituents = index_data.get("members", [])
        if not constituents:
            raise HTTPException(status_code=404, detail=f"No constituents for index: {index_code}")

        db = get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="D1 not available")

        repo = D1Repository(db)

        # Fetch historical prices for each constituent
        tickers_history = {}
        live_prices = {}

        r = get_redis()
        stock_raw = r.get("pool:bist_stocks:data")
        stocks_data = json.loads(stock_raw) if stock_raw else []

        for const in constituents:
            const_code = const.get("code") if isinstance(const, dict) else const
            if not const_code:
                continue

            rows = await repo.get_prices(const_code, limit=252)
            closes = [float(row["close"]) for row in reversed(rows)]
            if closes:
                tickers_history[const_code] = closes

            live = next(
                (s for s in stocks_data if s.get("code", "").upper() == const_code),
                None,
            )
            if live:
                live_prices[const_code] = float(live.get("last_price", 0) or 0)

        breadth = calculate_index_breadth(
            list(tickers_history.keys()),
            tickers_history,
            live_prices,
        )

        return {
            "index_code": index_code,
            "index_name": index_data.get("name", index_code),
            **breadth,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Index breadth error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
