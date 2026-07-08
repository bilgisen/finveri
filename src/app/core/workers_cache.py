"""
Workers KV-backed cache layer.

In-memory sync cache with optional Workers KV persistence.
Used by route handlers and pool in Workers mode.

Usage:
    from app.core.workers_cache import init_cache, cache_get, cache_set, get_cache

    # Called once from entry.py
    await init_cache(env.KV)

    # Sync read/write (in-memory)
    val = cache_get("pool:instruments:data")
    cache_set("pool:instruments:data", json_string, ttl=3600)

    # KV persistence writes are queued and flushed in entry.py
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_kv = None
_data: dict[str, str] = {}
_pending: list[tuple[str, str, Optional[int]]] = []
_initialized = False


async def init_cache(kv_binding: Any) -> None:
    global _kv, _initialized
    _kv = kv_binding
    _initialized = True
    logger.info("Workers cache initialized")


def is_ready() -> bool:
    return _initialized


def cache_get(key: str) -> Optional[str]:
    return _data.get(key)


def cache_set(key: str, value: str, ttl: Optional[int] = None) -> None:
    _data[key] = value
    if _kv is not None and ttl is not None:
        _pending.append((key, value, ttl))


def cache_delete(key: str) -> None:
    _data.pop(key, None)


def cache_keys(pattern: str = "*") -> list[str]:
    if pattern == "*":
        return list(_data.keys())
    if pattern.endswith("*"):
        prefix = pattern[:-1]
        return [k for k in _data if k.startswith(prefix)]
    return [k for k in _data if k == pattern]


class _CachePipeline:
    def __init__(self):
        self._ops: list = []

    def get(self, key):
        self._ops.append(("get", key))
        return self

    def set(self, key, value, ex=None):
        self._ops.append(("set", key, value, ex))
        return self

    def delete(self, key):
        self._ops.append(("delete", key))
        return self

    def execute(self):
        results = []
        for op in self._ops:
            if op[0] == "get":
                results.append(_data.get(op[1]))
            elif op[0] == "set":
                _data[op[1]] = op[2]
                if _kv is not None and op[3]:
                    _pending.append((op[1], op[2], op[3]))
                results.append(True)
            elif op[0] == "delete":
                _data.pop(op[1], None)
                results.append(True)
        self._ops.clear()
        return results


class _CacheStore:
    def get(self, key): return cache_get(key)
    def set(self, key, value, ex=None): return cache_set(key, value, ex)
    def delete(self, key): return cache_delete(key)
    def ping(self): return _initialized
    def keys(self, pattern="*"): return cache_keys(pattern)
    def pipeline(self): return _CachePipeline()
    def exists(self, key): return 1 if _data.get(key) is not None else 0


_store = _CacheStore()


def get_cache() -> _CacheStore:
    return _store


async def flush_pending() -> int:
    """Flush queued KV writes. Called from entry.py before returning response."""
    if _kv is None:
        return 0
    count = 0
    while _pending:
        key, value, ttl = _pending.pop(0)
        try:
            kwargs = {"expiration_ttl": ttl} if ttl else {}
            await _kv.put(key, value, **kwargs)
            count += 1
        except Exception as e:
            logger.warning("KV put failed for key=%s: %s", key, e)
    return count


async def load_initial(prefix: str = "pool:") -> int:
    """Load cached keys from KV into memory at startup."""
    if _kv is None:
        return 0
    try:
        result = await _kv.list({"prefix": prefix})
        count = 0
        for item in result.get("keys", []):
            name = item["name"]
            val = await _kv.get(name)
            if val is not None:
                _data[name] = val
                count += 1
        logger.info("Loaded %d keys (prefix=%s) from KV", count, prefix)
        return count
    except Exception as e:
        logger.warning("Failed to load from KV: %s", e)
        return 0
