"""
Anadolu Ajansı Finans — BIST hisse senedi fiyat verileri.
Sağladığı veri: bist_stocks (fiyat, hacim, değişim dahil)

GÜNCELLEME: AA Finans url'leri kalıcı olarak yönlendirildiği için,
AASource yapısı ve provides anahtarı korunarak arka planda veriler
İş Yatırım API'sinden eşzamanlı (ThreadPoolExecutor) olarak çekilmektedir.
Bu sayede sistem kesintisiz çalışmaya devam eder.
"""
import asyncio
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from app.core.config import settings
from app.sources.base import BaseSource, SourceResult
from app.core.ticker_store import get_all_tickers

logger = logging.getLogger(__name__)


class AASource(BaseSource):
    name = "aa"
    provides = ["bist_stocks"]

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.isyatirim.com.tr/",
    }

    @staticmethod
    async def _js_fetch(url: str) -> object | None:
        try:
            from js import fetch
            resp = await fetch(url, method="GET", headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.isyatirim.com.tr/",
            })
            return resp
        except ImportError:
            logger.debug("js.fetch not available, using httpx instead")
            return None
        except Exception as e:
            logger.warning("js.fetch failed for %s: %s", url, e)
            return None

    def _fetch_one(self, client: httpx.Client, code: str, name: str) -> dict:
        url = f"https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/OneEndeks?endeks={code}"
        try:
            resp = client.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    last = item.get("last", 0.0)
                    day_close = item.get("dayClose") or last
                    diff_price = last - day_close
                    diff_percent = (diff_price / day_close * 100) if day_close > 0 else 0.0
                    
                    return {
                        "code": code,
                        "name": name,
                        "type": "IMKB",
                        "display_name": f"{code} - {name}",
                        "last_price": last,
                        "first_price": item.get("open"),
                        "high_price": item.get("high"),
                        "low_price": item.get("low"),
                        "diff_price": diff_price,
                        "diff_percent": diff_percent,
                        "volume": item.get("volume"),
                        "record_date": item.get("updateDate"),
                        "source": "aa",
                    }
        except Exception as e:
            logger.warning("[%s] Ticker %s fetch failed: %s", self.name, code, e)
        return None

    async def async_fetch(self, max_concurrent: int = 10) -> SourceResult:
        try:
            tickers_dict = get_all_tickers()
            if not tickers_dict:
                return SourceResult(success=False, error="Ticker listesi boş")

            bist_stocks = [
                (code, info.get("name", code))
                for code, info in tickers_dict.items()
                if info.get("market") == "BIST"
            ]

            if not bist_stocks:
                return SourceResult(success=False, error="BIST hissesi bulunamadı")

            sem = asyncio.Semaphore(max_concurrent)

            async def _fetch_one_async(client: httpx.AsyncClient, code: str, name: str) -> dict | None:
                url = f"https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/OneEndeks?endeks={code}"
                async with sem:
                    try:
                        resp = await client.get(url, timeout=10.0)
                        if resp.status_code == 200:
                            data = resp.json()
                            if isinstance(data, list) and data:
                                item = data[0]
                                last = item.get("last", 0.0)
                                day_close = item.get("dayClose") or last
                                diff_price = last - day_close
                                diff_percent = (diff_price / day_close * 100) if day_close > 0 else 0.0
                                return {
                                    "code": code, "name": name, "type": "IMKB",
                                    "display_name": f"{code} - {name}",
                                    "last_price": last, "first_price": item.get("open"),
                                    "high_price": item.get("high"), "low_price": item.get("low"),
                                    "diff_price": diff_price, "diff_percent": diff_percent,
                                    "volume": item.get("volume"), "record_date": item.get("updateDate"),
                                    "source": "aa",
                                }
                    except Exception as e:
                        logger.warning("[%s] Ticker %s async fetch failed: %s", self.name, code, e)
                    return None

            async with httpx.AsyncClient(verify=False, headers=self._HEADERS, follow_redirects=True) as client:
                tasks = [_fetch_one_async(client, code, name) for code, name in bist_stocks]
                results = await asyncio.gather(*tasks)
                data = [r for r in results if r is not None]

            if not data:
                return SourceResult(success=False, error="BIST verisi çekilemedi")
            data.sort(key=lambda x: x["code"])
            return SourceResult(success=True, data=data, fetched_at=datetime.now(timezone.utc))
        except Exception as e:
            logger.error("[%s] async_fetch hatası: %s", self.name, e, exc_info=True)
            return SourceResult(success=False, error=str(e))

    def fetch(self, max_stocks: int = 100) -> SourceResult:
        try:
            tickers_dict = get_all_tickers()
            if not tickers_dict:
                from app.core.ticker_store import load_tickers
                load_tickers()
                tickers_dict = get_all_tickers()
            
            bist_stocks = [
                (code, info.get("name", code))
                for code, info in tickers_dict.items()
                if info.get("market") == "BIST"
            ]
            if max_stocks > 0:
                bist_stocks = bist_stocks[:max_stocks]
            
            if not bist_stocks:
                logger.warning("[%s] Ticker listesinde BIST hissesi bulunamadı.", self.name)
                return SourceResult(success=False, error="BIST hissesi bulunamadı")

            data = []
            with httpx.Client(verify=False, headers=self._HEADERS, follow_redirects=True) as client:
                try:
                    with ThreadPoolExecutor(max_workers=5) as executor:
                        futures = {
                            executor.submit(self._fetch_one, client, code, name): code
                            for code, name in bist_stocks
                        }
                        for future in as_completed(futures):
                            res = future.result()
                            if res:
                                data.append(res)
                except RuntimeError:
                    for code, name in bist_stocks[:100]:
                        res = self._fetch_one(client, code, name)
                        if res:
                            data.append(res)

            if not data:
                return SourceResult(success=False, error="İş Yatırım'dan BIST verisi çekilemedi")

            data = sorted(data, key=lambda x: x["code"])

            return SourceResult(
                success=True,
                data=data,
                fetched_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error("[%s] Beklenmeyen hata: %s", self.name, e, exc_info=True)
            return SourceResult(success=False, error=str(e))
