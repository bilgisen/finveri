"""
Workers-optimized historical OHLCV sync.
Fetches close-only data from Is Yatirim ChartData endpoint, saves to D1.
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

_CHART_URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/ChartData.aspx/IndexHistoricalAll"
_CHART_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.isyatirim.com.tr/",
}


async def fetch_isyatirim(ticker: str) -> Optional[List[Dict[str, Any]]]:
    """Fetches 2 years of daily (period=1440) close data from Is Yatirim."""
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=730)
    from_str = from_date.strftime("%Y%m%d000000")
    to_str = now.strftime("%Y%m%d235959")
    url = f"{_CHART_URL}?period=1440&from={from_str}&to={to_str}&endeks={ticker}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=_CHART_HEADERS)
        resp.raise_for_status()
        data = resp.json()

    chart_data = data.get("data", [])
    if not chart_data:
        raise ValueError(f"IsYatirim returned no data for {ticker}")

    records = []
    for point in chart_data:
        if len(point) >= 2:
            ts_ms = point[0]
            close_val = point[1]
            dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).date()
            records.append(dict(
                ticker=ticker,
                date=str(dt),
                open=close_val,
                high=close_val,
                low=close_val,
                close=close_val,
                volume=0.0
            ))
    return records


async def fetch_historical_with_fallback(ticker: str, info: dict) -> int:
    """Fetches historical data from IsYatirim and saves to D1. Returns record count."""
    from app.core.d1 import get_db, D1Repository

    records = await fetch_isyatirim(ticker)
    if not records:
        return 0

    db = get_db()
    if db is None:
        raise RuntimeError("D1 database not available")

    repo = D1Repository(db)
    await repo.batch_insert_prices(records)
    count = len(records)
    logger.info(f"Saved {count} OHLCV records for {ticker}")
    return count


async def sync_all_history():
    """Sync historical OHLCV data for all supported tickers."""
    from app.core.d1 import get_db
    if get_db() is None:
        raise RuntimeError("D1 database not available")

    tickers = {}
    # Fallback to KV-based ticker store for Workers
    try:
        from app.core.workers_cache import _cache
        all_tickers = _cache.get("tickers:all")
        if all_tickers:
            import json
            tickers = json.loads(all_tickers)
    except Exception:
        pass

    if not tickers:
        try:
            from app.core.ticker_store import get_all_tickers
            tickers = get_all_tickers()
        except Exception:
            pass

    if not tickers:
        logger.warning("No tickers found, skipping historical sync")
        return

    codes = list(tickers.keys())[:300]  # Limit for safety
    sem = asyncio.Semaphore(10)
    total = 0

    async def fetch_one(code):
        async with sem:
            try:
                return await fetch_historical_with_fallback(code, {})
            except Exception as e:
                logger.warning(f"[{code}] historical sync failed: {e}")
                return 0

    results = await asyncio.gather(*[fetch_one(code) for code in codes])
    total = sum(results)
    logger.info(f"Historical sync complete: {total} records across {len(codes)} tickers")


def _load_codes(cache) -> list:
    """Load ticker codes from KV cache, falling back to bundled data."""
    try:
        if cache:
            raw = cache.get("tickers:codes")
            if raw:
                import json
                codes = json.loads(raw)
                if codes:
                    return codes
    except Exception:
        pass
    try:
        from app.core.tickers_data import TICKERS
        return list(TICKERS.keys())
    except Exception:
        return []


async def sync_history_batch(batch_size: int = 60) -> dict:
    """KV cursor tabanlı tarihsel backfill.

    Her çağrıda `batch_size` hisse işlenir; ilerleme KV'daki `history:cursor`
    anahtarında tutulur. Bir tam tur bitince cursor sıfırlanır ve her cron'da
    yalnızca eksik verili (>=250 satırı olmayan) hisseler tekrar çekilir —
    upsert idempotent olduğu için güvenlidir.
    """
    from app.core.d1 import get_db, D1Repository
    from app.core.workers_cache import get_cache, is_ready

    db = get_db()
    if db is None:
        return {"status": "no_db"}

    cache = get_cache() if is_ready() else None
    codes = _load_codes(cache)
    if not codes:
        return {"status": "no_tickers", "total_tickers": 0}

    cursor = 0
    if cache:
        try:
            cursor = int(cache.get("history:cursor") or 0)
        except (TypeError, ValueError):
            cursor = 0

    if cursor >= len(codes):
        cursor = 0

    batch = codes[cursor:cursor + batch_size]
    if not batch:
        return {"status": "no_batch", "total_tickers": len(codes)}

    repo = D1Repository(db)
    sem = asyncio.Semaphore(10)
    processed = 0
    skipped = 0
    failed = 0

    async def fetch_one(code):
        nonlocal processed, skipped, failed
        async with sem:
            try:
                if await repo.get_price_count(code) >= 250:
                    skipped += 1
                    return
                count = await fetch_historical_with_fallback(code, {})
                if count > 0:
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.warning("[history-batch] %s: %s", code, e)

    await asyncio.gather(*[fetch_one(code) for code in batch])

    new_cursor = cursor + len(batch)
    if new_cursor >= len(codes):
        new_cursor = 0
        if cache:
            cache.set("history:completed", datetime.now(timezone.utc).isoformat(), ex=604800)
    if cache:
        cache.set("history:cursor", str(new_cursor), ex=604800)
        cache.set("history:batch_size", str(batch_size), ex=604800)

    logger.info(
        "history-batch: %d processed, %d skipped, %d failed (cursor %d/%d)",
        processed, skipped, failed, new_cursor, len(codes),
    )
    return {
        "status": "ok",
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "cursor": new_cursor,
        "batch_size": len(batch),
        "total_tickers": len(codes),
    }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(sync_all_history())
