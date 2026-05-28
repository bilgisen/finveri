import redis
from app.core.config import settings

# Add an alias to make standard pipeline work with upstash_redis's .exec() method name
redis.client.Pipeline.exec = redis.client.Pipeline.execute

_client = None


def get_redis() -> redis.Redis:
    """Redis bağlantısını döner, yoksa oluşturur (singleton)."""
    global _client
    if _client is None:
        if settings.REDIS_URL:
            _client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        else:
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
