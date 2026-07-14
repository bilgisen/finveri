"""
ta-fetcher Worker — Cron-triggered data refresh with progressive batches.
Runs every 15 minutes during market hours (09:00-18:00 IST, weekdays).
Fetches bist_stocks from İş Yatırım in small batches to avoid CPU limits.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from workers import WorkerEntrypoint

logger = logging.getLogger("ta-fetcher")

_BATCH_SIZE = 30
_OFFSET_KEY = "fetcher:batch_offset"
CACHE_TTL = 86400


def _is_market_hours() -> bool:
    ist = timezone(timedelta(hours=3))
    now = datetime.now(ist)
    if now.weekday() >= 5:
        return False
    return 9 <= now.hour < 18


def _normalize(raw: dict, code: str) -> dict:
    last = raw.get("last") or 0
    day_close = raw.get("dayClose") or last
    diff_price = last - day_close
    diff_percent = (diff_price / day_close * 100) if day_close > 0 else 0.0
    return {
        "code": code, "name": code, "type": "IMKB",
        "display_name": code, "last_price": last,
        "first_price": raw.get("open"), "high_price": raw.get("high"),
        "low_price": raw.get("low"), "diff_price": diff_price,
        "diff_percent": diff_percent, "volume": raw.get("volume"),
        "record_date": raw.get("updateDate"), "source": "ajans",
    }


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return self._json_response({"status": "ok", "message": "alive"})

    async def scheduled(self, event):
        logger.info("Cron: %s", event.cron)
        if not _is_market_hours():
            logger.info("Outside market hours — skip")
            return
        await self._refresh_all()

    async def _refresh_all(self):
        now_utc = datetime.now(timezone.utc).isoformat()

        # Instruments (OYAK) — lightweight, 1 call
        try:
            from js import fetch as js_fetch
            resp = await js_fetch("https://www.oyakyatirim.com.tr/Home/GetAllInstruments")
            if resp and resp.ok:
                raw = await resp.json()
                await self.env.KV.put("pool:instruments:data", json.dumps(raw), expiration_ttl=CACHE_TTL)
                await self.env.KV.put("pool:instruments:last_updated", now_utc, expiration_ttl=CACHE_TTL)
                logger.info("Instruments OK (%d items)", len(raw) if isinstance(raw, list) else 0)
        except Exception as e:
            logger.warning("Instruments failed: %s", e)

        # Market summary (AA) — lightweight, 1 call
        try:
            from js import fetch as js_fetch
            resp = await js_fetch("https://aafinans.com/Navigation/UstBarSembolListesiniAl")
            if resp and resp.ok:
                raw = await resp.json()
                await self.env.KV.put("pool:market_summary:data", json.dumps(raw), expiration_ttl=CACHE_TTL)
                await self.env.KV.put("pool:market_summary:last_updated", now_utc, expiration_ttl=CACHE_TTL)
                logger.info("Market summary OK (%d items)", len(raw) if isinstance(raw, list) else 0)
        except Exception as e:
            logger.warning("Market summary failed: %s", e)

        # BIST stocks — batched from İş Yatırım
        try:
            await self._refresh_stocks(now_utc)
        except Exception as e:
            logger.error("Stocks refresh failed: %s", e)

    async def _refresh_stocks(self, now_utc: str):
        offset = 0
        try:
            raw = await self.env.KV.get(_OFFSET_KEY)
            offset = int(raw) if raw else 0
        except Exception:
            pass

        from app.core.tickers_data import TICKERS
        codes = sorted([k for k, v in TICKERS.items() if v.get("market") == "BIST"])

        total = len(codes)
        batch = codes[offset:offset + _BATCH_SIZE]
        if not batch:
            offset = 0
            batch = codes[:min(_BATCH_SIZE, total)]

        from js import fetch as js_fetch

        results = []
        for i in range(0, len(batch), 10):
            chunk = batch[i:i + 10]
            tasks = []
            for code in chunk:
                url = f"https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/OneEndeks?endeks={code}"
                tasks.append(js_fetch(url))
            responses = await asyncio.gather(*tasks)
            for resp in responses:
                if resp and resp.ok:
                    try:
                        data = await resp.json()
                        if isinstance(data, list) and data:
                            item = data[0]
                            code = item.get("symbol", "")
                            if code:
                                results.append(_normalize(item, code))
                    except Exception:
                        pass
            await asyncio.sleep(0)

        if results:
            await self.env.KV.put("pool:bist_stocks:data", json.dumps(results), expiration_ttl=CACHE_TTL)
            await self.env.KV.put("pool:bist_stocks:last_updated", now_utc, expiration_ttl=CACHE_TTL)
            logger.info("BIST batch: %d stocks at offset %d", len(results), offset)

        new_offset = offset + _BATCH_SIZE
        if new_offset >= total:
            new_offset = 0
        await self.env.KV.put(_OFFSET_KEY, str(new_offset), expiration_ttl=86400)

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, default=str)
        from workers.response import Response
        return Response(body, status=status, headers={"Content-Type": "application/json"})
