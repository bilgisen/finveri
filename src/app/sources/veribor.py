"""
veribor (FastAPI Cloud) — BIST fiyat verisi alternatif kaynağı.

İş Yatırım'ın Cloudflare Worker IP'lerini engellemediği altyapıda (FastAPI Cloud)
çalışan veribor servisinden tüm hisse fiyatlarını, endeks özetini ve enstrüman
kataloğunu çeker. Yanıt zaten finveri pool şemasıyla birebir uyumludur
(StockQuote / MarketSummaryItem / Instrument), bu yüzden normalize yalnızca
basit bir passthrough'dan ibarettir.

Sağladığı veri: bist_stocks, market_summary, instruments
"""

import logging
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.sources.base import BaseSource, SourceResult

logger = logging.getLogger(__name__)


class VeriborSource(BaseSource):
    name = "veribor"
    provides = ["bist_stocks", "market_summary", "instruments"]

    # veribor data_type -> veribor uç nokta yolu
    _DATA_PATH = {
        "bist_stocks": "stocks",
        "market_summary": "summary",
        "instruments": "instruments?type=IMKB",
    }

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    def __init__(self, data_type: str = "bist_stocks"):
        if data_type not in self._DATA_PATH:
            raise ValueError(f"veribor {data_type} desteklemez")
        self._data_type = data_type
        self._base_url = settings.VERIBOR_API_URL

    def _normalize(self, payload) -> list:
        """veribor yanıtını ({total, data:[...]}) pool listesine çevirir."""
        if isinstance(payload, dict):
            data = payload.get("data")
        else:
            data = payload if isinstance(payload, list) else None
        if not isinstance(data, list):
            return []
        return [{k: v for k, v in item.items()} for item in data if isinstance(item, dict)]

    def _result(self, data: list) -> SourceResult:
        if not data:
            return SourceResult(success=False, error="veribor boş liste")
        return SourceResult(
            success=True,
            data=data,
            fetched_at=datetime.now(timezone.utc),
        )

    def fetch(self) -> SourceResult:
        """Lokal (APScheduler) pool yolu — senkron."""
        try:
            path = self._DATA_PATH[self._data_type]
            with httpx.Client(
                verify=False,
                timeout=settings.HTTP_TIMEOUT_SECONDS,
                headers=self._HEADERS,
                follow_redirects=True,
            ) as client:
                resp = client.get(f"{self._base_url}/{path}")
                if resp.status_code != 200:
                    return SourceResult(success=False, error=f"veribor HTTP {resp.status_code}")
                data = self._normalize(resp.json())
            logger.info("[veribor] %s: %d kayıt", self._data_type, len(data))
            return self._result(data)
        except Exception as e:
            logger.warning("[veribor] %s hatası: %s", self._data_type, e)
            return SourceResult(success=False, error=str(e))

    async def async_fetch(self) -> SourceResult:
        """Workers cron yolu — asenkron."""
        try:
            path = self._DATA_PATH[self._data_type]
            async with httpx.AsyncClient(
                verify=False,
                timeout=settings.HTTP_TIMEOUT_SECONDS,
                headers=self._HEADERS,
                follow_redirects=True,
            ) as client:
                resp = await client.get(f"{self._base_url}/{path}")
                if resp.status_code != 200:
                    return SourceResult(success=False, error=f"veribor HTTP {resp.status_code}")
                data = self._normalize(resp.json())
            logger.info("[veribor] %s: %d kayıt", self._data_type, len(data))
            return self._result(data)
        except Exception as e:
            logger.warning("[veribor] %s hatası: %s", self._data_type, e)
            return SourceResult(success=False, error=str(e))
