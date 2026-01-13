"""
Pydantic data models for the Learning Store.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class PatternType(str, Enum):
    """Types of patterns that can be recognized."""
    ENTRY_TIMING = "ENTRY_TIMING"
    EXIT_TIMING = "EXIT_TIMING"
    POSITION_SIZING = "POSITION_SIZING"
    REGIME_DETECTION = "REGIME_DETECTION"
    RISK_MANAGEMENT = "RISK_MANAGEMENT"
    PARAMETER_OPTIMIZATION = "PARAMETER_OPTIMIZATION"
    MOMENTUM_SIGNAL = "MOMENTUM_SIGNAL"
    REVERSAL_SIGNAL = "REVERSAL_SIGNAL"
    VOLATILITY_PATTERN = "VOLATILITY_PATTERN"


class LearningType(str, Enum):
    """Types of learning events."""
    TRADE_OUTCOME = "TRADE_OUTCOME"
    PATTERN_CONFIRMED = "PATTERN_CONFIRMED"
    PATTERN_INVALIDATED = "PATTERN_INVALIDATED"
    PARAMETER_ADJUSTED = "PARAMETER_ADJUSTED"
    REGIME_TRANSITION = "REGIME_TRANSITION"
    BACKTEST_INSIGHT = "BACKTEST_INSIGHT"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


class MarketRegime(str, Enum):
    """Market regime classifications."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    VOLATILE = "VOLATILE"
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"


class Pattern(BaseModel):
    """A recognized trading pattern."""
    pattern_id: Optional[int] = None
    pattern_type: PatternType
    name: str
    description: str
    conditions: dict[str, Any] = Field(default_factory=dict)
    expected_outcome: str
    confidence: float = Field(ge=0.0, le=1.0)
    sample_size: int = 0
    win_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    avg_pnl: float = 0.0
    regime: Optional[MarketRegime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True


class Learning(BaseModel):
    """A learning event recorded by the system."""
    learning_id: Optional[int] = None
    learning_type: LearningType
    description: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    source: str
    related_pattern_id: Optional[int] = None
    related_trade_id: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class MarketConditions(BaseModel):
    """Current market conditions for decision making."""
    regime: MarketRegime
    rsi: float = Field(ge=0.0, le=100.0)
    momentum: float
    volatility: float = Field(ge=0.0)
    trend_strength: float = Field(ge=-1.0, le=1.0)
    volume_ratio: float = Field(ge=0.0, default=1.0)
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
    timestamp: datetime = Field(default_factory=datetime.now)


class Recommendation(BaseModel):
    """A parameter or action recommendation."""
    recommendation_id: Optional[int] = None
    parameter_name: str
    current_value: Any
    recommended_value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    expected_improvement: float
    reasoning: str
    supporting_patterns: list[int] = Field(default_factory=list)
    regime: Optional[MarketRegime] = None
    valid_until: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    applied: bool = False
    outcome: Optional[str] = None


class ParameterPerformance(BaseModel):
    """Performance metrics for a parameter value."""
    parameter_name: str
    parameter_value: Any
    regime: Optional[MarketRegime] = None
    trade_count: int = 0
    win_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    avg_pnl: float = 0.0
    total_pnl: float = 0.0
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    first_used: datetime = Field(default_factory=datetime.now)
    last_used: datetime = Field(default_factory=datetime.now)


class TradeFeatures(BaseModel):
    """Features extracted from a trade for pattern learning."""
    trade_id: int
    symbol: str
    side: str
    entry_hour: int
    exit_hour: int
    holding_minutes: float
    entry_rsi: Optional[float] = None
    exit_rsi: Optional[float] = None
    entry_momentum: Optional[float] = None
    volatility_at_entry: Optional[float] = None
    regime_at_entry: Optional[MarketRegime] = None
    pnl: float
    pnl_percent: float
    is_winner: bool
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None


class LearningSnapshot(BaseModel):
    """A point-in-time snapshot of the learning state."""
    snapshot_id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    total_patterns: int = 0
    active_patterns: int = 0
    total_learnings: int = 0
    avg_pattern_confidence: float = 0.0
    top_patterns: list[Pattern] = Field(default_factory=list)
    recent_learnings: list[Learning] = Field(default_factory=list)
    parameter_performance: dict[str, ParameterPerformance] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
