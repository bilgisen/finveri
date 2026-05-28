from fastapi import APIRouter, Query, HTTPException
from typing import List
from app.services.ta_engine import calculate_indicators
from app.core.ticker_store import get_all_tickers

router = APIRouter(prefix="/api/v1/ta", tags=["Technical Analysis"])

@router.get("/{ticker}")
async def get_technical_analysis(
    ticker: str, 
    indicators: List[str] = Query(default=["rsi", "macd", "sma_20", "sma_50"], description="List of indicators to calculate")
):
    """
    Returns calculated technical indicators for the requested ticker.
    Uses historical daily close prices to compute indicators on the fly.
    """
    ticker_upper = ticker.upper()
    tickers = get_all_tickers()
    
    if ticker_upper not in tickers:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker_upper} not found in supported list.")
        
    result = await calculate_indicators(ticker_upper, indicators)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return {
        "ticker": ticker_upper,
        "indicators": result
    }

@router.get("/summary/{ticker}")
async def get_ta_summary(ticker: str):
    """
    Returns an LLM-friendly summary of the current Technical Analysis status.
    Suitable for direct injection into Chatbot prompts.
    Uses Redis caching to support Ultimate Level high-traffic volume.
    """
    from app.services.ta_engine import generate_llm_summary
    from app.core.redis_client import get_redis
    import json
    
    ticker_upper = ticker.upper()
    tickers = get_all_tickers()
    
    if ticker_upper not in tickers:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker_upper} not found in supported list.")
        
    redis_client = get_redis()
    cache_key = f"ta_summary:{ticker_upper}"
    
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache read failed for TA summary: {e}")
        
    result = await generate_llm_summary(ticker_upper)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    try:
        # Cache for 1 hour (3600 seconds)
        redis_client.setex(cache_key, 3600, json.dumps(result))
    except Exception as e:
        logger.warning(f"Redis cache write failed for TA summary: {e}")
        
    return result
