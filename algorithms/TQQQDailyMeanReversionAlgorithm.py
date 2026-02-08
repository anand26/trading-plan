# region imports
from AlgorithmImports import *  # type: ignore
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional
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
TQQQ/SQQQ Daily Mean Reversion Strategy
=========================================
Strategy: Z-score mean reversion on the TQQQ/SQQQ daily price ratio
Position: LONG-ONLY in either TQQQ or SQQQ
Concept:  Use DAILY bars (not 5-min) for a multi-day holding strategy.
          Captures larger mean-reversion moves with fewer trades,
          lower transaction costs, and overnight holding.

Key Differences from Intraday Pairs Strategy:
- Daily bars instead of 5-minute bars
- Multi-day holds (overnight, 2-10+ days)
- No forced EOD close
- Larger Z-score thresholds (daily moves are smaller vs lookback)
- Bollinger Band-style confirmation on the ratio
- RSI filter on ratio for oversold/overbought confirmation

Entry Rules:
- Calculate TQQQ/SQQQ price ratio on daily bars
- Compute rolling Z-score with configurable lookback (20-60 days)
- Z-score < -entry_threshold → Buy TQQQ (ratio compressed, TQQQ cheap)
- Z-score > +entry_threshold → Buy SQQQ (ratio extended, SQQQ cheap)
- Optional: require RSI of ratio to confirm (RSI < 30 for TQQQ, RSI > 70 for SQQQ)

Exit Rules:
- Z-score crosses back to exit_target (default 0.0 = full mean reversion)
- Hard stop loss (percentage-based)
- Max hold days
- Trailing stop (optional, in ATR units)

Position Sizing:
- Fixed percentage of portfolio (configurable)
- Optional vol-scaling: reduce size when ATR is elevated

Author: Trading Plan Implementation
Version: 1.0.0 (Daily Mean Reversion for 3x ETFs)
"""


class DailyMRPositionState(Enum):
    """Current position state"""
    FLAT = "flat"
    LONG_TQQQ = "long_tqqq"
    LONG_SQQQ = "long_sqqq"


@dataclass
class DailyMRTradeRecord:
    """Record of a completed trade"""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    entry_zscore: float
    exit_zscore: float
    hold_duration_days: int
    exit_reason: str


class TQQQDailyMeanReversionAlgorithm(QCAlgorithm):
    """
    Daily Mean Reversion on TQQQ/SQQQ ratio.
    
    Uses minute data consolidated to daily bars.
    Multi-day holds with Z-score-based entry/exit.
    Optional RSI confirmation and trailing stops.
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
        # DAILY MEAN REVERSION PARAMETERS
        # =====================================================
        
        # Z-score lookback (number of DAILY bars)
        self.zscore_lookback = int(float(self.GetParameter("zscore-lookback") or 30))
        
        # Entry threshold
        self.entry_zscore = float(self.GetParameter("entry-zscore") or 2.0)
        
        # Exit target Z-score (0.0 = full reversion to mean)
        self.exit_target_zscore = float(self.GetParameter("exit-target-zscore") or 0.0)
        
        # Stop loss
        self.stop_loss_pct = float(self.GetParameter("stop-loss-pct") or 0.05)  # 5% for multi-day
        
        # Position sizing
        self.position_size = float(self.GetParameter("position-size") or 0.50)  # 50% of portfolio
        
        # Max hold days (0 = no limit)
        self.max_hold_days = int(float(self.GetParameter("max-hold-days") or 20))
        
        # Trailing stop (in ATR units, 0 = disabled)
        self.trailing_stop_atr = float(self.GetParameter("trailing-stop-atr") or 0.0)
        
        # ATR period for trailing stop and vol scaling
        self.atr_period = int(float(self.GetParameter("atr-period") or 14))
        
        # RSI confirmation filter
        self.use_rsi_filter = str(self.GetParameter("use-rsi-filter") or "false").lower() == "true"
        self.rsi_period = int(float(self.GetParameter("rsi-period") or 14))
        self.rsi_oversold = float(self.GetParameter("rsi-oversold") or 30.0)
        self.rsi_overbought = float(self.GetParameter("rsi-overbought") or 70.0)
        
        # Vol scaling: reduce position when volatility is elevated
        self.use_vol_scaling = str(self.GetParameter("use-vol-scaling") or "false").lower() == "true"
        self.vol_scale_threshold = float(self.GetParameter("vol-scale-threshold") or 1.5)  # Reduce when ATR > 1.5x median
        self.vol_scale_factor = float(self.GetParameter("vol-scale-factor") or 0.5)        # Scale to 50% of normal size
        
        # Minimum days between trades
        self.min_days_between = int(float(self.GetParameter("min-days-between") or 1))
        
        # Log parameters
        self.Log(f"[PARAMS] Z-score Lookback: {self.zscore_lookback} days")
        self.Log(f"[PARAMS] Entry Z-score: ±{self.entry_zscore}, Exit Target: ±{self.exit_target_zscore}")
        self.Log(f"[PARAMS] Stop Loss: {self.stop_loss_pct:.1%}, Max Hold: {self.max_hold_days} days")
        self.Log(f"[PARAMS] Position Size: {self.position_size:.0%}")
        self.Log(f"[PARAMS] Trailing Stop ATR: {self.trailing_stop_atr}, RSI Filter: {self.use_rsi_filter}")
        self.Log(f"[PARAMS] Vol Scaling: {self.use_vol_scaling}")
        
        # =====================================================
        # ADD SECURITIES
        # =====================================================
        self.tqqq = self.AddEquity("TQQQ", Resolution.Minute).Symbol
        self.sqqq = self.AddEquity("SQQQ", Resolution.Minute).Symbol
        
        # =====================================================
        # DAILY BAR CONSOLIDATORS (from minute data)
        # =====================================================
        self.tqqq_daily_consolidator = TradeBarConsolidator(timedelta(days=1))
        self.tqqq_daily_consolidator.DataConsolidated += self.OnTQQQDailyBar
        self.SubscriptionManager.AddConsolidator(self.tqqq, self.tqqq_daily_consolidator)
        
        self.sqqq_daily_consolidator = TradeBarConsolidator(timedelta(days=1))
        self.sqqq_daily_consolidator.DataConsolidated += self.OnSQQQDailyBar
        self.SubscriptionManager.AddConsolidator(self.sqqq, self.sqqq_daily_consolidator)
        
        # =====================================================
        # PRICE HISTORY
        # =====================================================
        max_lookback = max(self.zscore_lookback, self.atr_period, self.rsi_period) + 10
        
        self.ratio_history: deque = deque(maxlen=max_lookback)
        self.tqqq_closes: deque = deque(maxlen=max_lookback)
        self.sqqq_closes: deque = deque(maxlen=max_lookback)
        
        # ATR tracking
        self.ratio_tr_history: deque = deque(maxlen=max_lookback)
        self.tqqq_prev_close: Optional[float] = None
        self.tqqq_atr: float = 0.0
        
        # For ATR on the ratio (used for trailing stop)
        self.ratio_prev: Optional[float] = None
        self.ratio_atr: float = 0.0
        self.ratio_atr_history: deque = deque(maxlen=max_lookback)
        
        # ATR history for vol scaling
        self.atr_median_history: deque = deque(maxlen=252)  # 1 year of daily ATR
        
        # =====================================================
        # POSITION TRACKING
        # =====================================================
        self.position_state = DailyMRPositionState.FLAT
        self.entry_price: float = 0.0
        self.entry_time: Optional[datetime] = None
        self.trade_entry_zscore: float = 0.0
        self.days_since_trade: int = 0
        self.trailing_stop_price: Optional[float] = None
        self.best_price_since_entry: float = 0.0
        
        # Trade history
        self.trade_history: List[DailyMRTradeRecord] = []
        
        # =====================================================
        # DAILY BAR FLAGS
        # =====================================================
        self.tqqq_bar_ready = False
        self.sqqq_bar_ready = False
        self.pending_tqqq_bar: Optional[TradeBar] = None
        self.pending_sqqq_bar: Optional[TradeBar] = None
        
        # =====================================================
        # WARMUP
        # =====================================================
        warmup_days = max_lookback + 10
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
                    "strategy": "DAILY_MEAN_REVERSION",
                    "zscore_lookback": self.zscore_lookback,
                    "entry_zscore": self.entry_zscore,
                    "exit_target_zscore": self.exit_target_zscore,
                    "stop_loss_pct": self.stop_loss_pct,
                    "position_size": self.position_size,
                    "max_hold_days": self.max_hold_days,
                    "trailing_stop_atr": self.trailing_stop_atr,
                    "use_rsi_filter": self.use_rsi_filter,
                }
                
                session_id = str(self.GetParameter("session-id") or "")
                if not session_id or session_id == "default":
                    session_id = None
                
                self.db.start_session(session_type, params_snapshot, session_id)
                self.Debug(f"[SQL] Session started: {self.db.session_id}")
                
            except Exception as e:
                self.Debug(f"[SQL] Failed to initialize: {e}")
                self.db = None
        
        self.Debug("TQQQDailyMeanReversionAlgorithm v1.0 Initialized")
    
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
    
    def _try_process_daily(self) -> None:
        """Process once both daily bars are ready"""
        if not (self.tqqq_bar_ready and self.sqqq_bar_ready):
            return
        
        tqqq_bar = self.pending_tqqq_bar
        sqqq_bar = self.pending_sqqq_bar
        
        # Reset flags
        self.tqqq_bar_ready = False
        self.sqqq_bar_ready = False
        
        # Update price history
        self._update_history(tqqq_bar, sqqq_bar)
        
        if self.IsWarmingUp:
            return
        
        # Need enough history
        if len(self.ratio_history) < self.zscore_lookback:
            self.Debug(f"{self.Time} Building ratio history: {len(self.ratio_history)}/{self.zscore_lookback}")
            return
        
        # Increment days counter
        self.days_since_trade += 1
        
        # Calculate Z-score
        zscore = self._calculate_zscore()
        
        # Calculate RSI of ratio if needed
        rsi_value = self._calculate_ratio_rsi() if self.use_rsi_filter else None
        
        # Log weekly
        if self.Time.weekday() == 0:
            ratio = list(self.ratio_history)[-1]
            rsi_str = f", RSI: {rsi_value:.1f}" if rsi_value is not None else ""
            self.Debug(
                f"{self.Time.date()} Ratio: {ratio:.4f}, Z-score: {zscore:.2f}{rsi_str} | "
                f"State: {self.position_state.value} | ATR: {self.ratio_atr:.4f}"
            )
        
        # Process exit logic first
        if self.position_state != DailyMRPositionState.FLAT:
            self._process_exits(zscore, tqqq_bar, sqqq_bar)
        
        # Then entry logic
        if self.position_state == DailyMRPositionState.FLAT:
            self._process_entries(zscore, rsi_value, tqqq_bar, sqqq_bar)
    
    def _update_history(self, tqqq_bar: TradeBar, sqqq_bar: TradeBar) -> None:
        """Update price history, ratio, and ATR"""
        tqqq_close = tqqq_bar.Close
        sqqq_close = sqqq_bar.Close
        
        self.tqqq_closes.append(tqqq_close)
        self.sqqq_closes.append(sqqq_close)
        
        # Calculate ratio
        if sqqq_close > 0:
            ratio = tqqq_close / sqqq_close
            self.ratio_history.append(ratio)
            
            # True Range of ratio (for trailing stop ATR)
            if self.ratio_prev is not None:
                ratio_change = abs(ratio - self.ratio_prev)
                self.ratio_atr_history.append(ratio_change)
                if len(self.ratio_atr_history) >= self.atr_period:
                    self.ratio_atr = statistics.mean(list(self.ratio_atr_history)[-self.atr_period:])
            self.ratio_prev = ratio
        
        # TQQQ ATR for vol scaling
        if self.tqqq_prev_close is not None:
            tr = max(
                tqqq_bar.High - tqqq_bar.Low,
                abs(tqqq_bar.High - self.tqqq_prev_close),
                abs(tqqq_bar.Low - self.tqqq_prev_close)
            )
            self.ratio_tr_history.append(tr)
            if len(self.ratio_tr_history) >= self.atr_period:
                self.tqqq_atr = statistics.mean(list(self.ratio_tr_history)[-self.atr_period:])
                self.atr_median_history.append(self.tqqq_atr)
        self.tqqq_prev_close = tqqq_close
    
    # =========================================================
    # Z-SCORE AND RSI CALCULATIONS
    # =========================================================
    
    def _calculate_zscore(self) -> float:
        """Calculate Z-score of current ratio vs lookback period"""
        if len(self.ratio_history) < self.zscore_lookback:
            return 0.0
        
        ratios = list(self.ratio_history)[-self.zscore_lookback:]
        mean = statistics.mean(ratios)
        stdev = statistics.stdev(ratios)
        
        if stdev == 0:
            return 0.0
        
        current_ratio = ratios[-1]
        return (current_ratio - mean) / stdev
    
    def _calculate_ratio_rsi(self) -> float:
        """Calculate RSI of the price ratio (simple Wilder's RSI)"""
        if len(self.ratio_history) < self.rsi_period + 1:
            return 50.0  # Neutral
        
        ratios = list(self.ratio_history)[-(self.rsi_period + 1):]
        changes = [ratios[i] - ratios[i-1] for i in range(1, len(ratios))]
        
        gains = [c for c in changes if c > 0]
        losses = [-c for c in changes if c < 0]
        
        avg_gain = statistics.mean(gains) if gains else 0.0001
        avg_loss = statistics.mean(losses) if losses else 0.0001
        
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    # =========================================================
    # ENTRY LOGIC
    # =========================================================
    
    def _process_entries(
        self, zscore: float, rsi_value: Optional[float],
        tqqq_bar: TradeBar, sqqq_bar: TradeBar
    ) -> None:
        """Check for mean-reversion entry signals"""
        
        # Minimum days between trades
        if self.days_since_trade < self.min_days_between:
            return
        
        # Calculate position size (with optional vol scaling)
        size = self.position_size
        if self.use_vol_scaling and len(self.atr_median_history) >= 20:
            atr_median = statistics.median(list(self.atr_median_history))
            if atr_median > 0 and self.tqqq_atr > atr_median * self.vol_scale_threshold:
                size *= self.vol_scale_factor
                self.Debug(f"[VOL] ATR {self.tqqq_atr:.2f} > {self.vol_scale_threshold}x median {atr_median:.2f} → size scaled to {size:.0%}")
        
        # Z-score LOW (negative) → Ratio compressed → TQQQ is cheap → Buy TQQQ
        if zscore < -self.entry_zscore:
            # Optional RSI confirmation
            if self.use_rsi_filter and rsi_value is not None:
                if rsi_value > self.rsi_oversold:
                    return  # RSI not oversold enough
            
            self._enter_position("TQQQ", self.tqqq, tqqq_bar.Close, zscore, size)
        
        # Z-score HIGH (positive) → Ratio extended → SQQQ is cheap → Buy SQQQ
        elif zscore > self.entry_zscore:
            # Optional RSI confirmation
            if self.use_rsi_filter and rsi_value is not None:
                if rsi_value < self.rsi_overbought:
                    return  # RSI not overbought enough
            
            self._enter_position("SQQQ", self.sqqq, sqqq_bar.Close, zscore, size)
    
    def _enter_position(
        self, symbol_name: str, symbol, price: float,
        zscore: float, size: float
    ) -> None:
        """Enter a long position"""
        self.SetHoldings(symbol, size, tag=f"DailyMR {symbol_name} Entry: Z={zscore:.2f}")
        
        self.entry_price = price
        self.entry_time = self.Time
        self.trade_entry_zscore = zscore
        self.days_since_trade = 0
        self.best_price_since_entry = price
        self.trailing_stop_price = None
        
        if symbol_name == "TQQQ":
            self.position_state = DailyMRPositionState.LONG_TQQQ
        else:
            self.position_state = DailyMRPositionState.LONG_SQQQ
        
        self.Log(
            f"[ENTRY] {symbol_name} @ {price:.2f} | Z-score: {zscore:.2f} | "
            f"Size: {size:.0%} | Ratio ATR: {self.ratio_atr:.4f}"
        )
    
    # =========================================================
    # EXIT LOGIC
    # =========================================================
    
    def _process_exits(
        self, zscore: float,
        tqqq_bar: TradeBar, sqqq_bar: TradeBar
    ) -> None:
        """Check exit conditions"""
        
        if self.position_state == DailyMRPositionState.LONG_TQQQ:
            symbol = self.tqqq
            symbol_name = "TQQQ"
            price = tqqq_bar.Close
        elif self.position_state == DailyMRPositionState.LONG_SQQQ:
            symbol = self.sqqq
            symbol_name = "SQQQ"
            price = sqqq_bar.Close
        else:
            return
        
        pnl_pct = (price - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
        
        # Update best price for trailing stop
        self.best_price_since_entry = max(self.best_price_since_entry, price)
        
        exit_reason = None
        
        # =====================================================
        # EXIT 1: Hard stop loss
        # =====================================================
        if pnl_pct < -self.stop_loss_pct:
            exit_reason = f"Stop loss: {pnl_pct:.2%}"
        
        # =====================================================
        # EXIT 2: Z-score mean reversion complete
        # =====================================================
        if exit_reason is None:
            if self.position_state == DailyMRPositionState.LONG_TQQQ:
                # Entered on negative Z, exit when Z crosses above target
                if zscore > -self.exit_target_zscore:
                    exit_reason = f"Z-score reversion: {zscore:.2f} (target: {-self.exit_target_zscore:.2f})"
            elif self.position_state == DailyMRPositionState.LONG_SQQQ:
                # Entered on positive Z, exit when Z crosses below target
                if zscore < self.exit_target_zscore:
                    exit_reason = f"Z-score reversion: {zscore:.2f} (target: {self.exit_target_zscore:.2f})"
        
        # =====================================================
        # EXIT 3: Trailing stop (ATR-based)
        # =====================================================
        if exit_reason is None and self.trailing_stop_atr > 0 and self.ratio_atr > 0:
            trail_distance = self.trailing_stop_atr * self.ratio_atr * self.entry_price / (list(self.ratio_history)[-1] if self.ratio_history else 1)
            trailing_stop = self.best_price_since_entry - trail_distance
            
            if self.trailing_stop_price is None or trailing_stop > self.trailing_stop_price:
                self.trailing_stop_price = trailing_stop
            
            if price < self.trailing_stop_price:
                exit_reason = f"Trailing stop: {price:.2f} < {self.trailing_stop_price:.2f}"
        
        # =====================================================
        # EXIT 4: Max hold days
        # =====================================================
        if exit_reason is None and self.max_hold_days > 0 and self.entry_time:
            hold_days = (self.Time - self.entry_time).days
            if hold_days >= self.max_hold_days:
                exit_reason = f"Max hold: {hold_days} days"
        
        if exit_reason:
            self._exit_position(symbol, symbol_name, price, zscore, pnl_pct, exit_reason)
    
    def _exit_position(
        self, symbol, symbol_name: str, exit_price: float,
        zscore: float, pnl_pct: float, reason: str
    ) -> None:
        """Exit current position"""
        quantity = self.Portfolio[symbol].Quantity
        pnl = (exit_price - self.entry_price) * quantity
        hold_days = (self.Time - self.entry_time).days if self.entry_time else 0
        
        self.Liquidate(symbol, tag=f"DailyMR Exit: {reason}")
        
        # Record trade
        trade_record = DailyMRTradeRecord(
            symbol=symbol_name,
            entry_time=self.entry_time or self.Time,
            exit_time=self.Time,
            entry_price=self.entry_price,
            exit_price=exit_price,
            quantity=quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            entry_zscore=self.trade_entry_zscore,
            exit_zscore=zscore,
            hold_duration_days=hold_days,
            exit_reason=reason
        )
        self.trade_history.append(trade_record)
        
        self.Log(
            f"[EXIT] {symbol_name} @ {exit_price:.2f} | P&L: {pnl_pct:.2%} (${pnl:,.2f}) | "
            f"Z: {self.trade_entry_zscore:.2f}→{zscore:.2f} | Hold: {hold_days}d | {reason}"
        )
        
        # SQL logging
        if self.db and self.entry_time:
            self.db.log_trade(
                symbol=symbol_name,
                side="BUY",
                quantity=quantity,
                entry_price=self.entry_price,
                exit_price=exit_price,
                entry_time=self.entry_time,
                exit_time=self.Time,
                entry_reason=f"Daily MR Z-score entry: {self.trade_entry_zscore:.2f}",
                exit_reason=reason
            )
        
        # Reset state
        self.position_state = DailyMRPositionState.FLAT
        self.entry_price = 0.0
        self.entry_time = None
        self.trade_entry_zscore = 0.0
        self.days_since_trade = 0
        self.trailing_stop_price = None
        self.best_price_since_entry = 0.0
    
    # =========================================================
    # END OF ALGORITHM
    # =========================================================
    
    def OnEndOfAlgorithm(self) -> None:
        """Log summary at end of backtest"""
        # Close any open position
        if self.position_state != DailyMRPositionState.FLAT:
            if self.position_state == DailyMRPositionState.LONG_TQQQ:
                price = self.Securities[self.tqqq].Price
                zscore = self._calculate_zscore()
                pnl_pct = (price - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
                self._exit_position(self.tqqq, "TQQQ", price, zscore, pnl_pct, "End of Backtest")
            else:
                price = self.Securities[self.sqqq].Price
                zscore = self._calculate_zscore()
                pnl_pct = (price - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
                self._exit_position(self.sqqq, "SQQQ", price, zscore, pnl_pct, "End of Backtest")
        
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
        
        # TQQQ vs SQQQ breakdown
        tqqq_trades = [t for t in self.trade_history if t.symbol == "TQQQ"]
        sqqq_trades = [t for t in self.trade_history if t.symbol == "SQQQ"]
        tqqq_pnl = sum(t.pnl for t in tqqq_trades)
        sqqq_pnl = sum(t.pnl for t in sqqq_trades)
        
        self.Log(f"[SUMMARY] === DAILY MEAN REVERSION RESULTS ===")
        self.Log(f"[SUMMARY] Total Trades: {total_trades}")
        self.Log(f"[SUMMARY] Win Rate: {win_rate:.1%} ({winning_trades}W / {total_trades - winning_trades}L)")
        self.Log(f"[SUMMARY] Total P&L: ${total_pnl:,.2f}")
        self.Log(f"[SUMMARY] Total Return: {total_return:.2%}")
        self.Log(f"[SUMMARY] Avg Win: ${avg_win:,.2f}, Avg Loss: ${avg_loss:,.2f}, R Ratio: {r_ratio:.2f}")
        self.Log(f"[SUMMARY] Avg Hold: {avg_hold:.1f} days")
        self.Log(f"[SUMMARY] TQQQ Trades: {len(tqqq_trades)}, P&L: ${tqqq_pnl:,.2f}")
        self.Log(f"[SUMMARY] SQQQ Trades: {len(sqqq_trades)}, P&L: ${sqqq_pnl:,.2f}")
        
        # SQL session end
        if self.db:
            self.db.end_session(
                total_return=total_return,
                total_trades=total_trades,
                win_rate=win_rate
            )
