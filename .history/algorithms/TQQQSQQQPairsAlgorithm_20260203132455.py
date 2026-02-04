# region imports
from AlgorithmImports import *  # type: ignore
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from collections import deque
import statistics

# SQL Persistence for Trade-Mind MCP integration
try:
    from sql_connector import TradingDBConnector, create_connector  # type: ignore
    HAS_SQL_CONNECTOR = True
except ImportError:
    HAS_SQL_CONNECTOR = False
# endregion

"""
TQQQ/SQQQ Pairs Ratio Strategy
==============================
Strategy: Trade the TQQQ/SQQQ price ratio using Z-score mean reversion
Position: LONG-ONLY (buy TQQQ when ratio low, buy SQQQ when ratio high)
Concept: Both 3x ETFs decay over time. The ratio between them reverts to mean.

Key Insight:
- We're NOT predicting market direction
- We're betting on which ETF is "relatively cheap"
- When ratio is low → TQQQ is cheap → Buy TQQQ
- When ratio is high → SQQQ is cheap → Buy SQQQ
- Exit when ratio normalizes (Z-score → 0)

Author: Trading Plan Implementation
Version: 3.0.0 (Pairs Strategy)
"""


class PositionState(Enum):
    """Current position state"""
    FLAT = "flat"
    LONG_TQQQ = "long_tqqq"
    LONG_SQQQ = "long_sqqq"


@dataclass
class TradeRecord:
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
    hold_duration_minutes: int


class TQQQSQQQPairsAlgorithm(QCAlgorithm):
    """
    TQQQ/SQQQ Pairs Ratio Mean-Reversion Strategy
    
    Signal Logic:
    - Calculate TQQQ/SQQQ price ratio
    - Compute rolling Z-score of the ratio
    - Z-score < -entry_threshold → Buy TQQQ (ratio is low, TQQQ cheap)
    - Z-score > +entry_threshold → Buy SQQQ (ratio is high, SQQQ cheap)
    - |Z-score| < exit_threshold → Close position (ratio normalized)
    
    Risk Management:
    - Stop loss based on Z-score extremes OR percentage loss
    - Maximum hold time (avoid being stuck in diverging spread)
    - Intraday only (close all at 3:50 PM)
    """
    
    def Initialize(self):  # type: ignore
        """Initialize algorithm settings, securities, and indicators"""
        
        # =====================================================
        # BASIC SETTINGS
        # =====================================================
        start_date_str = str(self.GetParameter("start-date") or "2026-01-02")  # type: ignore
        end_date_str = str(self.GetParameter("end-date") or "2026-01-14")  # type: ignore
        
        try:
            start_parts = start_date_str.split("-")
            self.SetStartDate(int(start_parts[0]), int(start_parts[1]), int(start_parts[2]))  # type: ignore
        except:
            self.SetStartDate(2026, 1, 2)  # type: ignore
        
        try:
            end_parts = end_date_str.split("-")
            self.SetEndDate(int(end_parts[0]), int(end_parts[1]), int(end_parts[2]))  # type: ignore
        except:
            self.SetEndDate(2026, 1, 14)  # type: ignore
        
        initial_cash = float(self.GetParameter("cash") or 100000)  # type: ignore
        self.SetCash(initial_cash)  # type: ignore
        
        self.SetBrokerageModel(BrokerageName.Alpaca, AccountType.Margin)  # type: ignore
        
        # =====================================================
        # PAIRS STRATEGY PARAMETERS
        # =====================================================
        
        # Z-score lookback period (number of 5-min bars)
        self.zscore_lookback = int(float(self.GetParameter("zscore-lookback") or self.GetParameter("zscore_lookback") or 50))  # type: ignore
        
        # Entry threshold (how many std devs from mean)
        self.entry_zscore = float(self.GetParameter("entry-zscore") or self.GetParameter("entry_zscore") or 1.5)  # type: ignore
        
        # Exit threshold (close when Z-score approaches this)
        self.exit_zscore = float(self.GetParameter("exit-zscore") or self.GetParameter("exit_zscore") or 0.3)  # type: ignore
        
        # Stop loss Z-score (exit if spread diverges further)
        self.stop_zscore = float(self.GetParameter("stop-zscore") or self.GetParameter("stop_zscore") or 3.0)  # type: ignore
        
        # Percentage stop loss (backup safety)
        self.stop_loss_pct = float(self.GetParameter("stop-loss-pct") or self.GetParameter("stop_loss_pct") or 0.03)  # type: ignore
        
        # Position size (percentage of portfolio)
        self.position_size = float(self.GetParameter("position-size") or self.GetParameter("position_size") or 0.50)  # type: ignore
        
        # Maximum hold time in minutes (0 = no limit)
        self.max_hold_minutes = int(float(self.GetParameter("max-hold-minutes") or self.GetParameter("max_hold_minutes") or 0))  # type: ignore
        
        # Minimum bars between trades (avoid overtrading)
        self.min_bars_between_trades = int(float(self.GetParameter("min-bars-between") or self.GetParameter("min_bars_between") or 3))  # type: ignore
        
        # Log parameters
        self.Log(f"[PARAMS] Z-score Lookback: {self.zscore_lookback} bars")  # type: ignore
        self.Log(f"[PARAMS] Entry Z-score: ±{self.entry_zscore}, Exit Z-score: ±{self.exit_zscore}")  # type: ignore
        self.Log(f"[PARAMS] Stop Z-score: ±{self.stop_zscore}, Stop Loss: {self.stop_loss_pct:.1%}")  # type: ignore
        self.Log(f"[PARAMS] Position Size: {self.position_size:.0%}")  # type: ignore
        
        # =====================================================
        # ADD SECURITIES
        # =====================================================
        self.tqqq = self.AddEquity("TQQQ", Resolution.Minute).Symbol
        self.sqqq = self.AddEquity("SQQQ", Resolution.Minute).Symbol
        
        # =====================================================
        # CONSOLIDATORS (5-minute bars)
        # =====================================================
        self.bar_period = timedelta(minutes=5)
        
        self.tqqq_consolidator = TradeBarConsolidator(self.bar_period)
        self.tqqq_consolidator.DataConsolidated += self.OnTQQQBarConsolidated
        self.SubscriptionManager.AddConsolidator(self.tqqq, self.tqqq_consolidator)
        
        self.sqqq_consolidator = TradeBarConsolidator(self.bar_period)
        self.sqqq_consolidator.DataConsolidated += self.OnSQQQBarConsolidated
        self.SubscriptionManager.AddConsolidator(self.sqqq, self.sqqq_consolidator)
        
        # =====================================================
        # RATIO TRACKING
        # =====================================================
        self.ratio_history: deque = deque(maxlen=self.zscore_lookback)
        self.last_tqqq_price: Optional[float] = None
        self.last_sqqq_price: Optional[float] = None
        self.last_tqqq_bar: Optional[TradeBar] = None
        self.last_sqqq_bar: Optional[TradeBar] = None
        
        # =====================================================
        # POSITION TRACKING
        # =====================================================
        self.position_state = PositionState.FLAT
        self.entry_price: float = 0.0
        self.entry_time: Optional[datetime] = None
        self.entry_zscore: float = 0.0
        self.bars_since_trade: int = 0
        
        # Trade history
        self.trade_history: List[TradeRecord] = []
        self.daily_trades_count: int = 0
        self.max_daily_trades = int(self.GetParameter("max_daily_trades") or 10)
        
        # =====================================================
        # SCHEDULING
        # =====================================================
        self.Schedule.On(
            self.DateRules.EveryDay(self.tqqq),
            self.TimeRules.At(15, 50),
            self.CloseAllPositions
        )
        
        self.Schedule.On(
            self.DateRules.EveryDay(self.tqqq),
            self.TimeRules.AfterMarketOpen(self.tqqq, 5),
            self.ResetDailyState
        )
        
        # =====================================================
        # WARMUP
        # =====================================================
        warmup_days = int(self.GetParameter("warmup-days") or "0")
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
                    "strategy": "PAIRS_RATIO",
                    "zscore_lookback": self.zscore_lookback,
                    "entry_zscore": self.entry_zscore,
                    "exit_zscore": self.exit_zscore,
                    "stop_zscore": self.stop_zscore,
                    "stop_loss_pct": self.stop_loss_pct,
                    "position_size": self.position_size,
                }
                
                session_id = str(self.GetParameter("session-id") or "")  # type: ignore
                if not session_id or session_id == "default":
                    session_id = None
                
                self.db.start_session(session_type, params_snapshot, session_id)
                self.Debug(f"[SQL] Session started: {self.db.session_id}")
                
            except Exception as e:
                self.Debug(f"[SQL] Failed to initialize: {e}")
                self.db = None
        
        self.Debug("TQQQSQQQPairsAlgorithm Initialized")
    
    # =========================================================
    # CONSOLIDATED BAR HANDLERS
    # =========================================================
    
    def OnTQQQBarConsolidated(self, sender, bar: TradeBar) -> None:
        """Handle TQQQ 5-minute bar"""
        self.last_tqqq_price = bar.Close
        self.last_tqqq_bar = bar
        self.TryProcessSignals()
    
    def OnSQQQBarConsolidated(self, sender, bar: TradeBar) -> None:
        """Handle SQQQ 5-minute bar"""
        self.last_sqqq_price = bar.Close
        self.last_sqqq_bar = bar
        self.TryProcessSignals()
    
    def TryProcessSignals(self) -> None:
        """Process signals when both bars are available"""
        if self.IsWarmingUp:
            return
        
        if self.last_tqqq_price is None or self.last_sqqq_price is None:
            return
        
        if self.last_tqqq_bar is None or self.last_sqqq_bar is None:
            return
        
        # Ensure bars are from same time (within tolerance)
        time_diff = abs((self.last_tqqq_bar.EndTime - self.last_sqqq_bar.EndTime).total_seconds())
        if time_diff > 60:  # More than 1 minute apart
            return
        
        # Skip if outside trading hours
        if not self.IsWithinTradingHours():
            return
        
        # Calculate ratio and update history
        ratio = self.last_tqqq_price / self.last_sqqq_price if self.last_sqqq_price > 0 else 0
        self.ratio_history.append(ratio)
        
        # Need enough history for Z-score
        if len(self.ratio_history) < self.zscore_lookback:
            if self.Time.minute == 0:
                self.Debug(f"{self.Time} Building ratio history: {len(self.ratio_history)}/{self.zscore_lookback}")
            return
        
        # Calculate Z-score
        zscore = self.CalculateZScore()
        
        # Increment bars since trade
        self.bars_since_trade += 1
        
        # Log every hour
        if self.Time.minute == 0:
            self.Debug(f"{self.Time} Ratio: {ratio:.4f}, Z-score: {zscore:.2f}, State: {self.position_state.value}")
        
        # Process exit logic first
        if self.position_state != PositionState.FLAT:
            self.ProcessExitSignals(zscore)
        
        # Then entry logic
        if self.position_state == PositionState.FLAT:
            self.ProcessEntrySignals(zscore)
        
        # Reset price tracking for next bar pair
        self.last_tqqq_price = None
        self.last_sqqq_price = None
    
    # =========================================================
    # Z-SCORE CALCULATION
    # =========================================================
    
    def CalculateZScore(self) -> float:
        """Calculate Z-score of current ratio vs historical mean"""
        if len(self.ratio_history) < 2:
            return 0.0
        
        ratios = list(self.ratio_history)
        mean = statistics.mean(ratios)
        stdev = statistics.stdev(ratios)
        
        if stdev == 0:
            return 0.0
        
        current_ratio = ratios[-1]
        return (current_ratio - mean) / stdev
    
    # =========================================================
    # ENTRY LOGIC
    # =========================================================
    
    def ProcessEntrySignals(self, zscore: float) -> None:
        """Check for entry signals based on Z-score"""
        
        # Check trade limits
        if self.daily_trades_count >= self.max_daily_trades:
            return
        
        # Minimum bars between trades
        if self.bars_since_trade < self.min_bars_between_trades:
            return
        
        # Z-score LOW (negative) → TQQQ is cheap → Buy TQQQ
        if zscore < -self.entry_zscore:
            self.EnterPosition(self.tqqq, "TQQQ", zscore)
        
        # Z-score HIGH (positive) → SQQQ is cheap → Buy SQQQ
        elif zscore > self.entry_zscore:
            self.EnterPosition(self.sqqq, "SQQQ", zscore)
    
    def EnterPosition(self, symbol, symbol_name: str, zscore: float) -> None:
        """Enter a long position"""
        self.SetHoldings(symbol, self.position_size, tag=f"{symbol_name} Entry: Z={zscore:.2f}")
        
        current_price = self.Securities[symbol].Price
        self.entry_price = current_price
        self.entry_time = self.Time
        self.entry_zscore = zscore
        self.bars_since_trade = 0
        self.daily_trades_count += 1
        
        if symbol_name == "TQQQ":
            self.position_state = PositionState.LONG_TQQQ
        else:
            self.position_state = PositionState.LONG_SQQQ
        
        self.Log(f"[ENTRY] {symbol_name} @ {current_price:.2f}, Z-score: {zscore:.2f}")
        
        # SQL logging
        if self.db:
            self.db.log_trade(
                symbol=symbol_name,
                side="BUY",
                quantity=self.Portfolio[symbol].Quantity,
                price=current_price,
                order_type="MARKET",
                strategy_signal=f"Z-score entry: {zscore:.2f}",
                indicators={"zscore": zscore, "ratio": list(self.ratio_history)[-1]}
            )
    
    # =========================================================
    # EXIT LOGIC
    # =========================================================
    
    def ProcessExitSignals(self, zscore: float) -> None:
        """Check for exit signals"""
        
        symbol = self.tqqq if self.position_state == PositionState.LONG_TQQQ else self.sqqq
        symbol_name = "TQQQ" if self.position_state == PositionState.LONG_TQQQ else "SQQQ"
        
        current_price = self.Securities[symbol].Price
        pnl_pct = (current_price - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
        
        exit_reason = None
        
        # Exit 1: Z-score normalized (mean reversion complete)
        if self.position_state == PositionState.LONG_TQQQ and zscore > -self.exit_zscore:
            exit_reason = f"Z-score normalized: {zscore:.2f}"
        elif self.position_state == PositionState.LONG_SQQQ and zscore < self.exit_zscore:
            exit_reason = f"Z-score normalized: {zscore:.2f}"
        
        # Exit 2: Z-score diverged too far (stop loss on spread)
        elif self.position_state == PositionState.LONG_TQQQ and zscore < -self.stop_zscore:
            exit_reason = f"Z-score stop: {zscore:.2f}"
        elif self.position_state == PositionState.LONG_SQQQ and zscore > self.stop_zscore:
            exit_reason = f"Z-score stop: {zscore:.2f}"
        
        # Exit 3: Percentage stop loss
        elif pnl_pct < -self.stop_loss_pct:
            exit_reason = f"Stop loss: {pnl_pct:.2%}"
        
        # Exit 4: Maximum hold time
        elif self.max_hold_minutes > 0 and self.entry_time:
            hold_minutes = (self.Time - self.entry_time).total_seconds() / 60
            if hold_minutes > self.max_hold_minutes:
                exit_reason = f"Max hold time: {hold_minutes:.0f} min"
        
        if exit_reason:
            self.ExitPosition(symbol, symbol_name, zscore, pnl_pct, exit_reason)
    
    def ExitPosition(self, symbol, symbol_name: str, zscore: float, pnl_pct: float, reason: str) -> None:
        """Exit current position"""
        current_price = self.Securities[symbol].Price
        quantity = self.Portfolio[symbol].Quantity
        
        self.Liquidate(symbol, tag=f"{symbol_name} Exit: {reason}")
        
        # Record trade
        if self.entry_time:
            hold_minutes = int((self.Time - self.entry_time).total_seconds() / 60)
            pnl = (current_price - self.entry_price) * quantity
            
            trade_record = TradeRecord(
                symbol=symbol_name,
                entry_time=self.entry_time,
                exit_time=self.Time,
                entry_price=self.entry_price,
                exit_price=current_price,
                quantity=quantity,
                pnl=pnl,
                pnl_pct=pnl_pct,
                entry_zscore=self.entry_zscore,
                exit_zscore=zscore,
                hold_duration_minutes=hold_minutes
            )
            self.trade_history.append(trade_record)
            
            self.Log(f"[EXIT] {symbol_name} @ {current_price:.2f}, P&L: {pnl_pct:.2%}, Reason: {reason}")
        
        # SQL logging
        if self.db:
            self.db.log_trade(
                symbol=symbol_name,
                side="SELL",
                quantity=quantity,
                price=current_price,
                order_type="MARKET",
                strategy_signal=reason,
                indicators={"zscore": zscore, "pnl_pct": pnl_pct}
            )
        
        # Reset state
        self.position_state = PositionState.FLAT
        self.entry_price = 0.0
        self.entry_time = None
        self.entry_zscore = 0.0
        self.bars_since_trade = 0
    
    # =========================================================
    # HELPER METHODS
    # =========================================================
    
    def IsWithinTradingHours(self) -> bool:
        """Check if within trading hours (9:35 AM - 3:45 PM)"""
        current_time = self.Time.time()
        market_open = dt_time(9, 35)
        market_close = dt_time(15, 45)
        return market_open <= current_time <= market_close
    
    def CloseAllPositions(self) -> None:
        """Close all positions at end of day"""
        if self.position_state != PositionState.FLAT:
            symbol = self.tqqq if self.position_state == PositionState.LONG_TQQQ else self.sqqq
            symbol_name = "TQQQ" if self.position_state == PositionState.LONG_TQQQ else "SQQQ"
            zscore = self.CalculateZScore() if len(self.ratio_history) >= 2 else 0
            current_price = self.Securities[symbol].Price
            pnl_pct = (current_price - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
            
            self.ExitPosition(symbol, symbol_name, zscore, pnl_pct, "EOD Close")
        
        self.Log(f"[EOD] All positions closed. Daily trades: {self.daily_trades_count}")
    
    def ResetDailyState(self) -> None:
        """Reset daily counters at market open"""
        self.daily_trades_count = 0
        self.Log(f"[NEW DAY] Daily state reset")
    
    def OnEndOfAlgorithm(self) -> None:
        """Log summary at end of backtest"""
        if not self.trade_history:
            self.Log("[SUMMARY] No trades executed")
            return
        
        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t.pnl > 0)
        total_pnl = sum(t.pnl for t in self.trade_history)
        
        self.Log(f"[SUMMARY] Total Trades: {total_trades}")
        self.Log(f"[SUMMARY] Winning: {winning_trades}, Losing: {total_trades - winning_trades}")
        self.Log(f"[SUMMARY] Win Rate: {winning_trades/total_trades:.1%}" if total_trades > 0 else "N/A")
        self.Log(f"[SUMMARY] Total P&L: ${total_pnl:.2f}")
        
        # SQL session end
        if self.db:
            self.db.end_session(
                final_balance=self.Portfolio.TotalPortfolioValue,
                total_return=(self.Portfolio.TotalPortfolioValue - 100000) / 100000,
                notes=f"Pairs strategy: {total_trades} trades"
            )
