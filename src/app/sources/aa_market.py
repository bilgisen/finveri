"""
Anadolu Ajansı Finans — Piyasa özeti (navbar ticker verisi).
Sağladığı veri: market_summary

GÜNCELLEME: AA Finans url'leri kalıcı olarak yönlendirildiği için,
AAMarketSummarySource yapısı ve provides anahtarı korunarak arka planda veriler
İş Yatırım API'sinden sadece Borsa İstanbul (BIST) endeksleri olarak çekilmektedir.
Herhangi bir Forex, emtia, altın veya kripto verisi içermez.
"""
import logging
from datetime import datetime, timezone

from app.sources.base import BaseSource, SourceResult

logger = logging.getLogger(__name__)


class AAMarketSummarySource(BaseSource):
    name = "ajans"
    provides = ["market_summary"]

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.isyatirim.com.tr/",
    }

    def _fetch_custom_summary(self) -> list:
        data = []
        
        # Is Yatirim'dan sadece BIST endekslerini cek
        try:
            from app.sources.isyatirim import fetch_detail
            index_codes = [
                ("XU100", "BIST 100", "BIST 100"),
                ("XU030", "BIST 30", "BIST 30"),
                ("XU500", "BIST 500", "BIST 500"),
                ("XBANK", "BIST Banka", "BIST Banka"),
                ("XUSIN", "BIST Sınai", "BIST Sınai")
            ]
            for extra_code, name, label in index_codes:
                detail = fetch_detail(extra_code)
                if detail and detail.get("last") is not None:
                    last_price = detail["last"]
                    day_close = detail.get("day_close") or last_price
                    diff_price = last_price - day_close
                    diff_percent = (diff_price / day_close * 100) if day_close > 0 else 0.0
                    
                    data.append({
                        "code": extra_code,
                        "name": name,
                        "label": label,
                        "category": "index",
                        "last_price": last_price,
                        "diff_price": diff_price,
                        "diff_percent": diff_percent,
                        "display_order": len(data) + 1,
                        "source": "ajans",
                    })
        except Exception as e:
            logger.error("[custom_summary] Is Yatirim fetch error: %s", e)

        return data

    def fetch(self) -> SourceResult:
        try:
            custom_data = self._fetch_custom_summary()
            if custom_data:
                logger.info("[%s] Market summary is custom generated successfully. %d items.", self.name, len(custom_data))
                return SourceResult(
                    success=True,
                    data=custom_data,
                    fetched_at=datetime.now(timezone.utc),
                )
            else:
                return SourceResult(success=False, error="Market summary empty")
        except Exception as e:
            logger.error("[%s] Beklenmeyen hata: %s", self.name, e, exc_info=True)
            return SourceResult(success=False, error=str(e))
