from typing import List, Optional
from pydantic import BaseModel


class Instrument(BaseModel):
    """Temel enstrüman bilgisi — tüm kaynaklardan normalize edilmiş."""
    code: str
    name: str
    type: str
    display_name: str


class StockQuote(BaseModel):
    """Fiyat verisi içeren hisse senedi kaydı (AA kaynağı)."""
    code: str
    name: str
    type: str
    display_name: str
    last_price: Optional[float] = None
    first_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    diff_price: Optional[float] = None
    diff_percent: Optional[float] = None
    volume: Optional[float] = None
    record_date: Optional[str] = None
    source: Optional[str] = None


class MarketSummaryItem(BaseModel):
    """Piyasa özeti kalemi — navbar ticker verisi (AA)."""
    code: str
    name: str
    label: str
    category: str
    last_price: Optional[float] = None
    diff_price: Optional[float] = None
    diff_percent: Optional[float] = None
    display_order: Optional[int] = None
    source: Optional[str] = None


class StockDetail(BaseModel):
    """Tek sembol tam detay verisi (İş Yatırım kaynağı, on-demand)."""
    code: str
    source: str
    update_date: Optional[str] = None
    last: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    base_price: Optional[float] = None
    quantity: Optional[int] = None
    volume: Optional[float] = None
    net_proceeds: Optional[float] = None
    shifted_net_proceed: Optional[float] = None
    day_close: Optional[float] = None
    week_close: Optional[float] = None
    month_close: Optional[float] = None
    year_close: Optional[float] = None
    prev_year_close: Optional[float] = None
    week_high: Optional[float] = None
    week_low: Optional[float] = None
    month_high: Optional[float] = None
    month_low: Optional[float] = None
    limit_up: Optional[float] = None
    limit_down: Optional[float] = None
    equity: Optional[float] = None
    capital: Optional[float] = None
    circulation_share: Optional[float] = None
    price_step: Optional[float] = None
    eq_price: Optional[float] = None
    eq_quantity: Optional[int] = None
    eq_remaining_bid: Optional[int] = None
    eq_remaining_ask: Optional[int] = None


# --- Response wrapper'ları ---

class InstrumentsResponse(BaseModel):
    total: int
    last_updated: Optional[str]
    data: List[Instrument]


class StockQuotesResponse(BaseModel):
    total: int
    last_updated: Optional[str]
    data: List[StockQuote]


class MarketSummaryResponse(BaseModel):
    total: int
    last_updated: Optional[str]
    data: List[MarketSummaryItem]


class TopMoversResponse(BaseModel):
    """Günün en çok yükselen veya düşen hisseleri."""
    direction: str   # "gainers" | "losers"
    total: int
    last_updated: Optional[str]
    data: List[StockQuote]
