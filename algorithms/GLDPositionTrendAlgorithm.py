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
GLD Position Trend Following Strategy
========================================
Strategy: Position trading based on GLD's own moving average trend detection
Concept:  Use slow+fast SMAs on GLD to determine gold trend,
          then hold GLD (non-leveraged) during uptrends, cash during downtrends.

This is the HEDGING companion to TQQQPositionTrendAlgorithm (Config B).
- TQQQ strategy profits in equity bull markets
- GLD strategy profits in uncertainty/inflation/USD weakness
- The two are uncorrelated, reducing portfolio-level drawdowns

Regime Detection (using GLD itself):
  - BULL:  GLD > SMA_fast AND GLD > SMA_slow  → Long GLD
  - BEAR:  GLD < SMA_fast AND GLD < SMA_slow  → Cash (flat)
  - MIXED: GLD between the two SMAs            → Cash (flat) or reduced position

Key Design Principles:
  - Signal source: GLD daily closes (direct, not a proxy)
  - Trade execution: End-of-day only (last 10 minutes of session)
  - Hold period: Weeks to months (not intraday)
  - Position sizing: Dynamic % of portfolio per regime
  - Simplicity: Same proven SMA crossover logic as TQQQ strategy
  - No leverage: GLD is non-leveraged, no decay risk

Parameters:
  - sma_fast: Fast SMA period (default 50 days)
  - sma_slow: Slow SMA period (default 200 days)
  - bull_allocation: % of portfolio in GLD during bull (default 0.90)
  - bear_allocation: % of portfolio in cash during bear (default 0 = all cash)
  - use_cash_zone: Whether to go flat when regime is mixed (default true)
  - mixed_allocation: % allocation during mixed regime if not flat (default 0)
  - rebalance_threshold: Min allocation drift to trigger rebalance (default 0.05)
  - max_drawdown_exit: Emergency exit if portfolio drawdown exceeds this (0=disabled)
  - confirmation_days: Days to confirm regime change (default 1)

Author: Trading Plan Implementation
Version: 1.0.0 (GLD Position Trend Following - Hedge Strategy)
"""


class GoldRegime(Enum):
    """GLD-based trend classification"""
    BULL = "bull"       # GLD above both SMAs → long GLD
    BEAR = "bear"       # GLD below both SMAs → cash
    MIXED = "mixed"     # GLD between SMAs → cash or reduced
    UNKNOWN = "unknown" # Not enough data


@dataclass
class GoldRegimeChange:
    """Record of a regime transition"""
    timestamp: datetime
    old_regime: str
    new_regime: str
    gld_price: float
    sma_fast_value: float
    sma_slow_value: float


@dataclass
class GLDTradeRecord:
    """Record of a completed GLD position"""
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


class GLDPositionTrendAlgorithm(QCAlgorithm):
    """
    Position Trend Following on GLD.
    
    Uses GLD's own daily SMAs to detect gold trend.
    Holds GLD in uptrends, cash in downtrends.
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
        # GLD TREND PARAMETERS
        # =====================================================
        
        # SMA periods for trend detection (on GLD itself)
        self.sma_fast_period = int(float(self.GetParameter("sma-fast") or 50))
        self.sma_slow_period = int(float(self.GetParameter("sma-slow") or 200))
        
        # Allocation percentages per regime
        self.bull_allocation = float(self.GetParameter("bull-allocation") or 0.90)    # 90% in GLD during uptrend
        self.bear_allocation = float(self.GetParameter("bear-allocation") or 0.0)     # 0% = all cash during downtrend
        
        # Cash zone behavior
        self.use_cash_zone = str(self.GetParameter("use-cash-zone") or "true").lower() == "true"
        self.mixed_allocation = float(self.GetParameter("mixed-allocation") or 0.0)   # 0% in mixed zone
        
        # Rebalance threshold — only rebalance if drift exceeds this
        self.rebalance_threshold = float(self.GetParameter("rebalance-threshold") or 0.05)  # 5% drift tolerance
        
        # Emergency drawdown exit (0 = disabled)
        self.max_drawdown_exit = float(self.GetParameter("max-drawdown-exit") or 0.0)
        
        # Confirmation bars — require N consecutive days in new regime before switching
        self.confirmation_days = int(float(self.GetParameter("confirmation-days") or 1))
        
        # Signal mode: "price" = price vs SMAs (original), "crossover" = SMA fast vs SMA slow
        # "breakout" = buy on N-day high when SMA_fast > SMA_slow, exit on death cross or N-day low
        # Breakout mode captures gold's spiking nature within confirmed uptrends
        self.signal_mode = str(self.GetParameter("signal-mode") or "price").lower()
        
        # Breakout lookback — only used in "breakout" mode
        # Buy when GLD hits N-day high (during uptrend), sell on N-day low or death cross
        self.breakout_lookback = int(float(self.GetParameter("breakout-lookback") or 20))
        
        # End-of-day execution window
        self.eod_hour = 15
        self.eod_minute = 50  # Execute trades at 3:50 PM ET (10 min before close)
        
        # Log parameters
        self.Log(f"[PARAMS] SMA Fast: {self.sma_fast_period}, SMA Slow: {self.sma_slow_period}")
        self.Log(f"[PARAMS] Bull Alloc: {self.bull_allocation:.0%}, Bear Alloc: {self.bear_allocation:.0%}")
        self.Log(f"[PARAMS] Cash Zone: {self.use_cash_zone}, Mixed Alloc: {self.mixed_allocation:.0%}")
        self.Log(f"[PARAMS] Rebalance Threshold: {self.rebalance_threshold:.0%}")
        self.Log(f"[PARAMS] Max DD Exit: {self.max_drawdown_exit:.0%}, Confirm Days: {self.confirmation_days}")
        self.Log(f"[PARAMS] Signal Mode: {self.signal_mode}, Breakout Lookback: {self.breakout_lookback}")
        
        # =====================================================
        # ADD SECURITIES — GLD only (simple!)
        # =====================================================
        self.gld = self.AddEquity("GLD", Resolution.Minute).Symbol
        
        # =====================================================
        # DAILY BAR CONSOLIDATOR FOR GLD (trend detection)
        # =====================================================
        self.gld_daily_consolidator = TradeBarConsolidator(timedelta(days=1))
        self.gld_daily_consolidator.DataConsolidated += self.OnGLDDailyBar
        self.SubscriptionManager.AddConsolidator(self.gld, self.gld_daily_consolidator)
        
        # =====================================================
        # GLD DAILY CLOSE HISTORY FOR SMAs (manual calculation)
        # =====================================================
        max_lookback = max(self.sma_slow_period + 10, self.breakout_lookback + 10)
        self.gld_closes: deque = deque(maxlen=max_lookback)
        self.gld_highs: deque = deque(maxlen=max_lookback)   # For breakout detection
        self.gld_lows: deque = deque(maxlen=max_lookback)    # For breakout exit
        
        # Current SMA values
        self.sma_fast_value: float = 0.0
        self.sma_slow_value: float = 0.0
        
        # =====================================================
        # REGIME TRACKING
        # =====================================================
        self.current_regime = GoldRegime.UNKNOWN
        self.pending_regime = GoldRegime.UNKNOWN
        self.pending_regime_count: int = 0
        self.regime_start_time: Optional[datetime] = None
        self.regime_history: List[GoldRegimeChange] = []
        
        # =====================================================
        # POSITION TRACKING
        # =====================================================
        self.entry_price: float = 0.0
        self.entry_time: Optional[datetime] = None
        self.entry_quantity: int = 0
        
        # =====================================================
        # TRADE EXECUTION FLAGS
        # =====================================================
        self.signal_generated_today = False
        self.pending_action: Optional[str] = None  # "BUY_GLD", "GO_FLAT", "REBALANCE", None
        self.pending_allocation: float = 0.0
        
        # Track if we already acted today
        self.last_action_date: Optional[datetime] = None
        
        # =====================================================
        # TRADE HISTORY
        # =====================================================
        self.trade_history: List[GLDTradeRecord] = []
        
        # =====================================================
        # PERFORMANCE TRACKING
        # =====================================================
        self.drawdown_exit_triggered = False
        self.last_gld_close: float = 0.0
        
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
                    "strategy": "GLD_POSITION_TREND",
                    "sma_fast": self.sma_fast_period,
                    "sma_slow": self.sma_slow_period,
                    "bull_allocation": self.bull_allocation,
                    "bear_allocation": self.bear_allocation,
                    "use_cash_zone": self.use_cash_zone,
                    "mixed_allocation": self.mixed_allocation,
                    "confirmation_days": self.confirmation_days,
                    "max_drawdown_exit": self.max_drawdown_exit,
                    "signal_mode": self.signal_mode,
                    "breakout_lookback": self.breakout_lookback,
                }
                
                session_id = str(self.GetParameter("session-id") or "")
                if not session_id or session_id == "default":
                    session_id = None
                
                self.db.start_session(session_type, params_snapshot, session_id)
                self.Debug(f"[SQL] Session started: {self.db.session_id}")
                
            except Exception as e:
                self.Debug(f"[SQL] Failed to initialize: {e}")
                self.db = None
        
        self.Debug("GLDPositionTrendAlgorithm v1.0 Initialized")
    
    # =========================================================
    # DAILY BAR HANDLER — GLD TREND DETECTION
    # =========================================================
    
    def OnGLDDailyBar(self, sender, bar: TradeBar) -> None:
        """
        Handle completed GLD daily bar.
        Calculate SMAs, detect trend, set pending action.
        """
        self.gld_closes.append(float(bar.Close))
        self.gld_highs.append(float(bar.High))
        self.gld_lows.append(float(bar.Low))
        self.last_gld_close = float(bar.Close)
        
        # Need enough history for slow SMA
        if len(self.gld_closes) < self.sma_slow_period:
            return
        
        if self.IsWarmingUp:
            # Still compute SMAs during warmup to be ready
            closes_list = list(self.gld_closes)
            self.sma_fast_value = sum(closes_list[-self.sma_fast_period:]) / self.sma_fast_period
            self.sma_slow_value = sum(closes_list[-self.sma_slow_period:]) / self.sma_slow_period
            return
        
        # Calculate SMAs
        closes_list = list(self.gld_closes)
        self.sma_fast_value = sum(closes_list[-self.sma_fast_period:]) / self.sma_fast_period
        self.sma_slow_value = sum(closes_list[-self.sma_slow_period:]) / self.sma_slow_period
        
        gld_price = float(bar.Close)
        
        # Determine raw regime
        raw_regime = self._classify_regime(gld_price)
        
        # Apply confirmation filter
        new_regime = self._apply_confirmation(raw_regime)
        
        if new_regime != self.current_regime:
            old_regime = self.current_regime
            
            # Log regime change
            change = GoldRegimeChange(
                timestamp=self.Time,
                old_regime=old_regime.value,
                new_regime=new_regime.value,
                gld_price=gld_price,
                sma_fast_value=self.sma_fast_value,
                sma_slow_value=self.sma_slow_value,
            )
            self.regime_history.append(change)
            
            self.Log(f"[REGIME] {old_regime.value} → {new_regime.value} | "
                     f"GLD={gld_price:.2f}, SMA{self.sma_fast_period}={self.sma_fast_value:.2f}, "
                     f"SMA{self.sma_slow_period}={self.sma_slow_value:.2f}")
            
            self.current_regime = new_regime
            self.regime_start_time = self.Time
        
        # Set pending action based on current regime
        self._generate_signal()
    
    def _classify_regime(self, gld_price: float) -> GoldRegime:
        """Classify gold trend.
        
        Three modes:
          'price':     BULL if price > SMA_fast AND price > SMA_slow
          'crossover': BULL if SMA_fast > SMA_slow (golden/death cross)
          'breakout':  Uses SMA crossover for trend direction, but entry/exit
                       is handled separately in _generate_signal via breakout logic.
                       Regime here just tracks the macro trend filter.
        """
        if self.sma_fast_value <= 0 or self.sma_slow_value <= 0:
            return GoldRegime.UNKNOWN
        
        if self.signal_mode in ("crossover", "breakout"):
            # SMA crossover: only two states (BULL / BEAR), no MIXED
            if self.sma_fast_value > self.sma_slow_value:
                return GoldRegime.BULL
            else:
                return GoldRegime.BEAR
        else:
            # Original: price vs both SMAs
            above_fast = gld_price > self.sma_fast_value
            above_slow = gld_price > self.sma_slow_value
            
            if above_fast and above_slow:
                return GoldRegime.BULL
            elif not above_fast and not above_slow:
                return GoldRegime.BEAR
            else:
                return GoldRegime.MIXED
    
    def _apply_confirmation(self, raw_regime: GoldRegime) -> GoldRegime:
        """
        Require N consecutive days in a new regime before switching.
        Reduces whipsaws around the SMA crossover points.
        """
        if self.confirmation_days <= 1:
            return raw_regime
        
        if raw_regime == self.current_regime:
            self.pending_regime = self.current_regime
            self.pending_regime_count = 0
            return self.current_regime
        
        if raw_regime == self.pending_regime:
            self.pending_regime_count += 1
            if self.pending_regime_count >= self.confirmation_days:
                self.pending_regime_count = 0
                return raw_regime
            else:
                return self.current_regime
        else:
            self.pending_regime = raw_regime
            self.pending_regime_count = 1
            if self.confirmation_days <= 1:
                return raw_regime
            return self.current_regime
    
    def _generate_signal(self) -> None:
        """
        Generate trading signal based on current regime.
        Sets pending_action for end-of-day execution.
        
        In breakout mode:
          - Trend filter: SMA_fast > SMA_slow (uptrend confirmed)
          - Entry: GLD closes at N-day high → buy (momentum breakout)
          - Hold: Stay invested as long as trend intact
          - Exit: SMA_fast < SMA_slow (death cross) OR GLD closes at N-day low
        """
        if self.drawdown_exit_triggered:
            self.pending_action = "GO_FLAT"
            self.pending_allocation = 0.0
            return
        
        # ===== BREAKOUT MODE =====
        if self.signal_mode == "breakout":
            self._generate_breakout_signal()
            return
        
        # ===== PRICE / CROSSOVER MODE (original) =====
        target_allocation = 0.0
        want_position = False
        
        if self.current_regime == GoldRegime.BULL:
            target_allocation = self.bull_allocation
            want_position = True
        
        elif self.current_regime == GoldRegime.BEAR:
            target_allocation = self.bear_allocation
            want_position = target_allocation > 0
        
        elif self.current_regime == GoldRegime.MIXED:
            if self.use_cash_zone:
                target_allocation = 0.0
                want_position = False
            else:
                target_allocation = self.mixed_allocation
                want_position = target_allocation > 0
        
        else:
            # UNKNOWN — stay flat
            target_allocation = 0.0
            want_position = False
        
        # Determine action needed
        current_holdings = self.Portfolio[self.gld].Quantity
        is_holding = current_holdings > 0
        
        if not want_position and not is_holding:
            # Already flat, nothing to do
            self.pending_action = None
            return
        
        if not want_position and is_holding:
            # Need to go flat
            self.pending_action = "GO_FLAT"
            self.pending_allocation = 0.0
            return
        
        if want_position and not is_holding:
            # Need to enter
            self.pending_action = "BUY_GLD"
            self.pending_allocation = target_allocation
            return
        
        # Already holding — check for rebalance
        if want_position and is_holding:
            current_pct = self._get_holding_pct()
            if abs(current_pct - target_allocation) > self.rebalance_threshold:
                self.pending_action = "REBALANCE"
                self.pending_allocation = target_allocation
            else:
                self.pending_action = None
    
    def _generate_breakout_signal(self) -> None:
        """
        Breakout-within-trend signal generation.
        
        Logic:
          1. TREND FILTER: SMA_fast > SMA_slow → uptrend confirmed
          2. ENTRY: Current close >= highest high of last N days → breakout, buy
          3. HOLD: Stay invested while trend intact
          4. EXIT: SMA_fast < SMA_slow (death cross) → sell everything
                   OR close <= lowest low of last N days → momentum exit
        
        This captures gold's tendency to spike in strong moves while
        filtering out choppy sideways periods via the trend filter.
        """
        is_holding = self.Portfolio[self.gld].Quantity > 0
        
        # Not enough data for breakout lookback
        if len(self.gld_highs) < self.breakout_lookback or len(self.gld_lows) < self.breakout_lookback:
            self.pending_action = None
            return
        
        gld_close = self.last_gld_close
        
        # N-day high/low channels (excluding today)
        recent_highs = list(self.gld_highs)[-self.breakout_lookback - 1:-1]
        recent_lows = list(self.gld_lows)[-self.breakout_lookback - 1:-1]
        
        if not recent_highs or not recent_lows:
            self.pending_action = None
            return
        
        n_day_high = max(recent_highs)
        n_day_low = min(recent_lows)
        
        if self.current_regime == GoldRegime.BEAR:
            # Death cross — exit everything regardless
            if is_holding:
                self.pending_action = "GO_FLAT"
                self.pending_allocation = 0.0
                self.Log(f"[BREAKOUT] Death cross exit | GLD={gld_close:.2f}")
            else:
                self.pending_action = None
            return
        
        # We're in BULL regime (SMA_fast > SMA_slow)
        if not is_holding:
            # ENTRY: Buy on N-day high breakout (momentum confirmation)
            if gld_close >= n_day_high:
                self.pending_action = "BUY_GLD"
                self.pending_allocation = self.bull_allocation
                self.Log(f"[BREAKOUT] Entry: GLD={gld_close:.2f} >= {self.breakout_lookback}d high={n_day_high:.2f}")
            else:
                self.pending_action = None
        else:
            # HOLDING — check for exit on N-day low breakdown
            if gld_close <= n_day_low:
                self.pending_action = "GO_FLAT"
                self.pending_allocation = 0.0
                self.Log(f"[BREAKOUT] Exit: GLD={gld_close:.2f} <= {self.breakout_lookback}d low={n_day_low:.2f}")
            else:
                # Check rebalance
                current_pct = self._get_holding_pct()
                if abs(current_pct - self.bull_allocation) > self.rebalance_threshold:
                    self.pending_action = "REBALANCE"
                    self.pending_allocation = self.bull_allocation
                else:
                    self.pending_action = None
    
    def _get_holding_pct(self) -> float:
        """Get current GLD holding as % of portfolio equity."""
        equity = self.Portfolio.TotalPortfolioValue
        if equity <= 0:
            return 0.0
        holding_value = abs(self.Portfolio[self.gld].HoldingsValue)
        return holding_value / equity
    
    # =========================================================
    # INTRADAY — END-OF-DAY EXECUTION
    # =========================================================
    
    def OnData(self, data: Slice) -> None:
        """
        Process every minute bar.
        Execute trades only at 3:50 PM ET.
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
            self._close_position("regime_change_flat")
        
        elif action == "BUY_GLD":
            self._enter_position(self.pending_allocation)
        
        elif action == "REBALANCE":
            self._rebalance_position(self.pending_allocation)
    
    def _enter_position(self, allocation: float) -> None:
        """Enter a new GLD position at the target allocation."""
        equity = self.Portfolio.TotalPortfolioValue
        target_value = equity * allocation
        price = self.Securities[self.gld].Price
        
        if price <= 0:
            self.Log(f"[SKIP] GLD price is 0")
            return
        
        quantity = int(target_value / price)
        if quantity <= 0:
            self.Log(f"[SKIP] Computed quantity is 0 for GLD")
            return
        
        ticket = self.MarketOrder(self.gld, quantity)
        
        self.entry_price = price
        self.entry_time = self.Time
        self.entry_quantity = quantity
        
        regime_str = self.current_regime.value.upper()
        self.Log(f"[ENTER] {regime_str} → GLD x{quantity} @ ~${price:.2f} "
                 f"({allocation:.0%} of ${equity:,.0f})")
    
    def _close_position(self, reason: str) -> None:
        """Close GLD position and record trade."""
        qty = self.Portfolio[self.gld].Quantity
        if qty != 0:
            price = self.Securities[self.gld].Price
            
            # Record completed trade
            if self.entry_time:
                pnl = (price - self.entry_price) * qty
                pnl_pct = (price / self.entry_price - 1.0) if self.entry_price > 0 else 0.0
                hold_days = (self.Time - self.entry_time).days if self.entry_time else 0
                
                record = GLDTradeRecord(
                    symbol="GLD",
                    regime=self.current_regime.value,
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
                
                self.Log(f"[EXIT] GLD x{qty} @ ${price:.2f} | "
                         f"P&L: ${pnl:,.2f} ({pnl_pct:+.2%}) | "
                         f"Held: {hold_days}d | Reason: {reason}")
            
            self.Liquidate(self.gld)
            
            # SQL trade logging
            if self.db and self.entry_time:
                try:
                    self.db.log_trade(
                        symbol="GLD",
                        side="BUY",
                        quantity=abs(qty),
                        entry_price=self.entry_price,
                        exit_price=price,
                        entry_time=self.entry_time,
                        exit_time=self.Time,
                        entry_reason=f"regime_{self.current_regime.value}",
                        exit_reason=reason,
                    )
                except Exception as e:
                    self.Debug(f"[SQL] Trade log failed: {e}")
        
        self.entry_price = 0.0
        self.entry_time = None
        self.entry_quantity = 0
    
    def _rebalance_position(self, target_allocation: float) -> None:
        """Rebalance GLD position to target allocation."""
        equity = self.Portfolio.TotalPortfolioValue
        target_value = equity * target_allocation
        current_value = abs(self.Portfolio[self.gld].HoldingsValue)
        price = self.Securities[self.gld].Price
        
        if price <= 0:
            return
        
        delta_value = target_value - current_value
        delta_shares = int(delta_value / price)
        
        if abs(delta_shares) < 1:
            return
        
        self.MarketOrder(self.gld, delta_shares)
        
        self.Log(f"[REBALANCE] GLD: {delta_shares:+d} shares | "
                 f"Current: {current_value/equity:.1%} → Target: {target_allocation:.1%}")
    
    # =========================================================
    # END OF BACKTEST
    # =========================================================
    
    def OnEndOfAlgorithm(self) -> None:
        """Log final summary statistics."""
        # Close any remaining position
        self._close_position("end_of_backtest")
        
        # Summary
        total_pnl = sum(t.pnl for t in self.trade_history)
        winners = [t for t in self.trade_history if t.pnl > 0]
        losers = [t for t in self.trade_history if t.pnl <= 0]
        
        self.Log(f"\n{'='*60}")
        self.Log(f"GLD POSITION TREND FOLLOWING - FINAL SUMMARY")
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
                     f"(GLD=${rc.gld_price:.2f})")
        
        self.Log(f"{'='*60}")
        
        # Close SQL session
        if self.db:
            try:
                self.db.end_session()
            except Exception:
                pass
