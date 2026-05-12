import json
import logging
from datetime import datetime, timezone
from typing import List, Dict

import httpx

from app.core.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

# Redis key sabitleri
KEY_ALL = "instruments:all"
KEY_LAST_UPDATED = "instruments:last_updated"
KEY_TYPES = "instruments:types"
KEY_BY_TYPE = "instruments:type:{type}"
KEY_BY_CODE = "instruments:code:{code}"


def _normalize(raw: List[Dict]) -> List[Dict]:
    """Ham veriyi normalize eder."""
    result = []
    for item in raw:
        result.append({
            "code": item.get("Code", "").strip(),
            "name": item.get("Name", "").strip(),
            "type": item.get("Type", "").strip(),
            "display_name": item.get("DisplayName", "").strip(),
        })
    return result


def fetch_and_cache() -> bool:
    """
    Kaynaktan enstrüman verilerini çeker ve Redis'e yazar.
    Başarılıysa True, hata varsa False döner.
    """
    try:
        logger.info("Enstrüman verileri çekiliyor: %s", settings.INSTRUMENTS_URL)

        with httpx.Client(timeout=15, verify=False) as client:
            response = client.get(settings.INSTRUMENTS_URL)
            response.raise_for_status()

        raw_data = response.json()
        instruments = _normalize(raw_data)

        if not instruments:
            logger.warning("Kaynak boş veri döndü, cache güncellenmedi.")
            return False

        r = get_redis()
        ttl = settings.CACHE_TTL_SECONDS
        now = datetime.now(timezone.utc).isoformat()

        pipe = r.pipeline()

        # Tüm enstrümanları tek key'de sakla
        pipe.set(KEY_ALL, json.dumps(instruments), ex=ttl)
        pipe.set(KEY_LAST_UPDATED, now, ex=ttl)

        # Tiplere göre grupla
        by_type: Dict[str, List[Dict]] = {}
        for inst in instruments:
            t = inst["type"]
            by_type.setdefault(t, []).append(inst)

        # Tip listesini sakla
        pipe.set(KEY_TYPES, json.dumps(list(by_type.keys())), ex=ttl)

        # Her tip için ayrı key
        for t, items in by_type.items():
            pipe.set(KEY_BY_TYPE.format(type=t), json.dumps(items), ex=ttl)

        # Her enstrüman için ayrı key (code bazlı lookup)
        for inst in instruments:
            pipe.set(KEY_BY_CODE.format(code=inst["code"]), json.dumps(inst), ex=ttl)

        pipe.execute()

        logger.info(
            "Cache güncellendi. Toplam: %d enstrüman, %d tip.",
            len(instruments),
            len(by_type),
        )
        return True

    except httpx.HTTPError as e:
        logger.error("HTTP hatası: %s", e)
        return False
    except Exception as e:
        logger.error("Beklenmeyen hata: %s", e, exc_info=True)
        return False
