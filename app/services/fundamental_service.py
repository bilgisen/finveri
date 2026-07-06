"""
Temel analiz servisi — P/E ve diğer rasyoları hesaplar.

Veri kaynakları:
- İş Yatırım: Fiyat, equity, capital, circulation_share
- COMP API: ROE, net_margin, current_ratio, debt_to_equity

P/E Hesaplama:
  P/E = Fiyat / EPS
  EPS ≈ (ROE × Equity) / Capital
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import settings

try:
    from app.core.redis_client import get_redis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

from app.sources.isyatirim import fetch_detail

logger = logging.getLogger(__name__)

_CACHE_KEY = "fundamental:{code}"
_CACHE_TTL = 300  # 5 dakika cache


def _compute_pe_ratio(
    last_price: Optional[float],
    roe: Optional[float],
    equity: Optional[float],
    capital: Optional[float],
) -> tuple[Optional[float], str]:
    """
    P/E ratio hesaplar.

    Returns:
        (pe_ratio, method) - pe_ratio None ise method "unavailable" olur
    """
    if not last_price or last_price <= 0:
        return None, "no_price"

    if not equity or not capital or capital <= 0:
        return None, "no_equity_capital"

    if roe is None:
        return None, "no_roe"

    # EPS ≈ (ROE × Equity) / Capital
    net_income = roe * equity
    eps = net_income / capital

    if eps <= 0:
        return None, "negative_eps"

    pe = last_price / eps
    return round(pe, 2), "computed"


def _fetch_comp_ratios(ticker: str) -> dict:
    """COMP API'den temel rasyoları çeker."""
    try:
        url = f"{settings.COMP_API_URL}/api/v1/companies/{ticker}/ratios"
        with httpx.Client(timeout=settings.COMP_API_TIMEOUT) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        ratios = data.get("ratios", {})
        return {
            "roe": ratios.get("roe", {}).get("value"),
            "roa": ratios.get("roa", {}).get("value"),
            "net_margin": ratios.get("net_margin", {}).get("value"),
            "current_ratio": ratios.get("current_ratio", {}).get("value"),
            "debt_to_equity": ratios.get("debt_to_equity", {}).get("value"),
            "sector": data.get("sector"),
        }
    except Exception as e:
        logger.warning("[fundamental] COMP API fetch failed for %s: %s", ticker, e)
        return {}


def get_fundamental_data(ticker: str) -> Optional[dict]:
    """
    Hisse için temel analiz verisi döner.

    İş Yatırım'dan fiyat + COMP API'den rasyolar çeker,
    P/E hesaplar ve sonucu cache'ler.
    """
    code = ticker.upper()
    cache_key = _CACHE_KEY.format(code=code)

    # Cache kontrol
    try:
        cached = get_redis().get(cache_key)
        if cached:
            import json
            return json.loads(cached)
    except Exception:
        pass

    # İş Yatırım'dan fiyat + equity + capital
    detail = fetch_detail(code)
    if not detail:
        logger.warning("[fundamental] İş Yatırım detail alınamadı: %s", code)
        return None

    last_price = detail.get("last")
    equity = detail.get("equity")
    capital = detail.get("capital")
    circulation_share = detail.get("circulation_share")

    # COMP API'den rasyolar
    comp = _fetch_comp_ratios(code)

    # P/E hesapla
    pe_ratio, pe_method = _compute_pe_ratio(
        last_price=last_price,
        roe=comp.get("roe"),
        equity=equity,
        capital=capital,
    )

    # Data quality belirle
    fields_available = sum(1 for v in [
        last_price, equity, capital, comp.get("roe")
    ] if v is not None)
    if fields_available >= 4:
        data_quality = "high"
    elif fields_available >= 2:
        data_quality = "medium"
    else:
        data_quality = "low"

    result = {
        "ticker": code,
        "source": "finveri",
        "last_price": last_price,
        "pe_ratio": pe_ratio,
        "pe_ratio_method": pe_method,
        "equity": equity,
        "capital": capital,
        "circulation_share": circulation_share,
        "roe": comp.get("roe"),
        "roa": comp.get("roa"),
        "net_margin": comp.get("net_margin"),
        "current_ratio": comp.get("current_ratio"),
        "debt_to_equity": comp.get("debt_to_equity"),
        "sector": comp.get("sector"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "data_quality": data_quality,
    }

    # Cache'e yaz
    try:
        import json
        get_redis().set(cache_key, json.dumps(result), ex=_CACHE_TTL)
    except Exception:
        pass

    return result
