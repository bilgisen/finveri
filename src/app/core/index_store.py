"""
Index store — indices.json'ı okur ve yönetir.

Worker ortamında cron ile yenilenen KV üzerindeki `indices:catalog` verisi
önceliklidir; yoksa deploy sırasında gömülen data/indices.json kullanılır.

Not: Anahtar bilerek `indices:catalog` — hono cron'u aynı namespace'te
`indices:all`'ı endeks kotasyon listesiyle ezdiği için çakışmayı önlemek
amacıyla ayrı bir anahtar kullanılır.
"""
import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_INDICES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "indices.json")
_INDICES_FILE = os.path.normpath(_INDICES_FILE)

KEY_ALL_INDICES = "indices:catalog"

# Bileşen listeleri nadiren değişir; KV'de 7 gün tutulur.
INDICES_CACHE_TTL = 7 * 24 * 3600

_cached_indices: Optional[Dict] = None


def _read_bundled() -> Dict:
    try:
        with open(_INDICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("indices.json bulunamadı: %s", _INDICES_FILE)
        return {}
    except json.JSONDecodeError as e:
        logger.error("indices.json parse hatası: %s", e)
        return {}


def _read_kv() -> Optional[Dict]:
    try:
        from app.core.redis_client import get_redis
        raw = get_redis().get(KEY_ALL_INDICES)
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
    except Exception as e:
        logger.warning("[index_store] KV okuma hatası: %s", e)
    return None


def get_all_indices() -> Dict:
    """Tüm endeksleri döner (KV öncelikli, sonra bundled file)."""
    global _cached_indices
    if _cached_indices:
        return _cached_indices

    data = _read_kv()
    if not data:
        data = _read_bundled()

    _cached_indices = data
    return data


def get_index(code: str) -> Optional[Dict]:
    """Tek bir endeks bilgisini döner."""
    indices = get_all_indices()
    return indices.get(code.upper())


def invalidate_cache() -> None:
    global _cached_indices
    _cached_indices = None


def store_to_cache(indices: Dict) -> None:
    """indices verisini KV'ye yazar ve in-memory cache'i yeniler."""
    global _cached_indices
    try:
        from app.core.redis_client import get_redis
        get_redis().set(KEY_ALL_INDICES, json.dumps(indices, ensure_ascii=False, default=str), ex=INDICES_CACHE_TTL)
        _cached_indices = indices
    except Exception as e:
        logger.warning("[index_store] KV yazma hatası: %s", e)
