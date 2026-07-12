"""
Cache Validation & Warming Module.
Manages TTL strategies, staleness checks, and proactive cache warming.
Integrates with workers_cache.py for KV-backed caching.
"""
from __future__ import annotations
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Market hours: Istanbul (UTC+3)
MARKET_OPEN_HOUR = 9
MARKET_CLOSE_HOUR = 17
_WEEKEND_DAYS = {5, 6}  # Saturday, Sunday


def is_market_open() -> bool:
    """BIST market hours: weekdays 09:00-17:00 Istanbul."""
    ist = timezone(timedelta(hours=3))
    now = datetime.now(ist)
    if now.weekday() in _WEEKEND_DAYS:
        return False
    return MARKET_OPEN_HOUR <= now.hour < MARKET_CLOSE_HOUR


def is_market_about_to_close(minutes: int = 30) -> bool:
    """Check if market is within N minutes of closing."""
    if not is_market_open():
        return False
    ist = timezone(timedelta(hours=3))
    now = datetime.now(ist)
    minutes_to_close = (MARKET_CLOSE_HOUR * 60) - (now.hour * 60 + now.minute)
    return 0 < minutes_to_close <= minutes


def get_ttl_for_cache_type(cache_type: str, baseline_ttl: Optional[int] = None) -> int:
    """
    Market-hour-aware TTL calculation.
    During market open: short TTL (stale data refreshes quickly).
    During market close: long TTL (data won't change).
    Before open: medium TTL (pre-market data).
    """
    open_ttl = baseline_ttl or 300
    closed_ttl = baseline_ttl or 3600

    if not is_market_open():
        return closed_ttl * 4
    if is_market_about_to_close(30):
        return closed_ttl
    return open_ttl


CACHE_TTL_MAP = {
    "public": lambda: get_ttl_for_cache_type("public", 300),
    "member": lambda: get_ttl_for_cache_type("member", 300),
    "full": lambda: get_ttl_for_cache_type("full", 900),
    "context": lambda: get_ttl_for_cache_type("context", 300),
    "pool": lambda: settings.CACHE_TTL_SECONDS,
    "company_profile": lambda: settings.COMPANY_PROFILE_CACHE_TTL,
    "fundamental": lambda: 300,
    "kurum_detail": lambda: 60,
}


def get_ttl(key_prefix: str) -> int:
    """Get TTL for a given cache key prefix."""
    ttl_fn = CACHE_TTL_MAP.get(key_prefix)
    if ttl_fn:
        return ttl_fn()
    return 300


class CacheWarming:
    """
    Proactive cache warming for top-N tickers.
    Runs after data refresh to pre-calculate TA for most-active stocks.
    """

    def __init__(self):
        self.top_tickers: list[str] = []
        self._last_warmed: float = 0
        self.warm_interval: int = 900  # 15 min

    def set_top_tickers(self, tickers: list[str]):
        """Set the list of top-N tickers to warm."""
        self.top_tickers = tickers[:50]

    async def warm(self, force: bool = False) -> int:
        """
        Pre-calculate TA for top tickers.
        Writes to KV: ta:warmed:{code}
        Returns count of successfully warmed tickers.
        """
        now = time.time()
        if not force and (now - self._last_warmed) < self.warm_interval:
            return 0

        if not self.top_tickers:
            return 0

        from app.services.ta_engine import calculate_full_analysis
        from app.core.workers_cache import cache_set, flush_pending

        count = 0
        for code in self.top_tickers:
            try:
                full = await calculate_full_analysis(code)
                if "error" not in full:
                    cache_set(f"ta:warmed:{code}", json.dumps(full, default=str), ttl=3600)
                    count += 1
            except Exception:
                continue

        await flush_pending()
        self._last_warmed = now
        logger.info("Cache warming: %d/%d tickers refreshed", count, len(self.top_tickers))
        return count


warming = CacheWarming()
