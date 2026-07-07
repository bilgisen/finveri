"""
DataPool — çoklu kaynak yöneticisi.

Her veri tipi için primary + fallback zinciri tanımlanır.
Primary başarısız olursa fallback denenir.
Her kaynağın durumu (son fetch zamanı, başarı/hata) takip edilir.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.config import settings

try:
    from app.core.redis_client import get_redis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

from app.sources.base import BaseSource, SourceResult

logger = logging.getLogger(__name__)

# Redis key şablonları
_KEY_DATA = "pool:{data_type}:data"
_KEY_LAST_UPDATED = "pool:{data_type}:last_updated"
_KEY_SOURCE_STATUS = "pool:source_status"


class DataPool:
    """
    Veri tipi → [primary_source, fallback_source, ...] zincirini yönetir.

    Kullanım:
        pool = DataPool()
        pool.register("instruments", primary=OyakSource(), fallbacks=[AASource()])
        pool.refresh("instruments")
    """

    def __init__(self):
        # { data_type: [source1, source2, ...] }  (öncelik sırasıyla)
        self._chains: Dict[str, List[BaseSource]] = {}

    def register(
        self,
        data_type: str,
        primary: BaseSource,
        fallbacks: Optional[List[BaseSource]] = None,
    ):
        """Bir veri tipi için kaynak zinciri kaydeder."""
        chain = [primary] + (fallbacks or [])
        self._chains[data_type] = chain
        logger.info(
            "Kayıt: '%s' → %s",
            data_type,
            [s.name for s in chain],
        )

    def refresh(self, data_type: str) -> bool:
        """
        Belirtilen veri tipini günceller.
        Zincirdeki kaynakları sırayla dener, ilk başarılıyı kullanır.
        """
        chain = self._chains.get(data_type)
        if not chain:
            logger.warning("'%s' için kayıtlı kaynak yok.", data_type)
            return False

        for source in chain:
            logger.info("[%s] '%s' için veri çekiliyor...", source.name, data_type)
            result = source.fetch()
            self._update_source_status(source.name, data_type, result)

            if result.success and result.data:
                self._write_to_cache(data_type, result)
                logger.info(
                    "[%s] '%s' güncellendi. %d kayıt.",
                    source.name, data_type, len(result.data),
                )
                return True
            else:
                logger.warning(
                    "[%s] '%s' başarısız: %s. Fallback deneniyor...",
                    source.name, data_type, result.error,
                )

        logger.error("'%s' için tüm kaynaklar başarısız oldu.", data_type)
        return False

    def refresh_all(self):
        """Kayıtlı tüm veri tiplerini günceller."""
        for data_type in self._chains:
            self.refresh(data_type)

    def get_status(self) -> dict:
        """Tüm kaynakların son durumunu döner (/health için)."""
        try:
            raw = get_redis().get(_KEY_SOURCE_STATUS)
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def _write_to_cache(self, data_type: str, result: SourceResult):
        """Normalize edilmiş veriyi Redis'e yazar."""
        r = get_redis()
        ttl = settings.CACHE_TTL_SECONDS
        now = result.fetched_at.isoformat() if result.fetched_at else datetime.now(timezone.utc).isoformat()

        # _raw alanını cache'e yazma (sadece normalize edilmiş alanlar)
        clean_data = []
        for item in result.data:
            clean_data.append({k: v for k, v in item.items() if k != "_raw"})

        pipe = r.pipeline()
        pipe.set(_KEY_DATA.format(data_type=data_type), json.dumps(clean_data), ex=ttl)
        pipe.set(_KEY_LAST_UPDATED.format(data_type=data_type), now, ex=ttl)
        pipe.exec()

    def _update_source_status(self, source_name: str, data_type: str, result: SourceResult):
        """Kaynak durumunu Redis'e yazar (monitoring için)."""
        try:
            r = get_redis()
            raw = r.get(_KEY_SOURCE_STATUS)
            status = json.loads(raw) if raw else {}

            key = f"{source_name}:{data_type}"
            status[key] = {
                "source": source_name,
                "data_type": data_type,
                "success": result.success,
                "error": result.error,
                "last_attempt": datetime.now(timezone.utc).isoformat(),
                "last_success": (
                    result.fetched_at.isoformat()
                    if result.success and result.fetched_at
                    else status.get(key, {}).get("last_success")
                ),
            }

            r.set(_KEY_SOURCE_STATUS, json.dumps(status), ex=settings.CACHE_TTL_SECONDS * 2)
        except Exception as e:
            logger.warning("Source status yazılamadı: %s", e)
