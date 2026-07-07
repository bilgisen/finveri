import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import httpx

from app.core.ticker_store import get_all_tickers

logger = logging.getLogger(__name__)


async def fetch_isyatirim(ticker: str, info: dict) -> Optional[List[Dict[str, Any]]]:
    """Fetches from IsYatirim (Close-only mapping)."""
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=730)

    from_str = from_date.strftime("%Y%m%d000000")
    to_str = now.strftime("%Y%m%d235959")

    url = f"https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/Common/ChartData.aspx/IndexHistoricalAll?period=1440&from={from_str}&to={to_str}&endeks={ticker}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    chart_data = data.get("data", [])
    if not chart_data:
        raise ValueError("IsYatirim returned no data")

    records = []
    for point in chart_data:
        if len(point) >= 2:
            ts_ms = point[0]
            close_val = point[1]
            dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).date()

            records.append(dict(
                ticker=ticker,
                date=dt,
                open=close_val,
                high=close_val,
                low=close_val,
                close=close_val,
                volume=0.0
            ))
    return records


async def fetch_historical_with_fallback(ticker: str, info: dict):
    """Fetches historical data from IsYatirim and saves to D1."""
    from app.core.d1 import get_db, D1Repository

    logger.info(f"Starting historical sync for {ticker}...")
    records = None

    try:
        records = await fetch_isyatirim(ticker, info)
        logger.debug(f"[{ticker}] SUCCESS via IsYatirim")
    except Exception as e:
        logger.error(f"[{ticker}] IsYatirim failed: {e}")
        return

    if not records:
        return

    db = get_db()
    if db is None:
        logger.error(f"[{ticker}] D1 database not available")
        return

    try:
        repo = D1Repository(db)
        await repo.batch_insert_prices(records)
        logger.info(f"Successfully saved {len(records)} OHLCV records for {ticker}")
    except Exception as e:
        logger.error(f"Failed to save records for {ticker} to D1: {e}")


async def sync_all_history():
    """Sync historical OHLCV data for all supported tickers."""
    from app.core.d1 import get_db
    if get_db() is None:
        logger.error("D1 database not available, skipping historical sync")
        return

    tickers = get_all_tickers()
    if not tickers:
        logger.warning("No tickers found, skipping historical sync")
        return

    for code, info in tickers.items():
        await fetch_historical_with_fallback(code, info)
        await asyncio.sleep(1)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(sync_all_history())
