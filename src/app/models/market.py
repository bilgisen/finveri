"""
Pydantic models for market breadth, sector analysis, and relative strength.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class TickerSectorInfo(BaseModel):
    code: str
    name: str
    sector: str
    market: str
    last_price: Optional[float] = None
    change_pct: Optional[float] = None


class SectorPerformance(BaseModel):
    sector: str
    ticker_count: int = 0
    median_score: int = 50
    mean_return: Optional[float] = None
    above_sma_50_pct: float = 50.0
    advance_decline_ratio: Optional[float] = None
    advancing_count: int = 0
    declining_count: int = 0
    top_ticker: Optional[str] = None
    bottom_ticker: Optional[str] = None
    top_ticker_return: Optional[float] = None
    bottom_ticker_return: Optional[float] = None


class IndexConstituent(BaseModel):
    code: str
    weight: Optional[float] = None
    last_price: Optional[float] = None
    change_pct: Optional[float] = None
    is_above_sma_20: bool = False
    is_above_sma_50: bool = False
    is_above_sma_200: bool = False


class AdvanceDeclineData(BaseModel):
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    total: int = 0
    ad_ratio: Optional[float] = None
    ad_line: Optional[float] = None


class NewHighLowData(BaseModel):
    new_highs: int = 0
    new_lows: int = 0
    nh_nl_ratio: Optional[float] = None


class CumulativeBreadth(BaseModel):
    cumulative_ad_line: Optional[float] = None
    cumulative_ad_pct: Optional[float] = None
    trend: str = "Neutral"


class IndexBreadthDetail(BaseModel):
    index_code: str
    index_name: str
    constituent_count: int = 0
    price: Optional[float] = None
    change_pct: Optional[float] = None
    advance_decline: Optional[AdvanceDeclineData] = None
    new_high_low: Optional[NewHighLowData] = None
    above_sma_20: int = 0
    above_sma_20_pct: float = 0.0
    above_sma_50: int = 0
    above_sma_50_pct: float = 0.0
    above_sma_200: int = 0
    above_sma_200_pct: float = 0.0
    cumulative: Optional[CumulativeBreadth] = None
    status: str = "Neutral"
    interpretation: str = ""


class RelativeStrength(BaseModel):
    ticker: str
    vs_index_code: str = "XU100"
    relative_strength_1m: Optional[float] = None
    relative_strength_3m: Optional[float] = None
    relative_strength_6m: Optional[float] = None
    relative_strength_12m: Optional[float] = None
    performance_label: str = "Neutral"
    vs_sector: Optional[str] = None
    sector_performance: Optional[str] = None


class MarketTemperature(BaseModel):
    overall_status: str = "Neutral"
    breadth_pct: float = 50.0
    volatility_index: Optional[float] = None
    put_call_ratio: Optional[float] = None
    foreign_flow: Optional[float] = None
    interpretation: str = ""
