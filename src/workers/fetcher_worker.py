"""
ta-fetcher Worker — Cron-triggered data refresh.
Runs every 15 minutes during market hours (09:00-17:00 IST, weekdays).
Fetches fresh data from sources (İş Yatırım, OYAK, etc.) and writes to KV.

Cloudflare Cron Trigger: */15 9-16 * * 1-5 (every 15 min, 9-16 UTC = 12-19 IST)
Also runs on every invocation as warm-up if no recent data.
"""
import logging
from datetime import datetime, timezone, timedelta
from workers import WorkerEntrypoint

logger = logging.getLogger("ta-fetcher")


def _is_market_hours() -> bool:
    ist = timezone(timedelta(hours=3))
    now = datetime.now(ist)
    if now.weekday() >= 5:
        return False
    return 9 <= now.hour < 18


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        """HTTP handler — for manual trigger or health check."""
        results = await self._run_refresh()
        return self._json_response(results)

    async def scheduled(self, event):
        """Cron trigger handler."""
        logger.info("Cron trigger received: %s", event.cron)
        if _is_market_hours():
            await self._run_refresh()
        else:
            logger.info("Outside market hours — skipping refresh")

    async def _run_refresh(self) -> dict:
        """Run the full data pool refresh."""
        from app.core.d1 import set_db
        set_db(self.env.DB)
        from app.core.workers_cache import init_cache
        await init_cache(self.env.KV)

        results = {}
        cache_types = ["instruments", "bist_stocks", "market_summary"]

        for data_type in cache_types:
            try:
                ok = await self._refresh_type(data_type)
                results[data_type] = ok
            except Exception as e:
                results[data_type] = False
                logger.error("%s refresh failed: %s", data_type, e)

        failed = [k for k, v in results.items() if not v]
        if failed:
            logger.warning("Partial failure: %s", failed)

        try:
            from app.core.workers_cache import flush_pending
            await flush_pending()
        except Exception:
            pass

        return results

    async def _refresh_type(self, data_type: str) -> bool:
        by_type = {
            "instruments": ("app.sources.oyak", "OyakSource", "instruments"),
            "bist_stocks": ("app.sources.aa", "AASource", "bist_stocks"),
            "market_summary": ("app.sources.aa_market", "AAMarketSummarySource", "market_summary"),
        }
        mod_path, cls_name, cache_key = by_type[data_type]

        import importlib
        mod = importlib.import_module(mod_path)
        source_cls = getattr(mod, cls_name)
        source = source_cls()

        if hasattr(source, "async_fetch"):
            result = await source.async_fetch(max_concurrent=20)
        else:
            result = source.fetch()

        if not result.success or not result.data:
            return False

        from app.core.workers_cache import cache_set, get_cache
        from app.core.config import settings
        cache = get_cache()
        ttl = settings.CACHE_TTL_SECONDS
        now = result.fetched_at.isoformat() if result.fetched_at else datetime.now(timezone.utc).isoformat()

        clean = [{k: v for k, v in item.items() if k != "_raw"} for item in result.data]
        pipe = cache.pipeline()
        pipe.set(f"pool:{cache_key}:data", __import__("json").dumps(clean), ex=ttl)
        pipe.set(f"pool:{cache_key}:last_updated", now, ex=ttl)
        pipe.execute()

        if data_type == "bist_stocks":
            await self._save_daily_ohlcv(result.data)

        return True

    async def _save_daily_ohlcv(self, data: list) -> None:
        try:
            from app.core.d1 import D1Repository
            db = self.env.DB
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

    def _json_response(self, data: dict, status: int = 200):
        import json
        from workers.response import Response
        body = json.dumps(data, default=str)
        return Response(body, status=status, headers={"Content-Type": "application/json"})
