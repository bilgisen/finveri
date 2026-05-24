"""
Anadolu Ajansı Finans — Piyasa özeti (navbar ticker verisi).
Sağladığı veri: market_summary

Brent, Altın, USD/TRY, EUR/TRY, BIST 100/500, Bitcoin, Dolar Endeksi vb.
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

    def _fetch_custom_summary(self) -> list:
        data = []
        
        # 1. Is Yatirim'dan endeksleri, emtialari ve altini cek
        try:
            from app.sources.isyatirim import fetch_detail
            index_codes = [
                ("XU100", "BIST 100", "BIST 100"),
                ("XU030", "BIST 30", "BIST 30"),
                ("XU500", "BIST 500", "BIST 500"),
                ("XBANK", "BIST Banka", "BIST Banka"),
                ("BRENT", "Brent Petrol", "BRENT PETROL $"),
                ("GLDGR", "Gram Altın TL", "ALTIN TL/GR")
            ]
            for extra_code, name, label in index_codes:
                detail = fetch_detail(extra_code)
                if detail and detail.get("last"):
                    last_price = detail["last"]
                    day_close = detail.get("day_close") or last_price
                    diff_price = last_price - day_close
                    diff_percent = (diff_price / day_close * 100) if day_close > 0 else 0.0
                    
                    code = "XGLD" if extra_code == "GLDGR" else extra_code
                    category = "gold" if extra_code == "GLDGR" else ("commodity" if extra_code == "BRENT" else "index")
                    
                    data.append({
                        "code": code,
                        "name": name,
                        "label": label,
                        "category": category,
                        "last_price": last_price,
                        "diff_price": diff_price,
                        "diff_percent": diff_percent,
                        "display_order": len(data) + 1,
                        "source": "isyatirim",
                    })
        except Exception as e:
            logger.error("[custom_summary] Is Yatirim fetch error: %s", e)

        # 2. Frankfurter'dan doviz kurlarini cek
        try:
            import httpx
            url = "https://api.frankfurter.app/latest?to=USD,TRY"
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                if resp.ok:
                    f_data = resp.json()
                    rates = f_data.get("rates", {})
                    usd = rates.get("USD")
                    try_rate = rates.get("TRY")
                    if usd and try_rate:
                        usdtry = try_rate / usd
                        
                        # USDTRY
                        data.append({
                            "code": "USDTRY",
                            "name": "Dolar/TL",
                            "label": "USD/TRY",
                            "category": "forex",
                            "last_price": round(usdtry, 4),
                            "diff_price": 0.0,
                            "diff_percent": 0.0,
                            "display_order": len(data) + 1,
                            "source": "frankfurter",
                        })
                        
                        # EURTRY
                        data.append({
                            "code": "EURTRY",
                            "name": "FX Euro/Turkish Lira",
                            "label": "EUR/TRY",
                            "category": "forex",
                            "last_price": try_rate,
                            "diff_price": 0.0,
                            "diff_percent": 0.0,
                            "display_order": len(data) + 1,
                            "source": "frankfurter",
                        })
                        
                        # EURUSD
                        data.append({
                            "code": "EURUSD",
                            "name": "FX USD/EURO",
                            "label": "EUR/USD",
                            "category": "forex",
                            "last_price": usd,
                            "diff_price": 0.0,
                            "diff_percent": 0.0,
                            "display_order": len(data) + 1,
                            "source": "frankfurter",
                        })
        except Exception as e:
            logger.error("[custom_summary] Frankfurter fetch error: %s", e)

        # 3. Binance'ten Bitcoin cek
        try:
            import httpx
            url = "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                if resp.ok:
                    b_data = resp.json()
                    last_price = float(b_data.get("lastPrice", 0))
                    pct_change = float(b_data.get("priceChangePercent", 0))
                    price_change = float(b_data.get("priceChange", 0))
                    
                    data.append({
                        "code": "BTCUSDT",
                        "name": "BTC_USDT",
                        "label": "BITCOIN/USD",
                        "category": "crypto",
                        "last_price": last_price,
                        "diff_price": price_change,
                        "diff_percent": pct_change,
                        "display_order": len(data) + 1,
                        "source": "binance",
                    })
        except Exception as e:
            logger.error("[custom_summary] Binance fetch error: %s", e)

        return data

    def fetch(self) -> SourceResult:
        # Oncelikle cok daha guvenilir ve canli olan Is Yatirim + Frankfurter + Binance summary generatorunu dene
        try:
            custom_data = self._fetch_custom_summary()
            if len(custom_data) >= 5:
                logger.info("[%s] Market summary is custom generated successfully. %d items.", self.name, len(custom_data))
                return SourceResult(
                    success=True,
                    data=custom_data,
                    fetched_at=datetime.now(timezone.utc),
                )
        except Exception as ex:
            logger.error("[%s] Custom summary generation failed, falling back to AA: %s", self.name, ex)

        # Fallback: Eski AA Finans crawler mekanizmasi
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
