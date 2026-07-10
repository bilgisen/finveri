"""
Workers-specific data refresh.

Fetches data from sources sequentially (no threads) and stores
in the KV-backed cache. Called from entry.py at startup and from cron.
"""
import json
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.workers_cache import cache_set, get_cache, is_ready

logger = logging.getLogger(__name__)


async def refresh_all() -> dict[str, bool]:
    """Fetch all data types and store in KV cache. Returns per-type status."""
    results = {}
    cache = get_cache() if is_ready() else None

    # instruments: Oyak
    try:
        from app.sources.oyak import OyakSource
        source = OyakSource()
        result = source.fetch()
        if result.success and result.data:
            _write_to_cache(cache, "instruments", result)
            results["instruments"] = True
            logger.info("instruments: %d records from Oyak", len(result.data))
        else:
            results["instruments"] = False
            logger.warning("instruments: Oyak failed: %s", result.error)
    except Exception as e:
        results["instruments"] = False
        logger.error("instruments: %s", e, exc_info=True)

    # Load tickers into KV store so AASource can find them
    _load_tickers(cache)

    # bist_stocks: AA (async with limited concurrency)
    try:
        from app.sources.aa import AASource
        source = AASource()
        result = await source.async_fetch(max_concurrent=20)
        if result.success and result.data:
            _write_to_cache(cache, "bist_stocks", result)
            results["bist_stocks"] = True
            logger.info("bist_stocks: %d records from AA", len(result.data))
            # Save daily OHLCV snapshot to D1 for volume profile
            await _save_daily_ohlcv(result.data)
        else:
            results["bist_stocks"] = False
            logger.warning("bist_stocks: AA failed: %s", result.error)
    except Exception as e:
        results["bist_stocks"] = False
        logger.error("bist_stocks: %s", e, exc_info=True)

    # market_summary: AA
    try:
        from app.sources.aa_market import AAMarketSummarySource
        source = AAMarketSummarySource()
        result = source.fetch()
        if result.success and result.data:
            _write_to_cache(cache, "market_summary", result)
            results["market_summary"] = True
            logger.info("market_summary: %d records from AA", len(result.data))
        else:
            results["market_summary"] = False
            logger.warning("market_summary: AA failed: %s", result.error)
    except Exception as e:
        results["market_summary"] = False
        logger.error("market_summary: %s", e, exc_info=True)

    return results


def _load_tickers(cache) -> int:
    """Load tickers into KV store from bundled data module."""
    try:
        from app.core.tickers_data import TICKERS
        tickers = TICKERS
        pipe = cache.pipeline()
        pipe.set("tickers:all", json.dumps(tickers))
        pipe.set("tickers:codes", json.dumps(list(tickers.keys())))
        for code, data in tickers.items():
            pipe.set(f"tickers:code:{code}", json.dumps(data))
        pipe.execute()
        logger.info("Loaded %d tickers into KV store", len(tickers))
        return len(tickers)
    except Exception as e:
        logger.warning("Failed to load tickers: %s", e)
        return 0


async def _save_daily_ohlcv(data: list) -> None:
    """Save today's OHLCV snapshot to D1 for each ticker."""
    try:
        from app.core.d1 import get_db, D1Repository
        db = get_db()
        if db is None:
            return
        repo = D1Repository(db)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        records = []
        for item in data:
            code = item.get("code") or item.get("ticker") or item.get("symbol")
            if not code:
                continue
            close = item.get("last_price") or item.get("close") or item.get("last")
            if close is None:
                continue
            records.append(dict(
                ticker=code.upper(),
                date=today,
                open=float(item.get("first_price", close) or close),
                high=float(item.get("high_price", close) or close),
                low=float(item.get("low_price", close) or close),
                close=float(close),
                volume=float(item.get("volume", 0) or 0),
            ))
        if records:
            await repo.batch_insert_prices(records)
            logger.info("Saved %d daily OHLCV snapshots to D1", len(records))
    except Exception as e:
        logger.warning("Failed to save daily OHLCV: %s", e)


def _write_to_cache(cache, data_type: str, result) -> None:
    """Normalize and write data to KV cache."""
    ttl = settings.CACHE_TTL_SECONDS
    now = result.fetched_at.isoformat() if result.fetched_at else datetime.now(timezone.utc).isoformat()
    clean = [{k: v for k, v in item.items() if k != "_raw"} for item in result.data]

    pipe = cache.pipeline()
    pipe.set(f"pool:{data_type}:data", json.dumps(clean), ex=ttl)
    pipe.set(f"pool:{data_type}:last_updated", now, ex=ttl)
    pipe.execute()
