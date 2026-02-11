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
QQQ RSI(2) Mean Reversion Swing Trading Strategy
===================================================
Strategy: Buy QQQ on oversold RSI bounces within confirmed uptrends.
Concept:  Larry Connors' RSI(2) strategy — the most academically validated
          mean reversion approach in existence.

Core Rules:
  1. TREND FILTER: QQQ must be above SMA(trend_sma) to take long trades
  2. ENTRY: Buy when RSI(rsi_period) drops below rsi_entry threshold
  3. EXIT:  Sell when RSI(rsi_period) rises above rsi_exit threshold
  4. SAFETY: Force exit if held longer than max_hold_days (0=unlimited)
  5. SAFETY: Force exit if trend filter breaks (QQQ drops below SMA)

Why This Works:
  - Stocks (and QQQ) tend to bounce after short-term oversold conditions
  - The SMA trend filter ensures we only buy dips in uptrends, not falling knives
  - RSI(2) is extremely sensitive — catches 2-5 day pullbacks perfectly
  - 65-75% historical win rate with favorable risk/reward

Key Design Principles:
  - Signal source: QQQ daily closes
  - Trade execution: End-of-day only (3:50 PM ET)
  - Hold period: 2-10 days typically
  - Uses QQQ (1x) not TQQQ — appropriate leverage for swing trades
  - Completely independent from TQQQ Position Trend strategy

Parameters:
  - rsi-period:       RSI calculation period (default 2)
  - rsi-entry:        Buy when RSI drops below this (default 10)
  - rsi-exit:         Sell when RSI rises above this (default 70)
  - trend-sma:        SMA period for trend filter (default 200)
  - use-trend-filter: Whether to require price > SMA (default true)
  - allocation:       % of portfolio per trade (default 0.90)
  - max-hold-days:    Force exit after N days, 0=unlimited (default 0)

Author: Trading Plan Implementation
Version: 1.0.0 (RSI Mean Reversion)
"""


class TrendState(Enum):
    """Market trend classification for trade filtering"""
    UPTREND = "uptrend"       # QQQ above SMA → trades allowed
    DOWNTREND = "downtrend"   # QQQ below SMA → no new trades
    UNKNOWN = "unknown"       # Not enough data


@dataclass
class SwingTradeRecord:
    """Record of a completed swing trade"""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    hold_days: int
    entry_rsi: float
    exit_rsi: float
    exit_reason: str  # "rsi_exit", "trend_break", "max_hold", "end_of_algo"


class QQQMeanReversionAlgorithm(QCAlgorithm):
    """
    RSI(2) Mean Reversion Swing Trading on QQQ.
    
    Buys QQQ when RSI(2) drops below oversold threshold during uptrends.
    Sells when RSI(2) rises above overbought threshold.
    Hold period: typically 2-10 days.
    """
    
    def Initialize(self):  # type: ignore
        """Initialize algorithm settings, securities, and indicators"""
        
        # =====================================================
        # BASIC SETTINGS
        # =====================================================
        start_date_str = str(self.GetParameter("start-date") or "2025-01-02")
        end_date_str = str(self.GetParameter("end-date") or "2026-02-05")
        
        try:
            start_parts = start_date_str.split("-")
            self.SetStartDate(int(start_parts[0]), int(start_parts[1]), int(start_parts[2]))
        except Exception:
            self.SetStartDate(2025, 1, 2)
        
        try:
            end_parts = end_date_str.split("-")
            self.SetEndDate(int(end_parts[0]), int(end_parts[1]), int(end_parts[2]))
        except Exception:
            self.SetEndDate(2026, 2, 5)
        
        initial_cash = float(self.GetParameter("cash") or 100000)
        self.SetCash(initial_cash)
        self.initial_cash = initial_cash
        self.peak_equity = initial_cash
        
        self.SetBrokerageModel(BrokerageName.Alpaca, AccountType.Margin)
        
        # =====================================================
        # RSI MEAN REVERSION PARAMETERS
        # =====================================================
        
        # RSI settings
        self.rsi_period = int(float(self.GetParameter("rsi-period") or 2))
        self.rsi_entry = float(self.GetParameter("rsi-entry") or 10)
        self.rsi_exit = float(self.GetParameter("rsi-exit") or 70)
        
        # Trend filter
        self.trend_sma_period = int(float(self.GetParameter("trend-sma") or 200))
        self.use_trend_filter = str(self.GetParameter("use-trend-filter") or "true").lower() == "true"
        
        # Position sizing
        self.allocation = float(self.GetParameter("allocation") or 0.90)
        
        # Max hold days (0 = unlimited)
        self.max_hold_days = int(float(self.GetParameter("max-hold-days") or 0))
        
        # End-of-day execution window
        self.eod_hour = 15
        self.eod_minute = 50  # Execute trades at 3:50 PM ET
        
        # Log parameters
        self.Log(f"[PARAMS] RSI Period: {self.rsi_period}, Entry < {self.rsi_entry}, Exit > {self.rsi_exit}")
        self.Log(f"[PARAMS] Trend SMA: {self.trend_sma_period}, Use Filter: {self.use_trend_filter}")
        self.Log(f"[PARAMS] Allocation: {self.allocation:.0%}, Max Hold Days: {self.max_hold_days}")
        
        # =====================================================
        # ADD SECURITIES
        # =====================================================
        self.qqq = self.AddEquity("QQQ", Resolution.Minute).Symbol
        
        # =====================================================
        # DAILY BAR CONSOLIDATOR
        # =====================================================
        self.qqq_daily_consolidator = TradeBarConsolidator(timedelta(days=1))
        self.qqq_daily_consolidator.DataConsolidated += self.OnQQQDailyBar
        self.SubscriptionManager.AddConsolidator(self.qqq, self.qqq_daily_consolidator)
        
        # =====================================================
        # PRICE HISTORY FOR RSI AND SMA
        # =====================================================
        max_lookback = self.trend_sma_period + 10
        self.qqq_closes: deque = deque(maxlen=max_lookback)
        
        # RSI internals — Wilder's smoothed RSI
        self.rsi_avg_gain: float = 0.0
        self.rsi_avg_loss: float = 0.0
        self.rsi_value: float = 50.0  # Start neutral
        self.rsi_initialized: bool = False
        self.rsi_init_gains: List[float] = []
        self.rsi_init_losses: List[float] = []
        
        # SMA value
        self.trend_sma_value: float = 0.0
        
        # Current trend state
        self.current_trend = TrendState.UNKNOWN
        self.last_qqq_close: float = 0.0
        
        # =====================================================
        # POSITION TRACKING
        # =====================================================
        self.is_holding: bool = False
        self.entry_price: float = 0.0
        self.entry_time: Optional[datetime] = None
        self.entry_quantity: int = 0
        self.entry_rsi: float = 0.0
        self.hold_start_date: Optional[datetime] = None  # Trading days counter
        self.days_held: int = 0
        
        # =====================================================
        # TRADE EXECUTION FLAGS
        # =====================================================
        self.signal_generated_today: bool = False
        self.pending_action: Optional[str] = None  # "BUY_QQQ", "SELL_QQQ", None
        self.last_action_date: Optional[datetime] = None
        
        # =====================================================
        # TRADE HISTORY
        # =====================================================
        self.trade_history: List[SwingTradeRecord] = []
        
        # =====================================================
        # PERFORMANCE TRACKING
        # =====================================================
        self.total_wins: int = 0
        self.total_losses: int = 0
        self.gross_profit: float = 0.0
        self.gross_loss: float = 0.0
        
        # =====================================================
        # WARMUP
        # =====================================================
        warmup_days = self.trend_sma_period + 20
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
                    enabled=True,
                    strategy_id="QQQ_MEAN_REVERSION"
                )
                
                session_type = "BACKTEST" if not self.LiveMode else "LIVE"
                params_snapshot = {
                    "strategy": "QQQ_MEAN_REVERSION",
                    "rsi_period": self.rsi_period,
                    "rsi_entry": self.rsi_entry,
                    "rsi_exit": self.rsi_exit,
                    "trend_sma": self.trend_sma_period,
                    "use_trend_filter": self.use_trend_filter,
                    "allocation": self.allocation,
                    "max_hold_days": self.max_hold_days,
                }
                
                session_id = str(self.GetParameter("session-id") or "")
                if not session_id or session_id == "default":
                    session_id = None
                
                self.db.start_session(session_type, params_snapshot, session_id)
                self.Debug(f"[SQL] Session started: {self.db.session_id}")
                
            except Exception as e:
                self.Debug(f"[SQL] Failed to initialize: {e}")
                self.db = None
        
        self.Debug("QQQMeanReversionAlgorithm v1.0 Initialized")
    
    # =========================================================
    # DAILY BAR HANDLER — RSI & TREND CALCULATION
    # =========================================================
    
    def OnQQQDailyBar(self, sender, bar: TradeBar) -> None:
        """
        Handle completed QQQ daily bar.
        Calculate RSI, SMA, determine trend, generate signals.
        """
        close = float(bar.Close)
        self.qqq_closes.append(close)
        self.last_qqq_close = close
        
        # ---- Calculate SMA for trend filter ----
        if len(self.qqq_closes) >= self.trend_sma_period:
            closes_list = list(self.qqq_closes)
            self.trend_sma_value = sum(closes_list[-self.trend_sma_period:]) / self.trend_sma_period
        
        # ---- Calculate RSI (Wilder's smoothing) ----
        if len(self.qqq_closes) >= 2:
            prev_close = list(self.qqq_closes)[-2]
            change = close - prev_close
            gain = max(change, 0.0)
            loss = abs(min(change, 0.0))
            
            if not self.rsi_initialized:
                # Collecting initial period data
                self.rsi_init_gains.append(gain)
                self.rsi_init_losses.append(loss)
                
                if len(self.rsi_init_gains) >= self.rsi_period:
                    # First RSI: simple average
                    self.rsi_avg_gain = sum(self.rsi_init_gains[-self.rsi_period:]) / self.rsi_period
                    self.rsi_avg_loss = sum(self.rsi_init_losses[-self.rsi_period:]) / self.rsi_period
                    self.rsi_initialized = True
                    
                    if self.rsi_avg_loss == 0:
                        self.rsi_value = 100.0
                    else:
                        rs = self.rsi_avg_gain / self.rsi_avg_loss
                        self.rsi_value = 100.0 - (100.0 / (1.0 + rs))
            else:
                # Subsequent RSI: Wilder's smoothing
                self.rsi_avg_gain = (self.rsi_avg_gain * (self.rsi_period - 1) + gain) / self.rsi_period
                self.rsi_avg_loss = (self.rsi_avg_loss * (self.rsi_period - 1) + loss) / self.rsi_period
                
                if self.rsi_avg_loss == 0:
                    self.rsi_value = 100.0
                else:
                    rs = self.rsi_avg_gain / self.rsi_avg_loss
                    self.rsi_value = 100.0 - (100.0 / (1.0 + rs))
        
        # ---- Determine trend ----
        if self.trend_sma_value > 0:
            if close > self.trend_sma_value:
                self.current_trend = TrendState.UPTREND
            else:
                self.current_trend = TrendState.DOWNTREND
        
        # ---- Track holding days ----
        if self.is_holding:
            self.days_held += 1
        
        # ---- Skip if warming up ----
        if self.IsWarmingUp:
            return
        
        if not self.rsi_initialized:
            return
        
        # ---- Reset daily flag ----
        self.signal_generated_today = False
        
        # ---- Generate signal ----
        self._generate_signal()
        
        self.Log(f"[DAILY] QQQ={close:.2f} | RSI({self.rsi_period})={self.rsi_value:.1f} | "
                 f"SMA{self.trend_sma_period}={self.trend_sma_value:.2f} | "
                 f"Trend={self.current_trend.value} | Holding={self.is_holding} | "
                 f"Days={self.days_held} | Action={self.pending_action}")
    
    # =========================================================
    # SIGNAL GENERATION
    # =========================================================
    
    def _generate_signal(self) -> None:
        """
        Generate buy/sell signal based on RSI and trend.
        
        ENTRY: RSI < entry_threshold AND (price > SMA or no filter)
        EXIT:  RSI > exit_threshold OR trend break OR max hold exceeded
        """
        if self.is_holding:
            # === CHECK EXIT CONDITIONS ===
            
            # Exit 1: RSI overbought — primary exit
            if self.rsi_value > self.rsi_exit:
                self.pending_action = "SELL_QQQ"
                self.Log(f"[SIGNAL] RSI EXIT: RSI={self.rsi_value:.1f} > {self.rsi_exit}")
                return
            
            # Exit 2: Trend break — safety exit
            if self.use_trend_filter and self.current_trend == TrendState.DOWNTREND:
                self.pending_action = "SELL_QQQ"
                self.Log(f"[SIGNAL] TREND BREAK EXIT: QQQ={self.last_qqq_close:.2f} < SMA={self.trend_sma_value:.2f}")
                return
            
            # Exit 3: Max hold days exceeded
            if self.max_hold_days > 0 and self.days_held >= self.max_hold_days:
                self.pending_action = "SELL_QQQ"
                self.Log(f"[SIGNAL] MAX HOLD EXIT: {self.days_held} days >= {self.max_hold_days}")
                return
            
            # No exit signal — hold
            self.pending_action = None
        
        else:
            # === CHECK ENTRY CONDITIONS ===
            
            # Trend filter must be satisfied (if enabled)
            if self.use_trend_filter and self.current_trend != TrendState.UPTREND:
                self.pending_action = None
                return
            
            # RSI oversold — entry signal
            if self.rsi_value < self.rsi_entry:
                self.pending_action = "BUY_QQQ"
                self.Log(f"[SIGNAL] RSI ENTRY: RSI={self.rsi_value:.1f} < {self.rsi_entry}")
                return
            
            # No entry signal
            self.pending_action = None
    
    # =========================================================
    # MINUTE BAR HANDLER — END-OF-DAY EXECUTION
    # =========================================================
    
    def OnData(self, data: Slice) -> None:
        """Process minute data — execute trades at 3:50 PM ET."""
        if self.IsWarmingUp:
            return
        
        if self.pending_action is None:
            return
        
        current_time = self.Time
        
        # Only execute in the EOD window
        if current_time.hour != self.eod_hour or current_time.minute != self.eod_minute:
            return
        
        # Don't execute twice on the same day
        if self.last_action_date and self.last_action_date.date() == current_time.date():
            return
        
        # Get current QQQ price
        if not data.ContainsKey(self.qqq):
            return
        
        qqq_price = float(data[self.qqq].Close)
        
        if self.pending_action == "BUY_QQQ":
            self._execute_buy(qqq_price, current_time)
        elif self.pending_action == "SELL_QQQ":
            self._execute_sell(qqq_price, current_time)
        
        self.last_action_date = current_time
        self.pending_action = None
    
    # =========================================================
    # TRADE EXECUTION
    # =========================================================
    
    def _execute_buy(self, price: float, timestamp: datetime) -> None:
        """Buy QQQ at target allocation."""
        if self.is_holding:
            return
        
        target_value = self.Portfolio.TotalPortfolioValue * self.allocation
        quantity = int(target_value / price)
        
        if quantity <= 0:
            return
        
        self.SetHoldings(self.qqq, self.allocation)
        
        self.is_holding = True
        self.entry_price = price
        self.entry_time = timestamp
        self.entry_quantity = quantity
        self.entry_rsi = self.rsi_value
        self.hold_start_date = timestamp
        self.days_held = 0
        
        self.Log(f"[BUY] QQQ @ {price:.2f} | Qty≈{quantity} | RSI={self.rsi_value:.1f} | "
                 f"Alloc={self.allocation:.0%}")
    
    def _execute_sell(self, price: float, timestamp: datetime) -> None:
        """Sell QQQ position — close swing trade."""
        if not self.is_holding:
            return
        
        # Determine exit reason
        exit_reason = "rsi_exit"
        if self.use_trend_filter and self.current_trend == TrendState.DOWNTREND:
            exit_reason = "trend_break"
        if self.max_hold_days > 0 and self.days_held >= self.max_hold_days:
            exit_reason = "max_hold"
        
        # Calculate PnL
        pnl = (price - self.entry_price) * self.entry_quantity
        pnl_pct = (price - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
        
        # Track performance
        if pnl > 0:
            self.total_wins += 1
            self.gross_profit += pnl
        else:
            self.total_losses += 1
            self.gross_loss += abs(pnl)
        
        # Record trade
        trade_record = SwingTradeRecord(
            symbol="QQQ",
            entry_time=self.entry_time,
            exit_time=timestamp,
            entry_price=self.entry_price,
            exit_price=price,
            quantity=self.entry_quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            hold_days=self.days_held,
            entry_rsi=self.entry_rsi,
            exit_rsi=self.rsi_value,
            exit_reason=exit_reason,
        )
        self.trade_history.append(trade_record)
        
        win_label = "WIN" if pnl > 0 else "LOSS"
        self.Log(f"[SELL] QQQ @ {price:.2f} | {win_label} ${pnl:+,.2f} ({pnl_pct:+.2%}) | "
                 f"Held {self.days_held}d | RSI={self.rsi_value:.1f} | Reason={exit_reason}")
        
        # Liquidate
        self.Liquidate(self.qqq)
        
        # Reset position state
        self.is_holding = False
        self.entry_price = 0.0
        self.entry_time = None
        self.entry_quantity = 0
        self.entry_rsi = 0.0
        self.days_held = 0
        
        # SQL logging — log completed round-trip trade
        if self.db:
            try:
                self.db.log_trade(
                    symbol="QQQ",
                    side="BUY",
                    quantity=trade_record.quantity,
                    entry_price=trade_record.entry_price,
                    exit_price=price,
                    entry_time=trade_record.entry_time,
                    exit_time=timestamp,
                    entry_reason=f"rsi_entry_{trade_record.entry_rsi:.0f}",
                    exit_reason=exit_reason,
                )
            except Exception as e:
                self.Debug(f"[SQL] Trade log error: {e}")
    
    # =========================================================
    # END OF ALGORITHM
    # =========================================================
    
    def OnEndOfAlgorithm(self) -> None:
        """Final summary and SQL close."""
        
        # Close any open position — record it but don't place an order
        # (Liquidate at 16:00 causes MarketOnOpen error)
        if self.is_holding and self.last_qqq_close > 0:
            # Record the trade in our history for stats
            pnl = (self.last_qqq_close - self.entry_price) * self.entry_quantity
            pnl_pct = (self.last_qqq_close - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
            if pnl > 0:
                self.total_wins += 1
                self.gross_profit += pnl
            else:
                self.total_losses += 1
                self.gross_loss += abs(pnl)
            trade_record = SwingTradeRecord(
                symbol="QQQ", entry_time=self.entry_time, exit_time=self.Time,
                entry_price=self.entry_price, exit_price=self.last_qqq_close,
                quantity=self.entry_quantity, pnl=pnl, pnl_pct=pnl_pct,
                hold_days=self.days_held, entry_rsi=self.entry_rsi,
                exit_rsi=self.rsi_value, exit_reason="end_of_algo"
            )
            self.trade_history.append(trade_record)
            self.is_holding = False
        
        # Summary stats
        total_trades = len(self.trade_history)
        wins = self.total_wins
        losses = self.total_losses
        win_rate = wins / total_trades if total_trades > 0 else 0
        profit_factor = self.gross_profit / self.gross_loss if self.gross_loss > 0 else float('inf')
        
        avg_win = self.gross_profit / wins if wins > 0 else 0
        avg_loss = self.gross_loss / losses if losses > 0 else 0
        
        # Average hold days
        if total_trades > 0:
            avg_hold = sum(t.hold_days for t in self.trade_history) / total_trades
        else:
            avg_hold = 0
        
        # Largest win/loss
        if self.trade_history:
            largest_win = max(t.pnl for t in self.trade_history)
            largest_loss = min(t.pnl for t in self.trade_history)
        else:
            largest_win = 0
            largest_loss = 0
        
        self.Log(f"\n{'='*60}")
        self.Log(f"QQQ MEAN REVERSION SUMMARY")
        self.Log(f"{'='*60}")
        self.Log(f"Total Trades:   {total_trades}")
        self.Log(f"Wins:           {wins} ({win_rate:.1%})")
        self.Log(f"Losses:         {losses}")
        self.Log(f"Gross Profit:   ${self.gross_profit:,.2f}")
        self.Log(f"Gross Loss:     ${self.gross_loss:,.2f}")
        self.Log(f"Profit Factor:  {profit_factor:.2f}")
        self.Log(f"Avg Win:        ${avg_win:,.2f}")
        self.Log(f"Avg Loss:       ${avg_loss:,.2f}")
        self.Log(f"Largest Win:    ${largest_win:,.2f}")
        self.Log(f"Largest Loss:   ${largest_loss:,.2f}")
        self.Log(f"Avg Hold Days:  {avg_hold:.1f}")
        self.Log(f"{'='*60}")
        
        # SQL session close
        if self.db:
            try:
                final_equity = self.Portfolio.TotalPortfolioValue
                total_return = (final_equity - self.initial_cash) / self.initial_cash
                
                self.db.end_session(
                    total_return=round(total_return, 4),
                    total_trades=total_trades,
                    win_rate=round(win_rate, 4),
                    sharpe_ratio=0.0,
                    max_drawdown=0.0,
                )
            except Exception as e:
                self.Debug(f"[SQL] Session close error: {e}")
