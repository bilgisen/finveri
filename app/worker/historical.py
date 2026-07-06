import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import httpx

try:
    from app.core.db import AsyncSessionLocal, engine
    from app.models.history import DailyPrice
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    _HAS_DB = True
except ImportError:
    _HAS_DB = False

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

async def fetch_historical_with_fallback(session, ticker: str, info: dict):
    """Fetches historical data from IsYatirim."""
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

    try:
        if "postgres" in str(engine.url):
            stmt = pg_insert(DailyPrice).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=['ticker', 'date'],
                set_=dict(
                    open=stmt.excluded.open,
                    high=stmt.excluded.high,
                    low=stmt.excluded.low,
                    close=stmt.excluded.close,
                    volume=stmt.excluded.volume
                )
            )
        else:
            stmt = sqlite_insert(DailyPrice).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=['ticker', 'date'],
                set_=dict(
                    open=stmt.excluded.open,
                    high=stmt.excluded.high,
                    low=stmt.excluded.low,
                    close=stmt.excluded.close,
                    volume=stmt.excluded.volume
                )
            )

        await session.execute(stmt)
        await session.commit()
        logger.info(f"Successfully saved {len(records)} OHLCV records for {ticker}")
    except Exception as e:
        logger.error(f"Failed to save records for {ticker} to DB: {e}")


async def batch_calculate_all_ta():
    """Calculates TA for all tickers and caches results in Redis."""
    from app.services.ta_engine import generate_llm_summary
    from app.core.redis_client import get_redis
    import json
    
    tickers = get_all_tickers()
    r = get_redis()
    
    logger.info(f"Starting batch TA calculation for {len(tickers)} tickers...")
    
    success_count = 0
    for code in tickers.keys():
        try:
            # This will calculate and return the full TA result
            result = await generate_llm_summary(code)
            if "error" not in result:
                # Cache for 24 hours (86400 seconds)
                cache_key = f"ta_data:{code}"
                r.setex(cache_key, 86400, json.dumps(result))
                success_count += 1
            
            # Small delay to prevent CPU/IO spikes
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Batch TA failed for {code}: {e}")
            
    logger.info(f"Batch TA calculation completed. Successfully cached {success_count}/{len(tickers)} tickers.")

async def sync_all_history():
    """Sync historical OHLCV data for all supported tickers."""
    from app.core.ticker_store import load_tickers
    load_tickers() # Load from JSON to Redis first
    
    tickers = get_all_tickers()
    
    async with AsyncSessionLocal() as session:
        for code, info in tickers.items():
            await fetch_historical_with_fallback(session, code, info)
            await asyncio.sleep(1) # Small delay to avoid rate limits
            
    # Run batch TA calculation after history sync
    await batch_calculate_all_ta()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(sync_all_history())
