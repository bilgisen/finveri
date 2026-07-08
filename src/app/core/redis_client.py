"""
Redis client — DEV ONLY.

In Workers mode, all cache ops go through workers_cache (KV-backed).
This module exists only for local development convenience.
If workers_cache is initialized, get_redis() delegates to it.
"""
import logging

from app.core.workers_cache import get_cache, is_ready

logger = logging.getLogger(__name__)
_client = None


def get_redis():
    global _client
    if _client is None:
        if is_ready():
            _client = get_cache()
            logger.info("Using Workers KV cache")
        else:
            logger.warning("Redis not available, using in-memory fallback")
            _client = get_cache()
    return _client


def ping_redis() -> bool:
    try:
        return get_redis().ping() is True
    except Exception as e:
        logger.error("ping hatası: %s", e)
        return False
