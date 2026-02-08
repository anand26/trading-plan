# region imports
from AlgorithmImports import *  # type: ignore
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import deque
import statistics
import math

# SQL Persistence for Trade-Mind MCP integration
try:
    from sql_connector import TradingDBConnector, create_connector  # type: ignore
    HAS_SQL_CONNECTOR = True
except ImportError:
    HAS_SQL_CONNECTOR = False
# endregion

"""
TQQQ/SQQQ Turtle Trading Strategy
===================================
Strategy: Donchian channel breakout (trend-following) on TQQQ/SQQQ
Position: LONG-ONLY in either TQQQ or SQQQ
Concept:  TQQQ/SQQQ are 3x leveraged ETFs that amplify trends.
          Turtle Trading captures these trends with breakout entries,
          ATR-based position sizing, pyramiding, and trailing stops.

Key Design Decisions for 3x ETFs:
- Reduced risk per trade (0.5-1% vs classic 2%) due to 3x volatility
- SQQQ used as "short" proxy instead of shorting TQQQ
- ATR multiplied by 3x factor for stop distance (3x leverage)
- No overnight holds initially (configurable)
- Pyramiding capped at 3 units (vs classic 4) due to leverage

Entry Rules:
- Buy TQQQ when price breaks ABOVE the N-day high (bull breakout)
- Buy SQQQ when price breaks BELOW the N-day low (bear breakout)
- Uses daily bars consolidated from minute data

Exit Rules:
- Exit TQQQ when price breaks below M-day low (M < N)
- Exit SQQQ when price breaks above M-day high (M < N)
- Hard stop at entry - 2*ATR per unit
- Trailing Donchian exit

Position Sizing (ATR-based):
- Dollar volatility = ATR_20 * 3 (for 3x ETF)
- Unit size = (Account * risk_pct) / dollar_volatility
- Pyramid: add 1 unit every 0.5*ATR move in favor, up to max_units

Author: Trading Plan Implementation
Version: 1.0.0 (Turtle Trading for 3x ETFs)
"""


class TurtlePositionState(Enum):
    """Current position state"""
    FLAT = "flat"
    LONG_TQQQ = "long_tqqq"    # Bull trend - long TQQQ
    LONG_SQQQ = "long_sqqq"    # Bear trend - long SQQQ


@dataclass
class TurtleUnit:
    """Track a single pyramid unit"""
    entry_price: float
    quantity: int
    entry_time: datetime
    stop_price: float      # Per-unit stop


@dataclass
class TurtleTradeRecord:
    """Record of a completed trade"""
    symbol: str
    direction: str           # "BULL" or "BEAR"
    entry_time: datetime
    exit_time: datetime
    avg_entry_price: float
    exit_price: float
    total_quantity: int
    num_units: int
    pnl: float
    pnl_pct: float
    hold_duration_days: int
    exit_reason: str


class TQQQTurtleAlgorithm(QCAlgorithm):
    """
    Turtle Trading on TQQQ/SQQQ with daily Donchian breakouts.
    
    Uses minute data consolidated to daily bars.
    ATR-based position sizing adapted for 3x leveraged ETFs.
    Pyramiding with trailing stops per unit.
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
        
        self.SetBrokerageModel(BrokerageName.Alpaca, AccountType.Margin)
        
        # =====================================================
        # TURTLE TRADING PARAMETERS
        # =====================================================
        
        # Donchian Channel periods
        self.entry_period = int(float(self.GetParameter("entry-period") or 20))
        self.exit_period = int(float(self.GetParameter("exit-period") or 10))
        
        # ATR period for sizing and stops
        self.atr_period = int(float(self.GetParameter("atr-period") or 20))
        
        # Risk management
        self.risk_per_trade = float(self.GetParameter("risk-per-trade") or 0.005)    # 0.5% account risk per unit
        self.atr_stop_multiple = float(self.GetParameter("atr-stop-multiple") or 2.0)  # 2x ATR stop per unit
        self.leverage_factor = float(self.GetParameter("leverage-factor") or 3.0)      # 3x ETF multiplier
        
        # Pyramiding
        self.max_units = int(float(self.GetParameter("max-units") or 3))                # Max pyramid units
        self.pyramid_atr_step = float(self.GetParameter("pyramid-atr-step") or 0.5)    # Add unit every 0.5 ATR move
        
        # Position size cap (max % of portfolio in one direction)
        self.max_position_pct = float(self.GetParameter("max-position-pct") or 0.80)   # 80% max exposure
        
        # Hold time limits
        self.max_hold_days = int(float(self.GetParameter("max-hold-days") or 0))        # 0 = no limit
        
        # Trend filter: use QQQ as sanity check (optional)
        self.use_qqq_filter = str(self.GetParameter("use-qqq-filter") or "false").lower() == "true"
        
        # Log parameters
        self.Log(f"[PARAMS] Entry Period: {self.entry_period}, Exit Period: {self.exit_period}")
        self.Log(f"[PARAMS] ATR Period: {self.atr_period}, Stop Multiple: {self.atr_stop_multiple}x")
        self.Log(f"[PARAMS] Risk/Trade: {self.risk_per_trade:.1%}, Max Units: {self.max_units}")
        self.Log(f"[PARAMS] Pyramid Step: {self.pyramid_atr_step}x ATR, Max Position: {self.max_position_pct:.0%}")
        self.Log(f"[PARAMS] Max Hold Days: {self.max_hold_days}, QQQ Filter: {self.use_qqq_filter}")
        
        # =====================================================
        # ADD SECURITIES
        # =====================================================
        self.tqqq = self.AddEquity("TQQQ", Resolution.Minute).Symbol
        self.sqqq = self.AddEquity("SQQQ", Resolution.Minute).Symbol
        
        if self.use_qqq_filter:
            self.qqq = self.AddEquity("QQQ", Resolution.Minute).Symbol
        
        # =====================================================
        # DAILY BAR CONSOLIDATORS (from minute data)
        # =====================================================
        self.tqqq_daily_consolidator = TradeBarConsolidator(timedelta(days=1))
        self.tqqq_daily_consolidator.DataConsolidated += self.OnTQQQDailyBar
        self.SubscriptionManager.AddConsolidator(self.tqqq, self.tqqq_daily_consolidator)
        
        self.sqqq_daily_consolidator = TradeBarConsolidator(timedelta(days=1))
        self.sqqq_daily_consolidator.DataConsolidated += self.OnSQQQDailyBar
        self.SubscriptionManager.AddConsolidator(self.sqqq, self.sqqq_daily_consolidator)
        
        if self.use_qqq_filter:
            self.qqq_daily_consolidator = TradeBarConsolidator(timedelta(days=1))
            self.qqq_daily_consolidator.DataConsolidated += self.OnQQQDailyBar
            self.SubscriptionManager.AddConsolidator(self.qqq, self.qqq_daily_consolidator)
        
        # =====================================================
        # PRICE HISTORY FOR DONCHIAN CHANNELS
        # =====================================================
        # Need max(entry_period, exit_period) + buffer days of history
        max_lookback = max(self.entry_period, self.exit_period) + 5
        
        self.tqqq_highs: deque = deque(maxlen=max_lookback)
        self.tqqq_lows: deque = deque(maxlen=max_lookback)
        self.tqqq_closes: deque = deque(maxlen=max_lookback)
        
        self.sqqq_highs: deque = deque(maxlen=max_lookback)
        self.sqqq_lows: deque = deque(maxlen=max_lookback)
        self.sqqq_closes: deque = deque(maxlen=max_lookback)
        
        if self.use_qqq_filter:
            self.qqq_closes: deque = deque(maxlen=max_lookback)
        
        # =====================================================
        # ATR TRACKING (True Range history for manual ATR)
        # =====================================================
        self.tqqq_tr_history: deque = deque(maxlen=self.atr_period + 5)
        self.sqqq_tr_history: deque = deque(maxlen=self.atr_period + 5)
        self.tqqq_prev_close: Optional[float] = None
        self.sqqq_prev_close: Optional[float] = None
        
        # Current ATR values
        self.tqqq_atr: float = 0.0
        self.sqqq_atr: float = 0.0
        
        # =====================================================
        # POSITION TRACKING
        # =====================================================
        self.position_state = TurtlePositionState.FLAT
        self.units: List[TurtleUnit] = []       # Active pyramid units
        self.last_add_price: float = 0.0        # Price of last pyramid add
        self.position_entry_time: Optional[datetime] = None
        
        # Track if we've had a losing trade on current breakout direction
        # Classic Turtle: skip S1 breakout if previous S1 was a winner
        # We'll skip this filter initially for simplicity
        
        # =====================================================
        # TRADE HISTORY
        # =====================================================
        self.trade_history: List[TurtleTradeRecord] = []
        
        # =====================================================
        # DAILY BAR FLAGS (ensure we process after both bars arrive)
        # =====================================================
        self.tqqq_bar_ready = False
        self.sqqq_bar_ready = False
        self.pending_tqqq_bar: Optional[TradeBar] = None
        self.pending_sqqq_bar: Optional[TradeBar] = None
        
        # =====================================================
        # WARMUP - need enough days to fill Donchian channels
        # =====================================================
        warmup_days = max(self.entry_period, self.atr_period) + 10
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
                    "strategy": "TURTLE_TQQQ",
                    "entry_period": self.entry_period,
                    "exit_period": self.exit_period,
                    "atr_period": self.atr_period,
                    "risk_per_trade": self.risk_per_trade,
                    "atr_stop_multiple": self.atr_stop_multiple,
                    "max_units": self.max_units,
                    "pyramid_atr_step": self.pyramid_atr_step,
                }
                
                session_id = str(self.GetParameter("session-id") or "")
                if not session_id or session_id == "default":
                    session_id = None
                
                self.db.start_session(session_type, params_snapshot, session_id)
                self.Debug(f"[SQL] Session started: {self.db.session_id}")
                
            except Exception as e:
                self.Debug(f"[SQL] Failed to initialize: {e}")
                self.db = None
        
        self.Debug("TQQQTurtleAlgorithm v1.0 Initialized")
    
    # =========================================================
    # DAILY BAR HANDLERS
    # =========================================================
    
    def OnTQQQDailyBar(self, sender, bar: TradeBar) -> None:
        """Handle completed TQQQ daily bar"""
        self.pending_tqqq_bar = bar
        self.tqqq_bar_ready = True
        self._try_process_daily()
    
    def OnSQQQDailyBar(self, sender, bar: TradeBar) -> None:
        """Handle completed SQQQ daily bar"""
        self.pending_sqqq_bar = bar
        self.sqqq_bar_ready = True
        self._try_process_daily()
    
    def OnQQQDailyBar(self, sender, bar: TradeBar) -> None:
        """Handle completed QQQ daily bar (trend filter)"""
        if self.use_qqq_filter:
            self.qqq_closes.append(bar.Close)
    
    def _try_process_daily(self) -> None:
        """Process once both daily bars are ready"""
        if not (self.tqqq_bar_ready and self.sqqq_bar_ready):
            return
        
        if self.IsWarmingUp:
            # Still accumulate history during warmup
            self._update_price_history(self.pending_tqqq_bar, self.pending_sqqq_bar)
            self.tqqq_bar_ready = False
            self.sqqq_bar_ready = False
            return
        
        tqqq_bar = self.pending_tqqq_bar
        sqqq_bar = self.pending_sqqq_bar
        
        # Reset flags
        self.tqqq_bar_ready = False
        self.sqqq_bar_ready = False
        
        # Update price history and ATR
        self._update_price_history(tqqq_bar, sqqq_bar)
        
        # Need enough history
        if len(self.tqqq_highs) < self.entry_period:
            self.Debug(f"{self.Time} Building history: {len(self.tqqq_highs)}/{self.entry_period}")
            return
        
        if self.tqqq_atr <= 0 or self.sqqq_atr <= 0:
            return
        
        # Process trading signals
        self._process_signals(tqqq_bar, sqqq_bar)
    
    def _update_price_history(self, tqqq_bar: TradeBar, sqqq_bar: TradeBar) -> None:
        """Update price history and ATR calculations"""
        # TQQQ
        self.tqqq_highs.append(tqqq_bar.High)
        self.tqqq_lows.append(tqqq_bar.Low)
        self.tqqq_closes.append(tqqq_bar.Close)
        
        # Calculate True Range for TQQQ
        if self.tqqq_prev_close is not None:
            tr = max(
                tqqq_bar.High - tqqq_bar.Low,
                abs(tqqq_bar.High - self.tqqq_prev_close),
                abs(tqqq_bar.Low - self.tqqq_prev_close)
            )
            self.tqqq_tr_history.append(tr)
        self.tqqq_prev_close = tqqq_bar.Close
        
        # Calculate TQQQ ATR
        if len(self.tqqq_tr_history) >= self.atr_period:
            self.tqqq_atr = statistics.mean(list(self.tqqq_tr_history)[-self.atr_period:])
        
        # SQQQ
        self.sqqq_highs.append(sqqq_bar.High)
        self.sqqq_lows.append(sqqq_bar.Low)
        self.sqqq_closes.append(sqqq_bar.Close)
        
        # Calculate True Range for SQQQ
        if self.sqqq_prev_close is not None:
            tr = max(
                sqqq_bar.High - sqqq_bar.Low,
                abs(sqqq_bar.High - self.sqqq_prev_close),
                abs(sqqq_bar.Low - self.sqqq_prev_close)
            )
            self.sqqq_tr_history.append(tr)
        self.sqqq_prev_close = sqqq_bar.Close
        
        # Calculate SQQQ ATR
        if len(self.sqqq_tr_history) >= self.atr_period:
            self.sqqq_atr = statistics.mean(list(self.sqqq_tr_history)[-self.atr_period:])
    
    # =========================================================
    # DONCHIAN CHANNEL CALCULATIONS
    # =========================================================
    
    def _get_donchian_high(self, highs: deque, period: int) -> float:
        """Get N-period high (exclude current bar)"""
        if len(highs) < period + 1:
            return float('inf')
        # Use the previous N bars (not including today)
        return max(list(highs)[-(period + 1):-1])
    
    def _get_donchian_low(self, lows: deque, period: int) -> float:
        """Get N-period low (exclude current bar)"""
        if len(lows) < period + 1:
            return 0.0
        # Use the previous N bars (not including today)
        return min(list(lows)[-(period + 1):-1])
    
    # =========================================================
    # SIGNAL PROCESSING
    # =========================================================
    
    def _process_signals(self, tqqq_bar: TradeBar, sqqq_bar: TradeBar) -> None:
        """Main daily signal processing"""
        
        tqqq_price = tqqq_bar.Close
        sqqq_price = sqqq_bar.Close
        
        # Calculate Donchian channels for TQQQ
        tqqq_entry_high = self._get_donchian_high(self.tqqq_highs, self.entry_period)
        tqqq_exit_low = self._get_donchian_low(self.tqqq_lows, self.exit_period)
        tqqq_entry_low = self._get_donchian_low(self.tqqq_lows, self.entry_period)
        tqqq_exit_high = self._get_donchian_high(self.tqqq_highs, self.exit_period)
        
        # Log channels weekly
        if self.Time.weekday() == 0:
            self.Debug(
                f"{self.Time.date()} TQQQ: {tqqq_price:.2f} | "
                f"Entry High: {tqqq_entry_high:.2f}, Entry Low: {tqqq_entry_low:.2f} | "
                f"ATR: {self.tqqq_atr:.2f} | State: {self.position_state.value} | "
                f"Units: {len(self.units)}"
            )
        
        # =====================================================
        # EXIT LOGIC (check first)
        # =====================================================
        if self.position_state != TurtlePositionState.FLAT:
            self._check_exits(tqqq_bar, sqqq_bar, tqqq_exit_low, tqqq_exit_high)
        
        # =====================================================
        # ENTRY / PYRAMID LOGIC
        # =====================================================
        if self.position_state == TurtlePositionState.FLAT:
            # Check for new breakout entries
            self._check_entries(
                tqqq_price, sqqq_price,
                tqqq_entry_high, tqqq_entry_low,
                tqqq_bar, sqqq_bar
            )
        else:
            # Check for pyramid adds
            self._check_pyramid(tqqq_price, sqqq_price)
    
    # =========================================================
    # ENTRY LOGIC
    # =========================================================
    
    def _check_entries(
        self,
        tqqq_price: float, sqqq_price: float,
        tqqq_entry_high: float, tqqq_entry_low: float,
        tqqq_bar: TradeBar, sqqq_bar: TradeBar
    ) -> None:
        """Check for Donchian breakout entries"""
        
        # Optional QQQ trend filter
        if self.use_qqq_filter and len(getattr(self, 'qqq_closes', [])) >= 50:
            qqq_list = list(self.qqq_closes)
            qqq_sma50 = statistics.mean(qqq_list[-50:])
            qqq_current = qqq_list[-1]
            # Only allow bull entries above SMA50, bear entries below
            qqq_bullish = qqq_current > qqq_sma50
        else:
            qqq_bullish = None  # No filter
        
        # BULL BREAKOUT: TQQQ price breaks above N-day high → buy TQQQ
        if tqqq_price > tqqq_entry_high:
            if qqq_bullish is None or qqq_bullish:
                self._enter_position("TQQQ", self.tqqq, tqqq_price, self.tqqq_atr, "BULL")
                return
        
        # BEAR BREAKOUT: TQQQ price breaks below N-day low → buy SQQQ
        if tqqq_price < tqqq_entry_low:
            if qqq_bullish is None or not qqq_bullish:
                self._enter_position("SQQQ", self.sqqq, sqqq_price, self.sqqq_atr, "BEAR")
                return
    
    def _enter_position(
        self, symbol_name: str, symbol, price: float, atr: float, direction: str
    ) -> None:
        """Enter first unit of a new position"""
        
        # Calculate unit size: risk_per_trade * account / (ATR * leverage_factor)
        account_value = self.Portfolio.TotalPortfolioValue
        dollar_risk = account_value * self.risk_per_trade
        dollar_volatility = atr * self.leverage_factor
        
        if dollar_volatility <= 0:
            return
        
        unit_dollars = dollar_risk / dollar_volatility * price
        
        # Cap at max_position_pct of account per unit
        max_unit_dollars = account_value * self.max_position_pct / self.max_units
        unit_dollars = min(unit_dollars, max_unit_dollars)
        
        quantity = int(unit_dollars / price) if price > 0 else 0
        if quantity <= 0:
            return
        
        # Calculate stop price
        stop_price = price - (atr * self.atr_stop_multiple) if direction == "BULL" else price + (atr * self.atr_stop_multiple)
        
        # Place order
        self.MarketOrder(symbol, quantity, tag=f"Turtle {direction} Entry U1 @ {price:.2f}")
        
        # Track unit
        unit = TurtleUnit(
            entry_price=price,
            quantity=quantity,
            entry_time=self.Time,
            stop_price=stop_price
        )
        self.units = [unit]
        self.last_add_price = price
        self.position_entry_time = self.Time
        
        if direction == "BULL":
            self.position_state = TurtlePositionState.LONG_TQQQ
        else:
            self.position_state = TurtlePositionState.LONG_SQQQ
        
        self.Log(
            f"[ENTRY] {direction} {symbol_name} Unit 1: {quantity} shares @ {price:.2f} | "
            f"ATR: {atr:.2f} | Stop: {stop_price:.2f} | "
            f"Risk: ${dollar_risk:.0f}"
        )
    
    # =========================================================
    # PYRAMIDING LOGIC
    # =========================================================
    
    def _check_pyramid(self, tqqq_price: float, sqqq_price: float) -> None:
        """Check if we should add a pyramid unit"""
        
        if len(self.units) >= self.max_units:
            return
        
        if self.position_state == TurtlePositionState.LONG_TQQQ:
            symbol = self.tqqq
            symbol_name = "TQQQ"
            price = tqqq_price
            atr = self.tqqq_atr
            direction = "BULL"
            # Add when price moved up by pyramid_atr_step * ATR
            threshold = self.last_add_price + (self.pyramid_atr_step * atr)
            if price < threshold:
                return
        elif self.position_state == TurtlePositionState.LONG_SQQQ:
            symbol = self.sqqq
            symbol_name = "SQQQ"
            price = sqqq_price
            atr = self.sqqq_atr
            direction = "BEAR"
            # Add when SQQQ price moved up (meaning market moved down)
            threshold = self.last_add_price + (self.pyramid_atr_step * atr)
            if price < threshold:
                return
        else:
            return
        
        # Check total position size doesn't exceed max
        current_value = sum(u.quantity * price for u in self.units)
        account_value = self.Portfolio.TotalPortfolioValue
        if current_value / account_value > self.max_position_pct * 0.9:
            return
        
        # Calculate new unit size
        dollar_risk = account_value * self.risk_per_trade
        dollar_volatility = atr * self.leverage_factor
        if dollar_volatility <= 0:
            return
        
        unit_dollars = dollar_risk / dollar_volatility * price
        max_unit_dollars = account_value * self.max_position_pct / self.max_units
        unit_dollars = min(unit_dollars, max_unit_dollars)
        
        quantity = int(unit_dollars / price) if price > 0 else 0
        if quantity <= 0:
            return
        
        # Stop for this unit
        stop_price = price - (atr * self.atr_stop_multiple) if direction == "BULL" else price + (atr * self.atr_stop_multiple)
        
        # Place order
        unit_num = len(self.units) + 1
        self.MarketOrder(symbol, quantity, tag=f"Turtle {direction} Pyramid U{unit_num} @ {price:.2f}")
        
        # Track unit
        unit = TurtleUnit(
            entry_price=price,
            quantity=quantity,
            entry_time=self.Time,
            stop_price=stop_price
        )
        self.units.append(unit)
        self.last_add_price = price
        
        # Move ALL stops up to newest unit's stop (Turtle rule: tighten stops on pyramid)
        for u in self.units:
            if direction == "BULL":
                u.stop_price = max(u.stop_price, stop_price)
            else:
                u.stop_price = min(u.stop_price, stop_price)
        
        self.Log(
            f"[PYRAMID] {direction} {symbol_name} Unit {unit_num}: {quantity} shares @ {price:.2f} | "
            f"New Stop: {stop_price:.2f} | Total Units: {len(self.units)}"
        )
    
    # =========================================================
    # EXIT LOGIC
    # =========================================================
    
    def _check_exits(
        self,
        tqqq_bar: TradeBar, sqqq_bar: TradeBar,
        tqqq_exit_low: float, tqqq_exit_high: float
    ) -> None:
        """Check all exit conditions"""
        
        if self.position_state == TurtlePositionState.LONG_TQQQ:
            symbol = self.tqqq
            symbol_name = "TQQQ"
            price = tqqq_bar.Close
            direction = "BULL"
        elif self.position_state == TurtlePositionState.LONG_SQQQ:
            symbol = self.sqqq
            symbol_name = "SQQQ"
            price = sqqq_bar.Close
            direction = "BEAR"
        else:
            return
        
        exit_reason = None
        
        # =====================================================
        # EXIT 1: Per-unit stop loss (highest priority)
        # =====================================================
        if direction == "BULL":
            # Check if any unit's stop was hit (use tightest stop = newest)
            worst_stop = max(u.stop_price for u in self.units)
            if price <= worst_stop:
                exit_reason = f"ATR stop hit: price {price:.2f} <= stop {worst_stop:.2f}"
        else:
            # SQQQ: stop is above price
            worst_stop = min(u.stop_price for u in self.units)
            if price >= worst_stop:
                exit_reason = f"ATR stop hit: price {price:.2f} >= stop {worst_stop:.2f}"
        
        # =====================================================
        # EXIT 2: Donchian exit (trend reversal)
        # =====================================================
        if exit_reason is None:
            if direction == "BULL" and tqqq_bar.Close < tqqq_exit_low:
                exit_reason = f"Donchian exit: TQQQ {tqqq_bar.Close:.2f} < {self.exit_period}-day low {tqqq_exit_low:.2f}"
            elif direction == "BEAR" and tqqq_bar.Close > tqqq_exit_high:
                exit_reason = f"Donchian exit: TQQQ {tqqq_bar.Close:.2f} > {self.exit_period}-day high {tqqq_exit_high:.2f}"
        
        # =====================================================
        # EXIT 3: Max hold time
        # =====================================================
        if exit_reason is None and self.max_hold_days > 0 and self.position_entry_time:
            hold_days = (self.Time - self.position_entry_time).days
            if hold_days >= self.max_hold_days:
                exit_reason = f"Max hold: {hold_days} days"
        
        # Execute exit
        if exit_reason:
            self._exit_position(symbol, symbol_name, price, direction, exit_reason)
    
    def _exit_position(
        self, symbol, symbol_name: str, exit_price: float,
        direction: str, reason: str
    ) -> None:
        """Exit all units of current position"""
        
        total_quantity = sum(u.quantity for u in self.units)
        total_cost = sum(u.entry_price * u.quantity for u in self.units)
        avg_entry = total_cost / total_quantity if total_quantity > 0 else 0
        
        pnl = (exit_price - avg_entry) * total_quantity
        pnl_pct = (exit_price - avg_entry) / avg_entry if avg_entry > 0 else 0
        
        hold_days = (self.Time - self.position_entry_time).days if self.position_entry_time else 0
        
        # Liquidate entire position
        self.Liquidate(symbol, tag=f"Turtle Exit: {reason}")
        
        # Record trade
        trade_record = TurtleTradeRecord(
            symbol=symbol_name,
            direction=direction,
            entry_time=self.position_entry_time or self.Time,
            exit_time=self.Time,
            avg_entry_price=avg_entry,
            exit_price=exit_price,
            total_quantity=total_quantity,
            num_units=len(self.units),
            pnl=pnl,
            pnl_pct=pnl_pct,
            hold_duration_days=hold_days,
            exit_reason=reason
        )
        self.trade_history.append(trade_record)
        
        self.Log(
            f"[EXIT] {direction} {symbol_name}: {total_quantity} shares @ {exit_price:.2f} | "
            f"Avg Entry: {avg_entry:.2f} | P&L: ${pnl:.2f} ({pnl_pct:.2%}) | "
            f"Units: {len(self.units)} | Hold: {hold_days}d | Reason: {reason}"
        )
        
        # SQL logging
        if self.db and self.position_entry_time:
            self.db.log_trade(
                symbol=symbol_name,
                side="BUY",
                quantity=total_quantity,
                entry_price=avg_entry,
                exit_price=exit_price,
                entry_time=self.position_entry_time,
                exit_time=self.Time,
                entry_reason=f"Turtle {direction} breakout ({len(self.units)} units)",
                exit_reason=reason
            )
        
        # Reset state
        self.position_state = TurtlePositionState.FLAT
        self.units = []
        self.last_add_price = 0.0
        self.position_entry_time = None
    
    # =========================================================
    # INTRADAY STOP MONITORING
    # =========================================================
    
    def OnData(self, data: Slice) -> None:
        """Monitor intraday prices for stop loss hits (between daily bars)"""
        if self.IsWarmingUp:
            return
        
        if self.position_state == TurtlePositionState.FLAT:
            return
        
        # Only check stops intraday, not full signal logic
        if self.position_state == TurtlePositionState.LONG_TQQQ:
            if data.ContainsKey(self.tqqq) and data[self.tqqq] is not None:
                price = data[self.tqqq].Price
                if self.units:
                    worst_stop = max(u.stop_price for u in self.units)
                    if price <= worst_stop:
                        self._exit_position(
                            self.tqqq, "TQQQ", price, "BULL",
                            f"Intraday ATR stop: {price:.2f} <= {worst_stop:.2f}"
                        )
        
        elif self.position_state == TurtlePositionState.LONG_SQQQ:
            if data.ContainsKey(self.sqqq) and data[self.sqqq] is not None:
                price = data[self.sqqq].Price
                if self.units:
                    worst_stop = min(u.stop_price for u in self.units)
                    if price >= worst_stop:
                        self._exit_position(
                            self.sqqq, "SQQQ", price, "BEAR",
                            f"Intraday ATR stop: {price:.2f} >= {worst_stop:.2f}"
                        )
    
    # =========================================================
    # END OF ALGORITHM
    # =========================================================
    
    def OnEndOfAlgorithm(self) -> None:
        """Log summary at end of backtest"""
        # Close any open position
        if self.position_state != TurtlePositionState.FLAT:
            if self.position_state == TurtlePositionState.LONG_TQQQ:
                price = self.Securities[self.tqqq].Price
                self._exit_position(self.tqqq, "TQQQ", price, "BULL", "End of Backtest")
            else:
                price = self.Securities[self.sqqq].Price
                self._exit_position(self.sqqq, "SQQQ", price, "BEAR", "End of Backtest")
        
        if not self.trade_history:
            self.Log("[SUMMARY] No trades executed")
            return
        
        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t.pnl > 0)
        total_pnl = sum(t.pnl for t in self.trade_history)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        total_return = (self.Portfolio.TotalPortfolioValue - self.initial_cash) / self.initial_cash
        
        # Average hold time
        avg_hold = statistics.mean([t.hold_duration_days for t in self.trade_history])
        
        # R ratio
        wins = [t.pnl for t in self.trade_history if t.pnl > 0]
        losses = [t.pnl for t in self.trade_history if t.pnl < 0]
        avg_win = statistics.mean(wins) if wins else 0
        avg_loss = abs(statistics.mean(losses)) if losses else 1
        r_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        # Bull vs Bear breakdown
        bull_trades = [t for t in self.trade_history if t.direction == "BULL"]
        bear_trades = [t for t in self.trade_history if t.direction == "BEAR"]
        bull_pnl = sum(t.pnl for t in bull_trades)
        bear_pnl = sum(t.pnl for t in bear_trades)
        
        self.Log(f"[SUMMARY] === TURTLE TRADING RESULTS ===")
        self.Log(f"[SUMMARY] Total Trades: {total_trades}")
        self.Log(f"[SUMMARY] Win Rate: {win_rate:.1%} ({winning_trades}W / {total_trades - winning_trades}L)")
        self.Log(f"[SUMMARY] Total P&L: ${total_pnl:,.2f}")
        self.Log(f"[SUMMARY] Total Return: {total_return:.2%}")
        self.Log(f"[SUMMARY] Avg Win: ${avg_win:,.2f}, Avg Loss: ${avg_loss:,.2f}, R Ratio: {r_ratio:.2f}")
        self.Log(f"[SUMMARY] Avg Hold: {avg_hold:.1f} days")
        self.Log(f"[SUMMARY] Bull Trades: {len(bull_trades)}, P&L: ${bull_pnl:,.2f}")
        self.Log(f"[SUMMARY] Bear Trades: {len(bear_trades)}, P&L: ${bear_pnl:,.2f}")
        
        # SQL session end
        if self.db:
            self.db.end_session(
                total_return=total_return,
                total_trades=total_trades,
                win_rate=win_rate
            )
