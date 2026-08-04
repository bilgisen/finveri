"""
Historical data sync endpoints — triggers D1 population from Is Yatirim.
"""
import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sync", tags=["Data Sync"])


@router.post("/historical/{ticker}")
async def sync_ticker_history(ticker: str) -> Dict[str, Any]:
    """Sync historical OHLCV data for a single ticker to D1."""
    from app.worker.historical import fetch_historical_with_fallback
    ticker_upper = ticker.upper()
    try:
        count = await fetch_historical_with_fallback(ticker_upper, {})
        return {"status": "ok", "ticker": ticker_upper, "records_inserted": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/historical/all")
async def sync_all_history() -> Dict[str, Any]:
    """Sync historical data for ALL tickers to D1."""
    from app.core.ticker_store import get_all_tickers
    from app.worker.historical import fetch_historical_with_fallback
    import asyncio

    tickers = get_all_tickers()
    if not tickers:
        raise HTTPException(status_code=400, detail="No tickers found")
    count = 0
    errors = []
    for code in list(tickers.keys())[:100]:
        try:
            c = await fetch_historical_with_fallback(code, {})
            count += c
            await asyncio.sleep(0.3)
        except Exception as e:
            errors.append(f"{code}: {e}")
    return {"status": "ok", "records_inserted": count, "errors": errors, "total_tickers": len(tickers)}


@router.post("/refresh")
async def sync_refresh(history: bool = False) -> Dict[str, Any]:
    """
    Veri havuzunu (bist_stocks, market_summary, instruments) senkron tazeler.
    Endeks bileşenleri KAP'tan seed'li ve statiktir (indices:catalog KV'de;
    Mynet kullanılmaz).
    """
    from app.worker.workers_refresh import refresh_all
    results = await refresh_all(include_indices=False, include_history=history)
    return {"status": "ok", "results": results}


@router.post("/backfill")
async def sync_backfill(batch_size: int = 15) -> Dict[str, Any]:
    """
    Sadece tarihsel OHLCV backfill'inin bir batch'ini çalıştırır (havuz
    refresh'ine dokunmaz). CPU limitlerine takılmamak için küçük batch'ler
    kullanılır; ilerleme KV'daki `history:cursor` ile takip edilir.
    """
    from app.worker.historical import sync_history_batch
    result = await sync_history_batch(batch_size=min(batch_size, 30))
    return {"status": "ok", "result": result}


@router.get("/status")
async def sync_status() -> Dict[str, Any]:
    """Check how many tickers have historical data in D1."""
    from app.core.d1 import get_db, D1Repository
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="D1 not available")
    repo = D1Repository(db)
    from app.core.ticker_store import get_all_tickers
    tickers = get_all_tickers()
    total = len(tickers) if tickers else 0
    sample_count = 0
    if tickers:
        first_code = list(tickers.keys())[0]
        sample_count = await repo.get_price_count(first_code)
    return {
        "total_tickers": total,
        "sample_ticker": list(tickers.keys())[0] if tickers else None,
        "sample_row_count": sample_count,
    }
