from fastapi import APIRouter, Query, HTTPException
from typing import List
import logging

from app.services.ta_engine import calculate_indicators
from app.core.ticker_store import get_all_tickers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ta", tags=["Technical Analysis"])

@router.get("/{ticker}")
async def get_technical_analysis(
    ticker: str, 
    indicators: List[str] = Query(default=["rsi", "macd", "sma_20", "sma_50", "supertrend", "bbands"], description="List of indicators to calculate")
):
    """
    Returns calculated technical indicators for the requested ticker.
    Uses Redis cache if available, otherwise calculates on the fly.
    """
    from app.core.redis_client import get_redis
    import json
    
    ticker_upper = ticker.upper()
    r = get_redis()
    cache_key = f"ta_data:{ticker_upper}"
    
    # Try to get from batch cache first
    try:
        cached = r.get(cache_key)
        if cached:
            full_data = json.loads(cached)
            # Filter indicators if needed, but for now return all common ones
            return {
                "ticker": ticker_upper,
                "indicators": full_data,
                "source": "cache"
            }
    except Exception as e:
        logger.warning(f"Redis read failed for {ticker_upper}: {e}")

    # Fallback to on-the-fly
    result = await calculate_indicators(ticker_upper, indicators)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return {
        "ticker": ticker_upper,
        "indicators": result,
        "source": "live"
    }

@router.get("/summary/{ticker}")
async def get_ta_summary(ticker: str):
    """
    Returns an LLM-friendly summary of the current Technical Analysis status.
    Uses Redis caching to support high-traffic volume.
    """
    from app.services.ta_engine import generate_llm_summary
    from app.core.redis_client import get_redis
    import json
    
    ticker_upper = ticker.upper()
    r = get_redis()
    cache_key = f"ta_data:{ticker_upper}"
    
    try:
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis read failed for {ticker_upper}: {e}")
        
    result = await generate_llm_summary(ticker_upper)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    try:
        # Cache for 24 hours
        r.setex(cache_key, 86400, json.dumps(result))
    except Exception as e:
        logger.warning(f"Redis write failed for {ticker_upper}: {e}")
        
    return result


@router.get("/ceo-report/{ticker}")
async def get_ceo_report(ticker: str):
    """
    CEO / Yönetim Kurulu seviyesinde profesyonel teknik analiz raporu.
    
    Executive summary, detaylı göstergeler, senaryo bazlı analiz ve risk değerlendirmesi içerir.
    Premium üyelere özeldir.
    """
    from app.services.ceo_ta_report import generate_ceo_report
    from app.core.redis_client import get_redis
    import json
    
    ticker_upper = ticker.upper()
    r = get_redis()
    cache_key = f"ceo_report:{ticker_upper}"
    
    # Redis cache'den kontrol et (1 saat TTL)
    try:
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis read failed for CEO report {ticker_upper}: {e}")
    
    result = generate_ceo_report(ticker_upper)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # Cache'e kaydet (1 saat)
    try:
        r.setex(cache_key, 3600, json.dumps(result))
    except Exception as e:
        logger.warning(f"Redis write failed for CEO report {ticker_upper}: {e}")
    
    return result
