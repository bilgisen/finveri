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


@router.get("/sector/summary")
async def get_all_sectors_summary(period: str = "daily"):
    """
    Tüm sektörler için periyot bazında performans özeti.
    Her sektörün ortalama getirisi + top/bottom hisseleri.
    period: daily | weekly | monthly | yearly | ytd
    """
    try:
        from app.core.redis_client import get_redis
        from app.services.periodic_movers import compute_periodic_movers

        r = get_redis()
        raw_tickers = r.get("tickers:all")
        stock_raw = r.get("pool:bist_stocks:data")
        if not raw_tickers or not stock_raw:
            raise HTTPException(status_code=503, detail="Market data not loaded")

        all_tickers = json.loads(raw_tickers)
        stocks_data = json.loads(stock_raw)

        sector_codes: dict[str, list[str]] = {}
        for code, info in all_tickers.items():
            sec = (info.get("sector") or "").upper()
            if sec:
                sector_codes.setdefault(sec, []).append(code.upper())

        rows = []
        for sec, codes in sector_codes.items():
            code_set = set(codes)
            sector_stocks = [s for s in stocks_data if (s.get("code") or "").upper() in code_set]
            if not sector_stocks:
                continue
            top = compute_periodic_movers(sector_stocks, period=period, direction="top", limit=5)
            bottom = compute_periodic_movers(sector_stocks, period=period, direction="bottom", limit=5)
            values = [row["change_pct"] for row in top + bottom if row.get("change_pct") is not None]
            avg = round(sum(values) / len(values), 2) if values else None
            rows.append({
                "sector": sec,
                "period": (period or "daily").lower(),
                "ticker_count": len(sector_stocks),
                "avg_return": avg,
                "top_performers": top,
                "bottom_performers": bottom,
            })

        rows.sort(key=lambda x: (x["avg_return"] is not None, x["avg_return"]), reverse=True)
        return {"period": (period or "daily").lower(), "total_sectors": len(rows), "sectors": rows}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("All-sector summary error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector/{sector}/summary")
async def get_sector_summary(sector: str, period: str = "daily"):
    """
    Layer: Public/Member | Role: Herkes
    Sector performance: median score, breadth, top/bottom performers.
    period: daily | weekly | monthly | yearly | ytd
    """
    try:
        from app.core.redis_client import get_redis
        from app.services.market_breadth import calculate_sector_performance
        from app.services.periodic_movers import compute_periodic_movers

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

        # Per-period top/bottom performers
        stock_raw = r.get("pool:bist_stocks:data")
        stocks_data = json.loads(stock_raw) if stock_raw else []
        sector_codes = {t["code"].upper() for t in sector_tickers}
        sector_stocks = [s for s in stocks_data if (s.get("code") or "").upper() in sector_codes]

        top = compute_periodic_movers(sector_stocks, period=period, direction="top", limit=5)
        bottom = compute_periodic_movers(sector_stocks, period=period, direction="bottom", limit=5)

        # Periodic average return for the sector
        avg_returns = {}
        for p in ("daily", "weekly", "monthly", "yearly"):
            rows = compute_periodic_movers(sector_stocks, period=p, direction="top", limit=len(sector_stocks))
            rows += compute_periodic_movers(sector_stocks, period=p, direction="bottom", limit=len(sector_stocks))
            seen = {}
            for row in rows:
                seen[row["code"]] = row["change_pct"]
            values = list(seen.values())
            avg_returns[p] = round(sum(values) / len(values), 2) if values else None

        return {
            "sector": sector_key,
            "period": (period or "daily").lower(),
            "ticker_count": result.get("ticker_count", len(sector_tickers)),
            "median_score": result.get("median_score", 50),
            "avg_return": result.get("mean_return"),
            "avg_returns": avg_returns,
            "advancing_count": result.get("advancing_count", 0),
            "declining_count": result.get("declining_count", 0),
            "above_sma_50_pct": result.get("above_sma_50_pct", 50.0),
            "top_performers": top,
            "bottom_performers": bottom,
            "sector_regime": "Bullish" if (result.get("mean_return") or 0) > 0.5 else "Bearish" if (result.get("mean_return") or 0) < -0.5 else "Neutral",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Sector summary error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/index/{code}/performance")
async def get_index_performance(code: str, period: str = "monthly"):
    """
    Endeks bileşenleri arasında periyot bazında performans sıralaması.
    period: daily | weekly | monthly | yearly | ytd
    """
    try:
        from app.core.redis_client import get_redis
        from app.services.periodic_movers import compute_periodic_movers

        from app.core.index_store import get_index
        index_data = get_index(code)
        if not index_data:
            raise HTTPException(status_code=404, detail=f"Index not found: {code}")

        members = index_data.get("members") or []
        member_codes = {str(m.get("code") if isinstance(m, dict) else m).upper() for m in members if m}
        if not member_codes:
            raise HTTPException(status_code=404, detail=f"No constituents for index: {code}")

        r = get_redis()
        raw = r.get("pool:bist_stocks:data")
        if not raw:
            raise HTTPException(status_code=503, detail="BIST fiyat verisi henüz cache'e alınmadı.")
        stocks = [s for s in json.loads(raw) if (s.get("code") or "").upper() in member_codes]

        top = compute_periodic_movers(stocks, period=period, direction="top", limit=10)
        bottom = compute_periodic_movers(stocks, period=period, direction="bottom", limit=10)

        return {
            "index_code": code.upper(),
            "index_name": index_data.get("name", code),
            "period": (period or "monthly").lower(),
            "member_count": len(member_codes),
            "top_performers": top,
            "bottom_performers": bottom,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Index performance error: %s", e)
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
            [c.get("code") if isinstance(c, dict) else c for c in constituents],
            tickers_history,
            live_prices,
            total_constituents=len(constituents),
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
