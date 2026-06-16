import logging
import asyncio
from datetime import datetime, timezone, timedelta
import pandas as pd
from typing import List, Dict, Any, Optional
import httpx

from app.core.db import AsyncSessionLocal, engine
from app.models.history import DailyPrice
from app.core.ticker_store import get_all_tickers
from app.core.yfinance_client import get_ticker
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from tvDatafeed import TvDatafeed, Interval

logger = logging.getLogger(__name__)

# Initialize TvDatafeed globally without login (Anonymous)
try:
    tv = TvDatafeed()
except Exception as e:
    logger.error(f"Failed to initialize TvDatafeed: {e}")
    tv = None

def get_yfinance_symbol(ticker: str, info: dict) -> str:
    """Maps internal tickers to Yahoo Finance symbols."""
    market = info.get("market", "")
    if market == "BIST" or market == "BIST_INDEX":
        return f"{ticker}.IS"
    elif market == "FOREX":
        return f"{ticker}=X"
    elif market == "COMMODITY":
        if ticker == "XAUUSD": return "GC=F"
        if ticker == "BRENT": return "BZ=F"
        if ticker == "XAGUSD": return "SI=F"
        if ticker == "XPDUSD": return "PA=F"
    return ticker

def get_tv_symbol(ticker: str, info: dict) -> tuple[str, str]:
    """Maps internal tickers to TradingView (symbol, exchange)."""
    market = info.get("market", "")
    if market == "BIST" or market == "BIST_INDEX":
        return ticker, "BIST"
    elif market == "FOREX":
        # Usually EURUSD, TRYUSD etc. on FX or OANDA
        if ticker == "EURUSD": return "EURUSD", "FX"
        if ticker == "USDTRY": return "USDTRY", "FX"
        if ticker == "EURTRY": return "EURTRY", "FX"
        return ticker, "FX"
    elif market == "COMMODITY":
        if ticker == "XAUUSD": return "GOLD", "TVC"
        if ticker == "BRENT": return "UKOIL", "TVC"
        if ticker == "XAGUSD": return "SILVER", "TVC"
        if ticker == "XPDUSD": return "PALLADIUM", "TVC"
    return ticker, ""

async def fetch_yfinance(ticker: str, info: dict) -> Optional[List[Dict[str, Any]]]:
    """Primary: Fetches from yfinance."""
    yf_symbol = get_yfinance_symbol(ticker, info)
    loop = asyncio.get_event_loop()
    yf_ticker = get_ticker(yf_symbol)
    df = await loop.run_in_executor(None, lambda: yf_ticker.history(period="2y", interval="1d"))
    
    if df.empty:
        raise ValueError("yfinance returned empty dataframe")
        
    records = []
    for date_idx, row in df.iterrows():
        dt = date_idx.date() if hasattr(date_idx, 'date') else date_idx
        records.append(dict(
            ticker=ticker,
            date=dt,
            open=float(row['Open']),
            high=float(row['High']),
            low=float(row['Low']),
            close=float(row['Close']),
            volume=float(row['Volume'])
        ))
    return records

async def fetch_tvdatafeed(ticker: str, info: dict) -> Optional[List[Dict[str, Any]]]:
    """Fallback 1: Fetches from TradingView."""
    if not tv:
        raise ValueError("tvdatafeed not initialized")
        
    tv_symbol, exchange = get_tv_symbol(ticker, info)
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, lambda: tv.get_hist(symbol=tv_symbol, exchange=exchange, interval=Interval.in_daily, n_bars=500))
    
    if df is None or df.empty:
        raise ValueError("tvdatafeed returned empty dataframe")
        
    records = []
    for date_idx, row in df.iterrows():
        dt = date_idx.date() if hasattr(date_idx, 'date') else date_idx
        records.append(dict(
            ticker=ticker,
            date=dt,
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume'])
        ))
    return records

async def fetch_isyatirim(ticker: str, info: dict) -> Optional[List[Dict[str, Any]]]:
    """Fallback 2: Fetches from IsYatirim (Close-only mapping)."""
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=730) # 2 years
    
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
            
            # Since we only have Close, map Open/High/Low to Close to prevent TA engine from breaking completely
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
    """Executes the unbreakable fallback chain: tvdatafeed -> isyatirim -> yfinance."""
    logger.info(f"Starting historical sync for {ticker}...")
    records = None
    
    # 1. Primary: tvdatafeed
    try:
        records = await fetch_tvdatafeed(ticker, info)
        logger.debug(f"[{ticker}] SUCCESS via Primary (tvdatafeed)")
    except Exception as e:
        logger.warning(f"[{ticker}] Primary (tvdatafeed) failed: {e}. Trying Fallback 1 (isyatirim)...")
        
        # 2. Fallback 1: IsYatirim
        try:
            records = await fetch_isyatirim(ticker, info)
            logger.debug(f"[{ticker}] SUCCESS via Fallback 1 (isyatirim)")
        except Exception as e2:
            logger.warning(f"[{ticker}] Fallback 1 (isyatirim) failed: {e2}. Trying Fallback 2 (yfinance)...")
            
            # 3. Fallback 2: yfinance
            try:
                records = await fetch_yfinance(ticker, info)
                logger.debug(f"[{ticker}] SUCCESS via Fallback 2 (yfinance)")
            except Exception as e3:
                logger.error(f"[{ticker}] ALL SOURCES FAILED! Last error: {e3}")
                return

    if not records:
        return
        
    # Upsert into DB
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
