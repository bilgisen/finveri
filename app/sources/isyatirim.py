"""
İş Yatırım — tek sembol detay verisi (on-demand).

Her sembol için ayrı istek gerektirir. Periyodik worker'da değil,
API isteği geldiğinde çalışır ve sonucu Redis'e kısa süreli cache'ler.

Endpoint: GET /OneEndeks?endeks={SYMBOL}

Response (liste, tek eleman):
[{
  "updateDate": "2026-04-30T18:05:28.000+03",
  "bid": 37.96,
  "ask": 0,
  "low": 37.02,
  "high": 37.96,
  "last": 37.96,
  "dayClose": 34.52,
  "quantity": 3390067,
  "volume": 128372862.88,
  "monthHigh": 37.96,
  "monthLow": 32,
  "limitUp": 41.74,
  "limitDown": 34.18,
  "netProceeds": 76665486,
  "equity": 3256301285,
  "capital": 55000000,
  "circulationShare": 41159399.85,
  "priceStep": 0.02,
  "basePrice": 37.96,
  "open": 37.52,
  "weekLow": 33.6,
  "weekHigh": 37.96,
  "weekClose": 34.42,
  "monthClose": 33.4,
  "yearClose": 32.46,
  "shiftedNetProceed": 76665,
  "eqPrice": 37.96,
  "eqQuantity": 500,
  "eqRemainingBidQuantity": 1611083,
  "eqRemainingAskQuantity": 0,
  "prevYearClose": 28.9,
  "symbol": "A1YEN"
}]
"""
import json
import logging
from typing import Optional

import httpx

from app.core.config import settings

try:
    from app.core.redis_client import get_redis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

logger = logging.getLogger(__name__)

_KEY_DETAIL = "isyatirim:detail:{code}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.isyatirim.com.tr/",
}


def fetch_detail(symbol: str) -> Optional[dict]:
    """
    Sembol için İş Yatırım'dan detay çeker.
    Önce Redis cache'e bakar, yoksa HTTP isteği atar.
    Başarısızsa None döner (caller 503 veya fallback uygular).
    """
    code = symbol.upper()
    cache_key = _KEY_DETAIL.format(code=code)

    # Cache'e bak
    try:
        cached = get_redis().get(cache_key)
        if cached:
            logger.debug("[isyatirim] Cache hit: %s", code)
            return json.loads(cached)
    except Exception as e:
        logger.warning("[isyatirim] Redis okuma hatası: %s", e)

    # HTTP isteği
    try:
        url = f"{settings.ISYATIRIM_QUOTE_URL}?endeks={code}"
        with httpx.Client(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            verify=False,
            headers=_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()

        data = resp.json()

        # Response liste — ilk elemanı al
        if not data or not isinstance(data, list):
            logger.warning("[isyatirim] Beklenmeyen format: %s", code)
            return None

        raw = data[0]
        result = _normalize(raw, code)

        # Cache'e yaz
        try:
            get_redis().set(
                cache_key,
                json.dumps(result),
                ex=settings.ONDEMAND_CACHE_TTL_SECONDS,
            )
        except Exception as e:
            logger.warning("[isyatirim] Redis yazma hatası: %s", e)

        return result

    except httpx.HTTPStatusError as e:
        logger.warning("[isyatirim] HTTP %s: %s", e.response.status_code, code)
        return None
    except httpx.HTTPError as e:
        logger.error("[isyatirim] HTTP hatası (%s): %s", code, e)
        return None
    except Exception as e:
        logger.error("[isyatirim] Beklenmeyen hata (%s): %s", code, e, exc_info=True)
        return None


def _normalize(raw: dict, requested_code: str) -> dict:
    """Ham İş Yatırım verisini standart formata çevirir."""
    # symbol alanı bazen farklı gelebilir, requested_code'u esas al
    symbol = raw.get("symbol", requested_code).upper()

    return {
        "code": symbol,
        "source": "isyatirim",
        "update_date": raw.get("updateDate"),
        # Anlık fiyat
        "last": raw.get("last"),
        "bid": raw.get("bid"),
        "ask": raw.get("ask"),
        "open": raw.get("open"),
        "high": raw.get("high"),
        "low": raw.get("low"),
        "base_price": raw.get("basePrice"),
        # Hacim
        "quantity": raw.get("quantity"),
        "volume": raw.get("volume"),
        "net_proceeds": raw.get("netProceeds"),
        "shifted_net_proceed": raw.get("shiftedNetProceed"),
        # Kapanışlar
        "day_close": raw.get("dayClose"),
        "week_close": raw.get("weekClose"),
        "month_close": raw.get("monthClose"),
        "year_close": raw.get("yearClose"),
        "prev_year_close": raw.get("prevYearClose"),
        # Periyot yüksek/düşük
        "week_high": raw.get("weekHigh"),
        "week_low": raw.get("weekLow"),
        "month_high": raw.get("monthHigh"),
        "month_low": raw.get("monthLow"),
        # Devre kesici
        "limit_up": raw.get("limitUp"),
        "limit_down": raw.get("limitDown"),
        # Şirket bilgileri
        "equity": raw.get("equity"),
        "capital": raw.get("capital"),
        "circulation_share": raw.get("circulationShare"),
        "price_step": raw.get("priceStep"),
        # Eşleşme
        "eq_price": raw.get("eqPrice"),
        "eq_quantity": raw.get("eqQuantity"),
        "eq_remaining_bid": raw.get("eqRemainingBidQuantity"),
        "eq_remaining_ask": raw.get("eqRemainingAskQuantity"),
    }
