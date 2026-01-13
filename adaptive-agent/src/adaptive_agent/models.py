"""
Data models for the Adaptive Agent.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    """Types of decisions the agent can make."""
    PARAMETER_ADJUSTMENT = "PARAMETER_ADJUSTMENT"
    REGIME_ADAPTATION = "REGIME_ADAPTATION"
    RISK_SCALING = "RISK_SCALING"
    TIMING_OPTIMIZATION = "TIMING_OPTIMIZATION"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    RESUME_TRADING = "RESUME_TRADING"
    NO_ACTION = "NO_ACTION"


class MarketRegime(str, Enum):
    """Market regime classifications."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    VOLATILE = "VOLATILE"
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"


class AgentMode(str, Enum):
    """Agent operating modes."""
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class MarketSnapshot(BaseModel):
    """Point-in-time market conditions."""
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Price data
    tqqq_price: Optional[float] = None
    sqqq_price: Optional[float] = None
    qqq_price: Optional[float] = None
    
    # Indicators
    rsi: float = 50.0
    momentum: float = 0.0
    volatility: float = 0.0
    trend_strength: float = 0.0
    volume_ratio: float = 1.0
    
    # Regime
    regime: MarketRegime = MarketRegime.NEUTRAL
    regime_confidence: float = 0.5
    
    # Time context
    hour_of_day: int = 12
    day_of_week: int = 2
    is_market_open: bool = True


class PositionSnapshot(BaseModel):
    """Current position information."""
    symbol: str
    quantity: int = 0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    side: str = "none"  # long, short, none


class PerformanceSnapshot(BaseModel):
    """Recent performance metrics."""
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Today's performance
    daily_pnl: float = 0.0
    daily_trades: int = 0
    daily_win_rate: float = 0.0
    
    # Recent performance (7 days)
    weekly_pnl: float = 0.0
    weekly_trades: int = 0
    weekly_win_rate: float = 0.0
    
    # Overall metrics
    total_pnl: float = 0.0
    total_trades: int = 0
    overall_win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    
    # Streaks
    current_streak: int = 0  # Positive = wins, negative = losses
    max_win_streak: int = 0
    max_loss_streak: int = 0


class Decision(BaseModel):
    """An agent decision with full context."""
    decision_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Decision details
    decision_type: DecisionType
    action: str
    confidence: float = Field(ge=0.0, le=1.0)
    
    # Parameters (if applicable)
    parameter_name: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    
    # Reasoning
    reasoning: str
    supporting_patterns: list[int] = Field(default_factory=list)
    contributing_factors: list[str] = Field(default_factory=list)
    
    # Context
    market_snapshot: Optional[MarketSnapshot] = None
    performance_snapshot: Optional[PerformanceSnapshot] = None
    
    # Execution
    executed: bool = False
    executed_at: Optional[datetime] = None
    execution_result: Optional[str] = None
    
    # Learning
    outcome_recorded: bool = False
    outcome: Optional[str] = None


class AgentState(BaseModel):
    """Current state of the agent."""
    agent_id: str = "adaptive-agent-001"
    started_at: datetime = Field(default_factory=datetime.now)
    last_cycle_at: Optional[datetime] = None
    
    # Operating state
    is_running: bool = False
    is_paused: bool = False
    mode: AgentMode = AgentMode.PAPER
    
    # Trading state
    trading_enabled: bool = True
    emergency_stop_active: bool = False
    emergency_stop_reason: Optional[str] = None
    
    # Counters
    cycles_completed: int = 0
    decisions_made: int = 0
    decisions_executed: int = 0
    parameter_changes_today: int = 0
    
    # Current context
    current_regime: MarketRegime = MarketRegime.NEUTRAL
    current_positions: list[PositionSnapshot] = Field(default_factory=list)
    
    # Recent decisions
    recent_decisions: list[Decision] = Field(default_factory=list)
    pending_decisions: list[Decision] = Field(default_factory=list)


class CycleResult(BaseModel):
    """Result of a single agent cycle."""
    cycle_number: int
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    
    # Snapshots taken
    market_snapshot: MarketSnapshot
    performance_snapshot: PerformanceSnapshot
    
    # Analysis results
    patterns_matched: int = 0
    recommendations_generated: int = 0
    
    # Decision
    decision: Optional[Decision] = None
    decision_executed: bool = False
    
    # Errors
    errors: list[str] = Field(default_factory=list)


class Alert(BaseModel):
    """An alert generated by the agent."""
    alert_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    severity: str = "info"  # info, warning, critical
    category: str
    message: str
    
    # Context
    related_decision_id: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)
    
    # Notification state
    notified: bool = False
    acknowledged: bool = False
