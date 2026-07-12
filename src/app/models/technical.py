"""
Pydantic models for Technical Analysis data structures.
Used by all TA endpoints: public, member, full, context, batch.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class PricePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MACDData(BaseModel):
    value: Optional[float] = None
    signal: Optional[float] = None
    histogram: Optional[float] = None


class BollingerBandsData(BaseModel):
    upper: Optional[float] = None
    middle: Optional[float] = None
    lower: Optional[float] = None


class StochasticData(BaseModel):
    k: Optional[float] = None
    d: Optional[float] = None


class ADXData(BaseModel):
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None


class SMAData(BaseModel):
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None


class IndicatorSummary(BaseModel):
    rsi: Optional[float] = None
    macd: Optional[MACDData] = None
    sma: Optional[SMAData] = None
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    bbands: Optional[BollingerBandsData] = None
    atr: Optional[float] = None
    atr_pct: Optional[float] = None
    stoch: Optional[StochasticData] = None
    adx: Optional[ADXData] = None
    obv: Optional[float] = None
    mfi: Optional[float] = None
    supertrend: Optional[float] = None
    supertrend_direction: Optional[str] = None
    psar: Optional[float] = None
    vwap: Optional[float] = None


class DivergenceInfo(BaseModel):
    bullish: bool = False
    bearish: bool = False
    confidence: str = "Low"


class DivergenceAnalysis(BaseModel):
    rsi: Optional[DivergenceInfo] = None
    macd: Optional[DivergenceInfo] = None
    obv: Optional[DivergenceInfo] = None
    overall_confidence: str = "Low"
    divergence_count: int = 0


class GoldenCrossInfo(BaseModel):
    has_golden_cross: bool = False
    has_death_cross: bool = False
    bars_since_cross: Optional[int] = None
    sma_20_minus_sma_50: Optional[float] = None
    previous_sma_20_minus_sma_50: Optional[float] = None


class TrendAgeInfo(BaseModel):
    daily_direction: str = "Neutral"
    daily_bars: int = 0
    weekly_direction: str = "Neutral"
    weekly_bars: int = 0


class MTFAlignment(BaseModel):
    daily_trend: str = "Neutral"
    weekly_trend: str = "Neutral"
    monthly_trend: str = "Neutral"
    alignment_score: int = 50
    alignment_label: str = "Mixed"


class VolumeMetrics(BaseModel):
    obv: Optional[float] = None
    obv_trend: str = "Neutral"
    relative_volume: Optional[float] = None
    volume_trend: str = "Neutral"
    volume_above_avg: bool = False
    mfi: Optional[float] = None
    volume_confirmation: str = "Neutral"


class MarketRegime(BaseModel):
    regime: str = "Unknown"
    trend_direction: str = "Neutral"
    volatility_regime: str = "Normal"
    adx: Optional[float] = None
    efficiency_ratio: Optional[float] = None
    volatility_pct: Optional[float] = None
    confidence: int = 50
    recommended_strategy: str = ""
    interpretation: str = ""


class VolumeProfile(BaseModel):
    poc: Optional[float] = None
    poc_volume: Optional[float] = None
    value_area_high: Optional[float] = None
    value_area_low: Optional[float] = None
    total_volume: Optional[float] = None
    value_area_volume_pct: int = 70


class LiquidityVoid(BaseModel):
    date: str = ""
    gap_start: float = 0.0
    gap_end: float = 0.0
    gap_size: float = 0.0
    gap_pct: float = 0.0
    direction: str = "up"
    bars_ago: int = 0


class SRLevel(BaseModel):
    price: float = 0.0
    type: str = ""
    strength: int = 50
    tests: int = 0
    source_bar: Optional[str] = None


class SupportResistance(BaseModel):
    current_price: float = 0.0
    resistance_zones: list[SRLevel] = []
    support_zones: list[SRLevel] = []
    nearest_resistance: Optional[SRLevel] = None
    nearest_support: Optional[SRLevel] = None


class CandlestickPattern(BaseModel):
    name: str = ""
    direction: str = "Neutral"
    reliability: int = 50
    bars_ago: int = 0
    confirmation_volume: bool = False


class ChartPattern(BaseModel):
    name: str = ""
    direction: str = "Neutral"
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    invalidation_price: Optional[float] = None
    confidence: int = 50
    bars_ago: int = 0
    volume_confirmed: bool = False


class PatternAnalysis(BaseModel):
    candlestick_patterns: list[CandlestickPattern] = []
    chart_patterns: list[ChartPattern] = []
    total_active: int = 0


class Scenario(BaseModel):
    name: str = ""
    direction: str = "Neutral"
    trigger_price: Optional[float] = None
    target_price: Optional[float] = None
    invalidation_price: Optional[float] = None
    supporting_signal_count: int = 0
    description: str = ""


class RiskMetrics(BaseModel):
    atr_based_stop_loss: Optional[float] = None
    risk_per_bar: Optional[float] = None
    max_drawdown_estimate: Optional[float] = None
    volatility_classification: str = "Normal"
    beta_vs_index: Optional[float] = None


class ScoreComponents(BaseModel):
    trend: int = 0
    momentum: int = 0
    volume: int = 0
    pattern: int = 0


class CompositeScore(BaseModel):
    total: int = 50
    confidence: str = "Low"
    components: Optional[ScoreComponents] = None


class ActiveSignal(BaseModel):
    label: str = ""
    direction: str = "Neutral"
    source: str = ""
    freshness: str = "Established"


class TASummaryPublic(BaseModel):
    ticker: str
    price: float
    change_pct: Optional[float] = None
    date: str = ""
    trend: str = "Neutral"
    regime: Optional[str] = None
    score: int = 50
    confidence: str = "Low"
    sma: Optional[SMAData] = None
    rsi: Optional[float] = None
    macd_status: Optional[str] = None
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    summary_text: str = ""
    source: str = "live"


class TASummaryMember(BaseModel):
    ticker: str
    price: float
    change_pct: Optional[float] = None
    date: str = ""
    indicators: Optional[IndicatorSummary] = None
    trend: str = "Neutral"
    weekly_trend: str = "Neutral"
    regime: Optional[MarketRegime] = None
    volume_profile: Optional[VolumeProfile] = None
    liquidity_voids: list[LiquidityVoid] = []
    sr_zones: Optional[SupportResistance] = None
    score: int = 50
    confidence: str = "Low"
    score_components: Optional[ScoreComponents] = None
    signals: list[str] = []
    divergences: Optional[DivergenceAnalysis] = None
    golden_cross: Optional[GoldenCrossInfo] = None
    mtf_alignment: Optional[MTFAlignment] = None
    volume_metrics: Optional[VolumeMetrics] = None
    summary_text: str = ""
    source: str = "live"


class TAFull(BaseModel):
    ticker: str
    price: float
    change_pct: Optional[float] = None
    date: str = ""
    indicators: Optional[IndicatorSummary] = None
    trend: str = "Neutral"
    weekly_trend: str = "Neutral"
    monthly_trend: str = "Neutral"
    regime: Optional[MarketRegime] = None
    volume_profile: Optional[VolumeProfile] = None
    liquidity_voids: list[LiquidityVoid] = []
    sr_zones: Optional[SupportResistance] = None
    patterns: Optional[PatternAnalysis] = None
    divergences: Optional[DivergenceAnalysis] = None
    golden_cross: Optional[GoldenCrossInfo] = None
    trend_age: Optional[TrendAgeInfo] = None
    mtf_alignment: Optional[MTFAlignment] = None
    volume_metrics: Optional[VolumeMetrics] = None
    scenarios: list[Scenario] = []
    risk_metrics: Optional[RiskMetrics] = None
    score: Optional[CompositeScore] = None
    signals: list[ActiveSignal] = []
    beta: Optional[float] = None
    market_breadth: Optional[dict] = None
    relative_strength: Optional[dict] = None
    llm_summary_prompt: str = ""
    source: str = "live"


class TAContext(BaseModel):
    ticker: str
    current_price: float
    trend: str
    regime: Optional[MarketRegime] = None
    key_levels: Optional[SupportResistance] = None
    active_signals: list[ActiveSignal] = []
    scenarios: list[Scenario] = []
    risk_metrics: Optional[RiskMetrics] = None
    summary_text: str = ""
    query_type: str = "general"


class BatchTickerRequest(BaseModel):
    tickers: list[str]
    filters: Optional[dict] = None


class BatchTickerResult(BaseModel):
    ticker: str
    score: int
    confidence: str
    regime: Optional[str] = None
    trend: str = "Neutral"
    price: Optional[float] = None
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None


class BatchResponse(BaseModel):
    results: list[BatchTickerResult] = []
    total: int = 0
    filtered: int = 0


class SectorSummary(BaseModel):
    sector: str
    ticker_count: int
    median_score: int = 50
    avg_return: Optional[float] = None
    above_sma_50_pct: float = 50.0
    advance_decline_ratio: Optional[float] = None
    top_performers: list[str] = []
    bottom_performers: list[str] = []
    sector_regime: str = "Neutral"


class IndexBreadth(BaseModel):
    index_code: str
    ticker_count: int = 0
    above_sma_20_pct: float = 50.0
    above_sma_50_pct: float = 50.0
    above_sma_200_pct: float = 50.0
    advancing_count: int = 0
    declining_count: int = 0
    advance_decline_ratio: Optional[float] = None
    new_highs: int = 0
    new_lows: int = 0
    status: str = "Neutral"


class HistoryLookupResult(BaseModel):
    ticker: str
    current_score: int = 50
    current_regime: str = "Unknown"
    similar_past_states: list[dict] = []
    average_outcome: Optional[float] = None
    positive_outcome_pct: Optional[float] = None
    sample_size: int = 0
