import logging
import httpx
from datetime import datetime, timezone

from app.sources.base import BaseSource, SourceResult
from app.core.config import settings

logger = logging.getLogger(__name__)

class FrankfurterSource(BaseSource):
    name = "frankfurter"
    provides = ["forex"]

    def fetch(self) -> SourceResult:
        try:
            # We want EURUSD, EURTRY, and USDTRY.
            # Base EUR to get USD and TRY.
            url = "https://api.frankfurter.app/latest?to=USD,TRY"
            with httpx.Client(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

            base = data.get("base", "EUR")
            rates = data.get("rates", {})
            date_str = data.get("date")

            usd = rates.get("USD")
            try_rate = rates.get("TRY")

            if not usd or not try_rate:
                return SourceResult(success=False, error="Frankfurter API did not return USD or TRY rates")

            instruments = []

            # EURUSD
            instruments.append({
                "code": "EURUSD",
                "source": self.name,
                "last": usd,
                "update_date": date_str
            })

            # EURTRY
            instruments.append({
                "code": "EURTRY",
                "source": self.name,
                "last": try_rate,
                "update_date": date_str
            })

            # USDTRY
            usdtry = try_rate / usd
            instruments.append({
                "code": "USDTRY",
                "source": self.name,
                "last": round(usdtry, 4),
                "update_date": date_str
            })

            return SourceResult(
                success=True,
                data=instruments,
                fetched_at=datetime.now(timezone.utc)
            )

        except Exception as e:
            logger.error(f"[frankfurter] Fetch failed: {e}")
            return SourceResult(success=False, error=str(e))
