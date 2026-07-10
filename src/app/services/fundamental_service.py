"""
Temel analiz servisi — P/E ve diğer rasyoları hesaplar.

Veri kaynakları:
- İş Yatırım (kurum): Fiyat, equity, capital, circulation_share, net_proceeds

P/E Hesaplama:
  P/E = Fiyat / EPS
  EPS ≈ (ROE × Equity) / Capital
  ROE ≈ Net_Proceeds / Equity
"""
import logging
from datetime import datetime, timezone
from typing import Optional

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


def get_fundamental_data(ticker: str) -> Optional[dict]:
    """
    Hisse için temel analiz verisi döner.

    İş Yatırım (kurum)'dan fiyat + bilanço verileri çeker,
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
    net_proceeds = detail.get("net_proceeds")

    # ROE hesapla (Net_Proceeds / Equity)
    roe = None
    if net_proceeds is not None and equity and equity > 0:
        roe = net_proceeds / equity

    # P/E hesapla
    pe_ratio, pe_method = _compute_pe_ratio(
        last_price=last_price,
        roe=roe,
        equity=equity,
        capital=capital,
    )

    # Data quality belirle
    fields_available = sum(1 for v in [
        last_price, equity, capital, roe
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
        "roe": roe,
        "roa": None,
        "net_margin": None,
        "current_ratio": None,
        "debt_to_equity": None,
        "sector": None,
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
