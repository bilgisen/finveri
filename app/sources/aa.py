"""
Anadolu Ajansı Finans — BIST hisse senedi fiyat verileri.
Sağladığı veri: bist_stocks (fiyat, hacim, değişim dahil)

Response yapısı:
{
  "SonTradeStatistics3": [
    {
      "Id": 1624517,
      "KayitTarihi": "/Date(1777561806073)/",
      "Symbol": "A1CAP",
      "Name": "A1 CAPITAL YATIRIM",
      "LastPrice": 12.48,
      "DiffLastPrice": -1.38,
      "DiffDayPer": -9.96,
      "FirstPrice": 12.48,
      "HighPrice": 12.79,
      "LowPrice": 12.48,
      "AccumulatedVolume": 32532413,
      "IsStatus": false,
      ...
    }
  ]
}
"""
import logging
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.sources.base import BaseSource, SourceResult

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
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "Referer": "https://aafinans.com/",
        "Origin": "https://aafinans.com",
        "X-Requested-With": "XMLHttpRequest",
    }

    def fetch(self) -> SourceResult:
        try:
            with httpx.Client(
                timeout=settings.HTTP_TIMEOUT_SECONDS,
                verify=False,
                headers=self._HEADERS,
                follow_redirects=True,
            ) as client:
                resp = client.get(settings.AA_BIST_URL)
                resp.raise_for_status()

            raw = resp.json()

            # AA response: {"SonTradeStatistics3": [...]}
            items = raw.get("SonTradeStatistics3", [])

            if not items:
                logger.warning("[%s] Boş veri döndü.", self.name)
                return SourceResult(success=False, error="Boş response")

            data = [self._normalize(item) for item in items if item.get("Symbol")]

            return SourceResult(
                success=True,
                data=data,
                fetched_at=datetime.now(timezone.utc),
            )

        except httpx.HTTPStatusError as e:
            logger.warning("[%s] HTTP %s hatası.", self.name, e.response.status_code)
            return SourceResult(success=False, error=f"HTTP {e.response.status_code}")
        except httpx.HTTPError as e:
            logger.error("[%s] HTTP hatası: %s", self.name, e)
            return SourceResult(success=False, error=str(e))
        except Exception as e:
            logger.error("[%s] Beklenmeyen hata: %s", self.name, e, exc_info=True)
            return SourceResult(success=False, error=str(e))

    @staticmethod
    def _parse_date(ms_date_str):
        """'/Date(1777561806073)/' formatını ISO string'e çevirir."""
        try:
            ms = int(ms_date_str.replace("/Date(", "").replace(")/", ""))
            return datetime.utcfromtimestamp(ms / 1000).isoformat() + "Z"
        except Exception:
            return None

    @classmethod
    def _normalize(cls, item: dict) -> dict:
        symbol = item.get("Symbol", "").strip()
        name = item.get("Name", "").strip()
        return {
            "code": symbol,
            "name": name,
            "type": "IMKB",
            "display_name": f"{symbol} - {name}",
            # Fiyat verileri
            "last_price": item.get("LastPrice"),
            "first_price": item.get("FirstPrice"),
            "high_price": item.get("HighPrice"),
            "low_price": item.get("LowPrice"),
            "diff_price": item.get("DiffLastPrice"),
            "diff_percent": item.get("DiffDayPer"),
            "volume": item.get("AccumulatedVolume"),
            "record_date": cls._parse_date(item.get("KayitTarihi", "")),
            "source": "aa",
        }
