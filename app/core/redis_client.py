import redis
from app.core.config import settings

_client = None


def get_redis() -> redis.Redis:
    """Redis bağlantısını döner, yoksa oluşturur (singleton)."""
    global _client
    if _client is None:
        _client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _client


def ping_redis() -> bool:
    """Redis bağlantısını test eder."""
    try:
        return get_redis().ping()
    except Exception:
        return False
