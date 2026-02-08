# region imports
from AlgorithmImports import *  # type: ignore
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import deque
import math

# SQL Persistence for Trade-Mind MCP integration
try:
    from sql_connector import TradingDBConnector, create_connector  # type: ignore
    HAS_SQL_CONNECTOR = True
except ImportError:
    HAS_SQL_CONNECTOR = False
# endregion

"""
TQQQ/SQQQ Position Trend Following Strategy
==============================================
Strategy: Position trading based on QQQ moving average regime detection
Concept:  Use slow+fast SMAs on QQQ (proxy for NDX) to determine market
          regime, then hold leveraged ETFs for weeks/months.

Regime Detection (using QQQ):
  - BULL:  QQQ > SMA_fast AND QQQ > SMA_slow  → Long TQQQ
  - BEAR:  QQQ < SMA_fast AND QQQ < SMA_slow  → Long SQQQ
           v1.1: BEAR requires stricter confirmation:
           - QQQ must be bear_sma_margin% below slow SMA
           - ROC over bear_momentum_lookback days must be negative
           - bear_confirmation_days consecutive days in bear zone
           If not all met → classified as MIXED (cash)
  - MIXED: QQQ between the two SMAs            → Cash (flat) or reduced position

Key Design Principles:
  - Signal source: QQQ daily closes (proxy for Nasdaq-100)
  - Trade execution: End-of-day only (last 10 minutes of session)
  - Hold period: Weeks to months (not intraday)
  - Position sizing: Dynamic % of portfolio per regime
  - Simplicity: The edge comes from riding trends, not over-optimizing
  - No shorting: SQQQ serves as the bear instrument
  - v1.1: Bear entry is much stricter to avoid whipsaws during corrections

Parameters:
  - sma_fast: Fast SMA period (default 50 days)
  - sma_slow: Slow SMA period (default 200 days)
  - bull_allocation: % of portfolio in TQQQ during bull (default 0.90, used as fixed when dynamic=off)
  - bear_allocation: % of portfolio in SQQQ during bear (default 0.50)
  - use_cash_zone: Whether to go flat when regime is mixed (default true)
  - mixed_allocation: % allocation during mixed regime if not flat (default 0.30)
  - rebalance_threshold: Min allocation drift to trigger rebalance (default 0.05)
  - max_drawdown_exit: Emergency exit if portfolio drawdown exceeds this (0=disabled)
  - bear_confirmation_days: Days to confirm bear regime (default 5, stricter than bull)
  - bear_sma_margin: QQQ must be this % below slow SMA for bear (default 0.02 = 2%)
  - bear_momentum_lookback: ROC lookback for bear momentum check (default 10 days)
  - dynamic_allocation: Enable distance-based position scaling (default false)
  - bull_alloc_min: Min allocation when barely in bull zone (default 0.30)
  - bull_alloc_max: Max allocation when strong bull trend (default 1.00)
  - alloc_scale_max_pct: QQQ distance % from slow SMA that maps to max allocation (default 0.10 = 10%)

Author: Trading Plan Implementation
Version: 1.3.0 (Dynamic Allocation Based on Trend Strength)
"""


class MarketRegime(Enum):
    """QQQ-based market regime classification"""
    BULL = "bull"       # QQQ above both SMAs → long TQQQ
    BEAR = "bear"       # QQQ below both SMAs → long SQQQ
    MIXED = "mixed"     # QQQ between SMAs → cash or reduced
    UNKNOWN = "unknown" # Not enough data


@dataclass
class RegimeChange:
    """Record of a regime transition"""
    timestamp: datetime
    old_regime: str
    new_regime: str
    qqq_price: float
    sma_fast_value: float
    sma_slow_value: float


@dataclass
class PositionTrendTradeRecord:
    """Record of a completed position"""
    symbol: str
    regime: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    hold_duration_days: int
    exit_reason: str


class TQQQPositionTrendAlgorithm(QCAlgorithm):
    """
    Position Trend Following on TQQQ/SQQQ.
    
    Uses QQQ daily SMAs to detect market regime.
    Holds TQQQ in bull trends, SQQQ in bear trends.
    Position trading — holds for weeks/months.
    Trades only in the last 10 minutes of the session.
    """
    
    def Initialize(self):  # type: ignore
        """Initialize algorithm settings, securities, and indicators"""
        
        # =====================================================
        # BASIC SETTINGS
        # =====================================================
        start_date_str = str(self.GetParameter("start-date") or "2025-01-02")
        end_date_str = str(self.GetParameter("end-date") or "2026-01-14")
        
        try:
            start_parts = start_date_str.split("-")
            self.SetStartDate(int(start_parts[0]), int(start_parts[1]), int(start_parts[2]))
        except Exception:
            self.SetStartDate(2025, 1, 2)
        
        try:
            end_parts = end_date_str.split("-")
            self.SetEndDate(int(end_parts[0]), int(end_parts[1]), int(end_parts[2]))
        except Exception:
            self.SetEndDate(2026, 1, 14)
        
        initial_cash = float(self.GetParameter("cash") or 100000)
        self.SetCash(initial_cash)
        self.initial_cash = initial_cash
        self.peak_equity = initial_cash
        
        self.SetBrokerageModel(BrokerageName.Alpaca, AccountType.Margin)
        
        # =====================================================
        # POSITION TREND PARAMETERS
        # =====================================================
        
        # SMA periods for regime detection (on QQQ)
        self.sma_fast_period = int(float(self.GetParameter("sma-fast") or 50))
        self.sma_slow_period = int(float(self.GetParameter("sma-slow") or 200))
        
        # Allocation percentages per regime
        self.bull_allocation = float(self.GetParameter("bull-allocation") or 0.90)    # 90% in TQQQ during bull
        self.bear_allocation = float(self.GetParameter("bear-allocation") or 0.50)    # 50% in SQQQ during bear
        
        # Cash zone behavior
        self.use_cash_zone = str(self.GetParameter("use-cash-zone") or "true").lower() == "true"
        self.mixed_allocation = float(self.GetParameter("mixed-allocation") or 0.30)  # 30% if trading in mixed zone
        self.mixed_instrument = str(self.GetParameter("mixed-instrument") or "tqqq").lower()  # tqqq or sqqq in mixed
        
        # Rebalance threshold — only rebalance if drift exceeds this
        self.rebalance_threshold = float(self.GetParameter("rebalance-threshold") or 0.05)  # 5% drift tolerance
        
        # Emergency drawdown exit (0 = disabled)
        self.max_drawdown_exit = float(self.GetParameter("max-drawdown-exit") or 0.0)
        
        # Confirmation bars — require N consecutive days in new regime before switching
        self.confirmation_days = int(float(self.GetParameter("confirmation-days") or 1))
        
        # =====================================================
        # v1.1: STRICTER BEAR REGIME PARAMETERS
        # =====================================================
        # Bear needs more confirmation than bull (avoid whipsaws during corrections)
        self.bear_confirmation_days = int(float(self.GetParameter("bear-confirmation-days") or 5))
        # QQQ must be this % below slow SMA to qualify as bear (e.g., 0.02 = 2%)
        self.bear_sma_margin = float(self.GetParameter("bear-sma-margin") or 0.02)
        # Rate of Change lookback — ROC must be negative over this many days
        self.bear_momentum_lookback = int(float(self.GetParameter("bear-momentum-lookback") or 10))
        
        # =====================================================
        # v1.3: DYNAMIC ALLOCATION PARAMETERS
        # =====================================================
        # Scale position size based on how far QQQ is from slow SMA
        # Stronger trend (farther from SMA) = larger position
        self.dynamic_allocation = str(self.GetParameter("dynamic-allocation") or "false").lower() == "true"
        self.bull_alloc_min = float(self.GetParameter("bull-alloc-min") or 0.30)   # Min allocation at edge of bull zone
        self.bull_alloc_max = float(self.GetParameter("bull-alloc-max") or 1.00)   # Max allocation at full trend strength
        self.alloc_scale_max_pct = float(self.GetParameter("alloc-scale-max-pct") or 0.10)  # 10% above SMA = max alloc
        
        # End-of-day execution window
        self.eod_hour = 15
        self.eod_minute = 50  # Execute trades at 3:50 PM ET (10 min before close)
        
        # Log parameters
        self.Log(f"[PARAMS] SMA Fast: {self.sma_fast_period}, SMA Slow: {self.sma_slow_period}")
        self.Log(f"[PARAMS] Bull Alloc: {self.bull_allocation:.0%}, Bear Alloc: {self.bear_allocation:.0%}")
        self.Log(f"[PARAMS] Cash Zone: {self.use_cash_zone}, Mixed Alloc: {self.mixed_allocation:.0%}")
        self.Log(f"[PARAMS] Rebalance Threshold: {self.rebalance_threshold:.0%}")
        self.Log(f"[PARAMS] Max DD Exit: {self.max_drawdown_exit:.0%}, Confirm Days: {self.confirmation_days}")
        self.Log(f"[PARAMS] Bear Confirm: {self.bear_confirmation_days}d, Bear Margin: {self.bear_sma_margin:.1%}, Bear ROC Lookback: {self.bear_momentum_lookback}d")
        self.Log(f"[PARAMS] Dynamic Alloc: {self.dynamic_allocation}, Min: {self.bull_alloc_min:.0%}, Max: {self.bull_alloc_max:.0%}, Scale Max: {self.alloc_scale_max_pct:.0%}")
        
        # =====================================================
        # ADD SECURITIES
        # =====================================================
        self.tqqq = self.AddEquity("TQQQ", Resolution.Minute).Symbol
        self.sqqq = self.AddEquity("SQQQ", Resolution.Minute).Symbol
        self.qqq = self.AddEquity("QQQ", Resolution.Minute).Symbol
        
        # =====================================================
        # DAILY BAR CONSOLIDATOR FOR QQQ (regime detection)
        # =====================================================
        self.qqq_daily_consolidator = TradeBarConsolidator(timedelta(days=1))
        self.qqq_daily_consolidator.DataConsolidated += self.OnQQQDailyBar
        self.SubscriptionManager.AddConsolidator(self.qqq, self.qqq_daily_consolidator)
        
        # =====================================================
        # QQQ DAILY CLOSE HISTORY FOR SMAs (manual calculation)
        # =====================================================
        max_lookback = self.sma_slow_period + 10  # Slow SMA needs the most history
        self.qqq_closes: deque = deque(maxlen=max_lookback)
        
        # Current SMA values
        self.sma_fast_value: float = 0.0
        self.sma_slow_value: float = 0.0
        
        # =====================================================
        # REGIME TRACKING
        # =====================================================
        self.current_regime = MarketRegime.UNKNOWN
        self.pending_regime = MarketRegime.UNKNOWN  # Regime waiting for confirmation
        self.pending_regime_count: int = 0          # Days in pending regime
        self.pending_bear_count: int = 0            # v1.1: Separate counter for bear confirmation
        self.regime_start_time: Optional[datetime] = None
        self.regime_history: List[RegimeChange] = []
        
        # =====================================================
        # POSITION TRACKING
        # =====================================================
        self.current_symbol: Optional[Symbol] = None   # Currently held symbol (TQQQ or SQQQ)
        self.entry_price: float = 0.0
        self.entry_time: Optional[datetime] = None
        self.entry_quantity: int = 0
        
        # =====================================================
        # TRADE EXECUTION FLAGS
        # =====================================================
        self.signal_generated_today = False     # Only generate signal once per day
        self.pending_action: Optional[str] = None  # "BUY_TQQQ", "BUY_SQQQ", "GO_FLAT", "REBALANCE", None
        self.pending_allocation: float = 0.0
        self.pending_target_symbol: Optional[Symbol] = None
        
        # Track if we already acted today
        self.last_action_date: Optional[datetime] = None
        
        # =====================================================
        # TRADE HISTORY
        # =====================================================
        self.trade_history: List[PositionTrendTradeRecord] = []
        
        # =====================================================
        # PERFORMANCE TRACKING
        # =====================================================
        self.drawdown_exit_triggered = False
        self.last_qqq_close: float = 0.0
        
        # =====================================================
        # WARMUP — need enough days to build slow SMA
        # =====================================================
        warmup_days = self.sma_slow_period + 20
        self.SetWarmUp(timedelta(days=warmup_days))
        
        # =====================================================
        # SQL PERSISTENCE
        # =====================================================
        sql_enabled_param = self.GetParameter("sql_enabled") or "true"
        self.sql_enabled = str(sql_enabled_param).lower() == "true"
        self.db: Optional[TradingDBConnector] = None
        
        if HAS_SQL_CONNECTOR and self.sql_enabled:
            try:
                self.db = create_connector(
                    algorithm=self,
                    server=str(self.GetParameter("sql_server") or "localhost"),
                    database=str(self.GetParameter("sql_database") or "TradingDB"),
                    enabled=True
                )
                
                session_type = "BACKTEST" if not self.LiveMode else "LIVE"
                params_snapshot = {
                    "strategy": "POSITION_TREND",
                    "sma_fast": self.sma_fast_period,
                    "sma_slow": self.sma_slow_period,
                    "bull_allocation": self.bull_allocation,
                    "bear_allocation": self.bear_allocation,
                    "use_cash_zone": self.use_cash_zone,
                    "mixed_allocation": self.mixed_allocation,
                    "confirmation_days": self.confirmation_days,
                    "max_drawdown_exit": self.max_drawdown_exit,
                }
                
                session_id = str(self.GetParameter("session-id") or "")
                if not session_id or session_id == "default":
                    session_id = None
                
                self.db.start_session(session_type, params_snapshot, session_id)
                self.Debug(f"[SQL] Session started: {self.db.session_id}")
                
            except Exception as e:
                self.Debug(f"[SQL] Failed to initialize: {e}")
                self.db = None
        
        self.Debug("TQQQPositionTrendAlgorithm v1.3 Initialized")
    
    # =========================================================
    # DAILY BAR HANDLER — QQQ REGIME DETECTION
    # =========================================================
    
    def OnQQQDailyBar(self, sender, bar: TradeBar) -> None:
        """
        Handle completed QQQ daily bar.
        Calculate SMAs, detect regime, set pending action.
        """
        self.qqq_closes.append(float(bar.Close))
        self.last_qqq_close = float(bar.Close)
        
        # Need enough history for slow SMA
        if len(self.qqq_closes) < self.sma_slow_period:
            return
        
        if self.IsWarmingUp:
            # Still compute SMAs during warmup to be ready
            closes_list = list(self.qqq_closes)
            self.sma_fast_value = sum(closes_list[-self.sma_fast_period:]) / self.sma_fast_period
            self.sma_slow_value = sum(closes_list[-self.sma_slow_period:]) / self.sma_slow_period
            return
        
        # Calculate SMAs
        closes_list = list(self.qqq_closes)
        self.sma_fast_value = sum(closes_list[-self.sma_fast_period:]) / self.sma_fast_period
        self.sma_slow_value = sum(closes_list[-self.sma_slow_period:]) / self.sma_slow_period
        
        qqq_price = float(bar.Close)
        
        # Determine raw regime
        raw_regime = self._classify_regime(qqq_price)
        
        # Apply confirmation filter
        new_regime = self._apply_confirmation(raw_regime)
        
        if new_regime != self.current_regime:
            old_regime = self.current_regime
            
            # Log regime change
            change = RegimeChange(
                timestamp=self.Time,
                old_regime=old_regime.value,
                new_regime=new_regime.value,
                qqq_price=qqq_price,
                sma_fast_value=self.sma_fast_value,
                sma_slow_value=self.sma_slow_value,
            )
            self.regime_history.append(change)
            
            self.Log(f"[REGIME] {old_regime.value} → {new_regime.value} | "
                     f"QQQ={qqq_price:.2f}, SMA{self.sma_fast_period}={self.sma_fast_value:.2f}, "
                     f"SMA{self.sma_slow_period}={self.sma_slow_value:.2f}")
            
            self.current_regime = new_regime
            self.regime_start_time = self.Time
        
        # Set pending action based on current regime
        self._generate_signal()
    
    def _classify_regime(self, qqq_price: float) -> MarketRegime:
        """Classify market regime based on QQQ price vs SMAs.
        
        v1.1: Bear regime has stricter requirements:
        - QQQ must be below BOTH SMAs (same as before)
        - QQQ must be bear_sma_margin% below the slow SMA
        - Rate of change over bear_momentum_lookback days must be negative
        If below both SMAs but criteria not fully met → MIXED (cash)
        """
        if self.sma_fast_value <= 0 or self.sma_slow_value <= 0:
            return MarketRegime.UNKNOWN
        
        above_fast = qqq_price > self.sma_fast_value
        above_slow = qqq_price > self.sma_slow_value
        
        if above_fast and above_slow:
            return MarketRegime.BULL
        elif not above_fast and not above_slow:
            # v1.1: Stricter bear detection
            # Check 1: QQQ must be bear_sma_margin% below the slow SMA
            bear_threshold = self.sma_slow_value * (1.0 - self.bear_sma_margin)
            if qqq_price > bear_threshold:
                # Below both SMAs but not far enough below → MIXED (cash)
                return MarketRegime.MIXED
            
            # Check 2: Rate of change must be negative (momentum confirming downtrend)
            if len(self.qqq_closes) >= self.bear_momentum_lookback:
                closes_list = list(self.qqq_closes)
                price_n_days_ago = closes_list[-self.bear_momentum_lookback]
                roc = (qqq_price - price_n_days_ago) / price_n_days_ago if price_n_days_ago > 0 else 0
                if roc >= 0:
                    # Price is not declining → correction might be recovering → MIXED
                    return MarketRegime.MIXED
            
            return MarketRegime.BEAR
        else:
            return MarketRegime.MIXED
    
    def _apply_confirmation(self, raw_regime: MarketRegime) -> MarketRegime:
        """
        Require N consecutive days in a new regime before switching.
        v1.1: Bear transitions use bear_confirmation_days (stricter).
        Bull transitions use confirmation_days (responsive).
        """
        # Determine how many days are needed for this transition
        if raw_regime == MarketRegime.BEAR:
            required_days = self.bear_confirmation_days
        else:
            required_days = self.confirmation_days
        
        if required_days <= 1 and raw_regime != MarketRegime.BEAR:
            return raw_regime
        
        if raw_regime == self.current_regime:
            # Already in this regime — reset pending
            self.pending_regime = self.current_regime
            self.pending_regime_count = 0
            return self.current_regime
        
        if raw_regime == self.pending_regime:
            self.pending_regime_count += 1
            if self.pending_regime_count >= required_days:
                # Confirmed — switch
                self.pending_regime_count = 0
                return raw_regime
            else:
                return self.current_regime  # Not yet confirmed
        else:
            # New pending regime
            self.pending_regime = raw_regime
            self.pending_regime_count = 1
            if required_days <= 1:
                return raw_regime
            return self.current_regime
    
    def _calculate_dynamic_allocation(self, base_allocation: float, regime: MarketRegime) -> float:
        """
        v1.3: Scale allocation based on QQQ distance from slow SMA.
        
        In bull: farther above SMA → larger position (trend is strong)
        In bear: farther below SMA → larger position (bear trend is strong)
        When dynamic_allocation is False, returns base_allocation unchanged.
        
        Formula (linear scaling):
          distance_pct = abs(qqq_price - sma_slow) / sma_slow
          scale = clamp(distance_pct / alloc_scale_max_pct, 0, 1)
          allocation = bull_alloc_min + scale * (bull_alloc_max - bull_alloc_min)
        """
        if not self.dynamic_allocation:
            return base_allocation
        
        if self.sma_slow_value <= 0 or self.last_qqq_close <= 0:
            return base_allocation
        
        # Calculate distance from slow SMA
        distance_pct = abs(self.last_qqq_close - self.sma_slow_value) / self.sma_slow_value
        
        # Linear scale: 0 at SMA, 1 at alloc_scale_max_pct away
        if self.alloc_scale_max_pct > 0:
            scale = min(distance_pct / self.alloc_scale_max_pct, 1.0)
        else:
            scale = 1.0
        
        # For bull regime, use bull_alloc_min/max
        if regime == MarketRegime.BULL:
            dynamic_alloc = self.bull_alloc_min + scale * (self.bull_alloc_max - self.bull_alloc_min)
        elif regime == MarketRegime.BEAR:
            # Bear uses same scaling but with bear_allocation as ceiling
            bear_min = self.bull_alloc_min  # Reuse min for symmetry
            dynamic_alloc = bear_min + scale * (self.bear_allocation - bear_min)
        else:
            return base_allocation
        
        # Clamp to valid range
        dynamic_alloc = max(0.0, min(dynamic_alloc, 1.0))
        
        self.Log(f"[DYNAMIC] QQQ={self.last_qqq_close:.2f} SMA{self.sma_slow_period}={self.sma_slow_value:.2f} "
                 f"dist={distance_pct:.2%} scale={scale:.2f} alloc={dynamic_alloc:.1%}")
        
        return dynamic_alloc
    
    def _generate_signal(self) -> None:
        """
        Generate trading signal based on current regime.
        Sets pending_action for end-of-day execution.
        v1.3: Uses dynamic allocation scaling when enabled.
        """
        if self.drawdown_exit_triggered:
            self.pending_action = "GO_FLAT"
            self.pending_allocation = 0.0
            return
        
        target_symbol = None
        target_allocation = 0.0
        
        if self.current_regime == MarketRegime.BULL:
            target_symbol = self.tqqq
            target_allocation = self._calculate_dynamic_allocation(self.bull_allocation, MarketRegime.BULL)
        
        elif self.current_regime == MarketRegime.BEAR:
            target_symbol = self.sqqq
            target_allocation = self._calculate_dynamic_allocation(self.bear_allocation, MarketRegime.BEAR)
        
        elif self.current_regime == MarketRegime.MIXED:
            if self.use_cash_zone:
                # Go flat in mixed zone
                target_symbol = None
                target_allocation = 0.0
            else:
                # Reduced position in mixed zone
                if self.mixed_instrument == "tqqq":
                    target_symbol = self.tqqq
                else:
                    target_symbol = self.sqqq
                target_allocation = self.mixed_allocation
        
        else:
            # UNKNOWN — stay flat
            target_symbol = None
            target_allocation = 0.0
        
        # Determine action needed
        current_holdings_tqqq = self.Portfolio[self.tqqq].Quantity
        current_holdings_sqqq = self.Portfolio[self.sqqq].Quantity
        is_holding_tqqq = current_holdings_tqqq > 0
        is_holding_sqqq = current_holdings_sqqq > 0
        
        if target_symbol is None and not is_holding_tqqq and not is_holding_sqqq:
            # Already flat, nothing to do
            self.pending_action = None
            return
        
        if target_symbol is None:
            # Need to go flat
            self.pending_action = "GO_FLAT"
            self.pending_allocation = 0.0
            self.pending_target_symbol = None
            return
        
        # Need to switch sides?
        if target_symbol == self.tqqq and is_holding_sqqq:
            self.pending_action = "SWITCH_TO_TQQQ"
            self.pending_allocation = target_allocation
            self.pending_target_symbol = self.tqqq
            return
        
        if target_symbol == self.sqqq and is_holding_tqqq:
            self.pending_action = "SWITCH_TO_SQQQ"
            self.pending_allocation = target_allocation
            self.pending_target_symbol = self.sqqq
            return
        
        # Already on correct side — check for rebalance
        if target_symbol == self.tqqq and is_holding_tqqq:
            current_pct = self._get_holding_pct(self.tqqq)
            if abs(current_pct - target_allocation) > self.rebalance_threshold:
                self.pending_action = "REBALANCE"
                self.pending_allocation = target_allocation
                self.pending_target_symbol = self.tqqq
            else:
                self.pending_action = None
            return
        
        if target_symbol == self.sqqq and is_holding_sqqq:
            current_pct = self._get_holding_pct(self.sqqq)
            if abs(current_pct - target_allocation) > self.rebalance_threshold:
                self.pending_action = "REBALANCE"
                self.pending_allocation = target_allocation
                self.pending_target_symbol = self.sqqq
            else:
                self.pending_action = None
            return
        
        # Not holding anything, need to enter
        if target_symbol == self.tqqq:
            self.pending_action = "BUY_TQQQ"
        else:
            self.pending_action = "BUY_SQQQ"
        self.pending_allocation = target_allocation
        self.pending_target_symbol = target_symbol
    
    def _get_holding_pct(self, symbol: Symbol) -> float:
        """Get current holding as % of portfolio equity."""
        equity = self.Portfolio.TotalPortfolioValue
        if equity <= 0:
            return 0.0
        holding_value = abs(self.Portfolio[symbol].HoldingsValue)
        return holding_value / equity
    
    # =========================================================
    # INTRADAY — END-OF-DAY EXECUTION
    # =========================================================
    
    def OnData(self, data: Slice) -> None:
        """
        Process every minute bar.
        Execute trades only in the last 10 minutes (3:50 PM ET).
        Check for emergency drawdown exit.
        """
        if self.IsWarmingUp:
            return
        
        # Check emergency drawdown
        if self.max_drawdown_exit > 0 and not self.drawdown_exit_triggered:
            current_equity = self.Portfolio.TotalPortfolioValue
            if current_equity > self.peak_equity:
                self.peak_equity = current_equity
            
            drawdown = (self.peak_equity - current_equity) / self.peak_equity
            if drawdown >= self.max_drawdown_exit:
                self.Log(f"[EMERGENCY] Drawdown {drawdown:.1%} exceeds limit {self.max_drawdown_exit:.1%}")
                self.drawdown_exit_triggered = True
                self.pending_action = "GO_FLAT"
        
        # Only execute at end of day
        if self.Time.hour != self.eod_hour or self.Time.minute != self.eod_minute:
            return
        
        # Don't act twice on the same day
        if self.last_action_date and self.last_action_date.date() == self.Time.date():
            return
        
        if self.pending_action is None:
            return
        
        # Execute the pending action
        self._execute_action(data)
    
    def _execute_action(self, data: Slice) -> None:
        """Execute the pending trading action."""
        action = self.pending_action
        self.pending_action = None
        self.last_action_date = self.Time
        
        if action == "GO_FLAT":
            self._close_all_positions("regime_change_flat")
        
        elif action == "SWITCH_TO_TQQQ":
            self._close_all_positions("regime_switch")
            self._enter_position(self.tqqq, self.pending_allocation, "BULL")
        
        elif action == "SWITCH_TO_SQQQ":
            self._close_all_positions("regime_switch")
            self._enter_position(self.sqqq, self.pending_allocation, "BEAR")
        
        elif action == "BUY_TQQQ":
            self._enter_position(self.tqqq, self.pending_allocation, "BULL")
        
        elif action == "BUY_SQQQ":
            self._enter_position(self.sqqq, self.pending_allocation, "BEAR")
        
        elif action == "REBALANCE":
            self._rebalance_position(self.pending_target_symbol, self.pending_allocation)
    
    def _enter_position(self, symbol: Symbol, allocation: float, regime: str) -> None:
        """Enter a new position at the target allocation."""
        equity = self.Portfolio.TotalPortfolioValue
        target_value = equity * allocation
        price = self.Securities[symbol].Price
        
        if price <= 0:
            self.Log(f"[SKIP] {symbol.Value} price is 0")
            return
        
        quantity = int(target_value / price)
        if quantity <= 0:
            self.Log(f"[SKIP] Computed quantity is 0 for {symbol.Value}")
            return
        
        ticket = self.MarketOrder(symbol, quantity)
        
        self.current_symbol = symbol
        self.entry_price = price
        self.entry_time = self.Time
        self.entry_quantity = quantity
        
        self.Log(f"[ENTER] {regime} → {symbol.Value} x{quantity} @ ~${price:.2f} "
                 f"({allocation:.0%} of ${equity:,.0f})")
    
    def _close_all_positions(self, reason: str) -> None:
        """Close all positions and record trades."""
        for symbol in [self.tqqq, self.sqqq]:
            qty = self.Portfolio[symbol].Quantity
            if qty != 0:
                price = self.Securities[symbol].Price
                
                # Record completed trade
                if self.entry_time and self.current_symbol == symbol:
                    pnl = (price - self.entry_price) * qty
                    pnl_pct = (price / self.entry_price - 1.0) if self.entry_price > 0 else 0.0
                    hold_days = (self.Time - self.entry_time).days if self.entry_time else 0
                    
                    regime = "BULL" if symbol == self.tqqq else "BEAR"
                    record = PositionTrendTradeRecord(
                        symbol=str(symbol.Value),
                        regime=regime,
                        entry_time=self.entry_time,
                        exit_time=self.Time,
                        entry_price=self.entry_price,
                        exit_price=price,
                        quantity=qty,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        hold_duration_days=hold_days,
                        exit_reason=reason,
                    )
                    self.trade_history.append(record)
                    
                    self.Log(f"[EXIT] {symbol.Value} x{qty} @ ${price:.2f} | "
                             f"P&L: ${pnl:,.2f} ({pnl_pct:+.2%}) | "
                             f"Held: {hold_days}d | Reason: {reason}")
                
                self.Liquidate(symbol)
                
                # SQL trade logging (round-trip)
                if self.db and self.entry_time:
                    try:
                        self.db.log_trade(
                            symbol=str(symbol.Value),
                            side="BUY",
                            quantity=abs(qty),
                            entry_price=self.entry_price,
                            exit_price=price,
                            entry_time=self.entry_time,
                            exit_time=self.Time,
                            entry_reason=f"regime_{regime.lower()}",
                            exit_reason=reason,
                        )
                    except Exception as e:
                        self.Debug(f"[SQL] Trade log failed: {e}")
        
        self.current_symbol = None
        self.entry_price = 0.0
        self.entry_time = None
        self.entry_quantity = 0
    
    def _rebalance_position(self, symbol: Symbol, target_allocation: float) -> None:
        """Rebalance existing position to target allocation."""
        equity = self.Portfolio.TotalPortfolioValue
        target_value = equity * target_allocation
        current_value = abs(self.Portfolio[symbol].HoldingsValue)
        price = self.Securities[symbol].Price
        
        if price <= 0:
            return
        
        delta_value = target_value - current_value
        delta_shares = int(delta_value / price)
        
        if abs(delta_shares) < 1:
            return
        
        self.MarketOrder(symbol, delta_shares)
        
        self.Log(f"[REBALANCE] {symbol.Value}: {delta_shares:+d} shares | "
                 f"Current: {current_value/equity:.1%} → Target: {target_allocation:.1%}")
    
    # =========================================================
    # END OF BACKTEST
    # =========================================================
    
    def OnEndOfAlgorithm(self) -> None:
        """Log final summary statistics."""
        # Close any remaining position
        self._close_all_positions("end_of_backtest")
        
        # Summary
        total_pnl = sum(t.pnl for t in self.trade_history)
        winners = [t for t in self.trade_history if t.pnl > 0]
        losers = [t for t in self.trade_history if t.pnl <= 0]
        
        self.Log(f"\n{'='*60}")
        self.Log(f"POSITION TREND FOLLOWING - FINAL SUMMARY")
        self.Log(f"{'='*60}")
        self.Log(f"Total Trades: {len(self.trade_history)}")
        self.Log(f"Winners: {len(winners)}, Losers: {len(losers)}")
        
        if self.trade_history:
            win_rate = len(winners) / len(self.trade_history)
            avg_hold = sum(t.hold_duration_days for t in self.trade_history) / len(self.trade_history)
            self.Log(f"Win Rate: {win_rate:.1%}")
            self.Log(f"Total P&L: ${total_pnl:,.2f}")
            self.Log(f"Avg Hold Duration: {avg_hold:.1f} days")
            
            if winners:
                avg_win = sum(t.pnl for t in winners) / len(winners)
                self.Log(f"Avg Win: ${avg_win:,.2f}")
            if losers:
                avg_loss = sum(t.pnl for t in losers) / len(losers)
                self.Log(f"Avg Loss: ${avg_loss:,.2f}")
        
        self.Log(f"\nRegime Changes: {len(self.regime_history)}")
        for rc in self.regime_history[-10:]:  # Last 10 changes
            self.Log(f"  {rc.timestamp}: {rc.old_regime} → {rc.new_regime} "
                     f"(QQQ=${rc.qqq_price:.2f})")
        
        self.Log(f"{'='*60}")
        
        # Close SQL session
        if self.db:
            try:
                self.db.end_session()
            except Exception:
                pass
