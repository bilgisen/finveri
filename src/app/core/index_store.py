"""
Index store — indices.json'ı okur ve yönetir.
"""
import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_INDICES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "indices.json")
_INDICES_FILE = os.path.normpath(_INDICES_FILE)

_cached_indices: Dict = {}

def get_all_indices() -> Dict:
    """Tüm endeksleri döner (Caching-enabled)."""
    global _cached_indices
    if _cached_indices:
        return _cached_indices

    try:
        with open(_INDICES_FILE, "r", encoding="utf-8") as f:
            _cached_indices = json.load(f)
    except FileNotFoundError:
        logger.warning("indices.json bulunamadı: %s", _INDICES_FILE)
        return {}
    except json.JSONDecodeError as e:
        logger.error("indices.json parse hatası: %s", e)
        return {}

    return _cached_indices

def get_index(code: str) -> Optional[Dict]:
    """Tek bir endeks bilgisini döner."""
    indices = get_all_indices()
    return indices.get(code.upper())
