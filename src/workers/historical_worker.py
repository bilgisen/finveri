"""
ta-historical Worker — Cron-triggered historical OHLCV sync.
Runs daily at 00:05 IST.
Fetches 2 years of daily OHLCV from İş Yatırım ChartData API for all tickers,
writes to D1 daily_prices table.

Cloudflare Cron Trigger: 5 21 * * * (21:05 UTC = 00:05 IST next day)
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from workers import WorkerEntrypoint

logger = logging.getLogger("ta-historical")


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        """HTTP handler — manual trigger or health check."""
        result = await self._sync_all()
        return self._json_response(result)

    async def scheduled(self, event):
        """Cron trigger handler (daily 00:05)."""
        logger.info("Historical sync cron triggered: %s", event.cron)
        result = await self._sync_all()
        total = result.get("synced", 0)
        failed = result.get("failed", 0)
        logger.info("Historical sync complete: %d synced, %d failed", total, failed)

    async def _sync_all(self) -> dict:
        """Sync historical OHLCV for all tickers."""
        from app.core.d1 import set_db, D1Repository
        set_db(self.env.DB)
        db = self.env.DB
        repo = D1Repository(db)

        ticker_codes = self._get_ticker_codes()
        if not ticker_codes:
            logger.warning("No ticker codes found in KV")
            return {"synced": 0, "failed": 0, "total": 0}

        semaphore = asyncio.Semaphore(20)
        synced = 0
        failed = 0

        async def sync_one(code: str):
            nonlocal synced, failed
            async with semaphore:
                try:
                    ok = await self._fetch_and_save(repo, code)
                    if ok:
                        synced += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    logger.warning("Sync failed for %s: %s", code, e)

        tasks = [sync_one(code) for code in ticker_codes]
        await asyncio.gather(*tasks)

        return {"synced": synced, "failed": failed, "total": len(ticker_codes)}

    def _get_ticker_codes(self) -> list:
        """Load ticker codes from bundled data."""
        try:
            from app.core.tickers_data import TICKERS
            return sorted(TICKERS.keys())
        except Exception:
            logger.warning("Could not load TICKERS from bundled data")
            return []

    async def _fetch_and_save(self, repo, ticker: str) -> bool:
        """Fetch historical OHLCV from İş Yatırım and save to D1."""
        import httpx

        # 2 years of daily data
        to_date = datetime.now(timezone.utc)
        from_date = to_date - timedelta(days=730)
        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        url = (
            "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/"
            f"ChartData.aspx/IndexHistoricalAll?period=1440&from={from_str}&to={to_str}&endeks={ticker}"
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                raw = resp.json()

            raw_data = raw.get("data") or raw.get("result") or raw.get("d")
            if not raw_data or not isinstance(raw_data, list):
                return False

            records = []
            seen = set()
            for item in raw_data:
                if isinstance(item, list) and len(item) >= 2:
                    ts = item[0]
                    close = float(item[1])
                    if isinstance(ts, (int, float)):
                        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                        date_str = dt.strftime("%Y-%m-%d")
                    else:
                        date_str = str(ts)[:10]
                    if date_str in seen:
                        continue
                    seen.add(date_str)
                    records.append(dict(
                        ticker=ticker,
                        date=date_str,
                        open=close,
                        high=close,
                        low=close,
                        close=close,
                        volume=0.0,
                    ))

            if records:
                await repo.batch_insert_prices(records)
                return True
            return False

        except Exception as e:
            logger.debug("Fetch error for %s: %s", ticker, e)
            return False

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, default=str)
        from workers.response import Response
        return Response(body, status=status, headers={"Content-Type": "application/json"})
