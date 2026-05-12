"""
Oyak Yatırım — tüm enstrüman listesi kaynağı.
Sağladığı veri: instruments (IMKB, Foreks, VIOP, ISEFunds)
"""
import logging
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.sources.base import BaseSource, SourceResult

logger = logging.getLogger(__name__)


class OyakSource(BaseSource):
    name = "oyak"
    provides = ["instruments"]

    def fetch(self) -> SourceResult:
        try:
            with httpx.Client(timeout=settings.HTTP_TIMEOUT_SECONDS, verify=False) as client:
                resp = client.get(settings.OYAK_INSTRUMENTS_URL)
                resp.raise_for_status()

            raw = resp.json()
            data = [self._normalize(item) for item in raw if item.get("Code")]

            return SourceResult(success=True, data=data, fetched_at=datetime.now(timezone.utc))

        except httpx.HTTPError as e:
            logger.error("[%s] HTTP hatası: %s", self.name, e)
            return SourceResult(success=False, error=str(e))
        except Exception as e:
            logger.error("[%s] Beklenmeyen hata: %s", self.name, e, exc_info=True)
            return SourceResult(success=False, error=str(e))

    @staticmethod
    def _normalize(item: dict) -> dict:
        return {
            "code": item.get("Code", "").strip(),
            "name": item.get("Name", "").strip(),
            "type": item.get("Type", "").strip(),
            "display_name": item.get("DisplayName", "").strip(),
        }
