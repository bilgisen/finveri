"""
Anadolu Ajansı Finans — Piyasa özeti (navbar ticker verisi).
Sağladığı veri: market_summary

Brent, Altın, USD/TRY, EUR/TRY, BIST 100/500, Bitcoin, Dolar Endeksi vb.

Response yapısı:
{
  "UstBarSembolListesi": [
    {
      "SymbolId": 26,
      "Symbol": "USDTRY",
      "Name": "Dolar/TL",
      "LastPrice": 45.157,
      "DiffDayPer": -0.01,
      "DiffLastPrice": 0,
      "Kolon": 4,
      "Sira": 2,
      "OnyuzTanim": "USD/TRY",   ← görünen etiket
      "SembolVeriTipi": 4,
      "type": 1
    }
  ]
}

type değerleri (gözlemlenen):
  0 → Endeks / Kripto / VIOP
  1 → Forex
  3 → Endeks (BIST Repo)
  4 → Emtia / Forex
  5 → Kripto
  8 → Emtia (Brent)
  9 → Altın TL
  11 → Dolar Endeksi

SembolVeriTipi:
  2 → VIOP
  3 → Endeks
  4 → Forex / Emtia
  5 → Kripto
"""
import logging
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.sources.base import BaseSource, SourceResult

logger = logging.getLogger(__name__)

# type → okunabilir kategori
_TYPE_CATEGORY = {
    0: "index",
    1: "forex",
    3: "repo",
    4: "commodity",   # Brent, Altın Ons gibi emtialar bu grupta
    5: "crypto",
    8: "commodity",   # Brent Petrol
    9: "gold",        # Gram Altın TL
    11: "index",      # Dolar Endeksi
}

_VERI_TIPI_CATEGORY = {
    2: "viop",
    3: "index",
    4: "commodity",   # Forex ve emtia karışık — type ile ayrıştırılır
    5: "crypto",
}


def _resolve_category(item: dict) -> str:
    """type + SembolVeriTipi kombinasyonundan kategori belirler."""
    t = item.get("type", 0)
    vt = item.get("SembolVeriTipi", 0)

    # type=1 kesinlikle forex
    if t == 1:
        return "forex"
    # type=8 → Brent (emtia)
    if t == 8:
        return "commodity"
    # type=9 → Gram Altın TL
    if t == 9:
        return "gold"
    # type=3 → Repo
    if t == 3:
        return "repo"
    # type=5 → Kripto (ama Symbol=GLD ise altın emtiası)
    if t == 5:
        symbol = item.get("Symbol", "")
        if symbol in ("GLD", "XGLD", "GOLD"):
            return "gold"
        return "crypto"
    # SembolVeriTipi ile ayrıştır
    if vt == 2:
        return "viop"
    if vt == 3:
        return "index"
    if vt == 5:
        return "crypto"
    # SembolVeriTipi=4 → type'a göre karar ver
    if vt == 4:
        return _TYPE_CATEGORY.get(t, "commodity")
    return _TYPE_CATEGORY.get(t, "other")


class AAMarketSummarySource(BaseSource):
    name = "aa_market"
    provides = ["market_summary"]

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
                resp = client.get(settings.AA_MARKET_SUMMARY_URL)
                resp.raise_for_status()

            raw = resp.json()
            items = raw.get("UstBarSembolListesi", [])

            if not items:
                return SourceResult(success=False, error="Boş response")

            # Kolon/Sira sırasına göre sırala (navbar'daki görünüm sırası)
            items_sorted = sorted(items, key=lambda x: (x.get("Kolon", 99), x.get("Sira", 99)))
            data = [self._normalize(item) for item in items_sorted]

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

    @classmethod
    def _normalize(cls, item: dict) -> dict:
        symbol = item.get("Symbol", "").strip()
        name = item.get("Name", "").strip()
        label = item.get("OnyuzTanim", "").strip()  # görünen etiket (ör: "USD/TRY")

        return {
            "code": symbol,
            "name": name,
            "label": label or name,
            "category": _resolve_category(item),
            "last_price": item.get("LastPrice"),
            "diff_price": item.get("DiffLastPrice"),
            "diff_percent": item.get("DiffDayPer"),
            "display_order": (item.get("Kolon", 99) - 1) * 2 + item.get("Sira", 99),
            "source": "aa",
        }
