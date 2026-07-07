"""
Ticker store — tickers.json'ı okur, Redis'e yükler.
API başlangıcında bir kez çalışır. Reload endpoint'i ile yeniden yüklenebilir.
"""
import json
import logging
import os
from typing import Dict, Optional

try:
    from app.core.redis_client import get_redis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

logger = logging.getLogger(__name__)

_TICKERS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "tickers.json")
_TICKERS_FILE = os.path.normpath(_TICKERS_FILE)

KEY_TICKER = "tickers:code:{code}"
KEY_ALL_TICKERS = "tickers:all"
KEY_TICKER_CODES = "tickers:codes"


def load_tickers() -> int:
    """
    tickers.json'ı okur ve Redis'e yazar.
    Yüklenen ticker sayısını döner.
    """
    if not _HAS_REDIS:
        logger.warning("Redis mevcut degil, ticker yuklenemedi.")
        return 0

    try:
        with open(_TICKERS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        logger.warning("tickers.json bulunamadı: %s", _TICKERS_FILE)
        return 0
    except json.JSONDecodeError as e:
        logger.error("tickers.json parse hatası: %s", e)
        return 0

    tickers = {k: v for k, v in raw.items() if not k.startswith("_")}

    r = get_redis()
    pipe = r.pipeline()

    for code, data in tickers.items():
        pipe.set(KEY_TICKER.format(code=code), json.dumps(data))

    pipe.set(KEY_ALL_TICKERS, json.dumps(tickers))
    pipe.set(KEY_TICKER_CODES, json.dumps(list(tickers.keys())))

    pipe.execute()
    logger.info("%d ticker Redis'e yüklendi.", len(tickers))
    return len(tickers)


def get_ticker(code: str) -> Optional[Dict]:
    """Tek bir ticker'ı Redis'ten döner."""
    if not _HAS_REDIS:
        return None
    try:
        raw = get_redis().get(KEY_TICKER.format(code=code.upper()))
        return json.loads(raw) if raw else None
    except Exception:
        return None


def get_all_tickers() -> Dict:
    """Tüm ticker'ları döner."""
    if not _HAS_REDIS:
        return {}
    try:
        raw = get_redis().get(KEY_ALL_TICKERS)
        return json.loads(raw) if raw else {}
    except Exception:
        return {}
