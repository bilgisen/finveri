import redis
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)
_client = None


def get_redis() -> redis.Redis:
    """OVH Valkey/Redis bağlantısını döner, yoksa oluşturur (singleton)."""
    global _client
    if _client is None:
        url = settings.REDIS_URL
        if not url:
            raise ValueError(
                "REDIS_URL çevre değişkeni eksik!"
            )
        
        logger.info("Standard Redis istemcisi başlatılıyor: %s", url.split("@")[-1])
        _client = redis.from_url(
            url,
            decode_responses=True,
            ssl_cert_reqs=None,
            socket_timeout=10.0,
            socket_connect_timeout=10.0,
        )
    return _client


def ping_redis() -> bool:
    """Redis bağlantısını test eder."""
    try:
        # Standart redis.ping() True döner veya ping() yöntemi test edilir
        return get_redis().ping() is True
    except Exception as e:
        logger.error("Redis ping hatası: %s", e)
        return False
