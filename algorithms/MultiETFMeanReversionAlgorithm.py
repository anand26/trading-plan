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
Multi-ETF RSI(2) Mean Reversion Swing Trading Strategy
=========================================================
Strategy: Buy ETFs on oversold RSI bounces within confirmed uptrends.
Concept:  Larry Connors' RSI(2) strategy applied across a basket of
          uncorrelated index ETFs: QQQ, SPY, IWM, DIA.

Core Rules (applied INDEPENDENTLY per symbol):
  1. TREND FILTER: Symbol must be above its SMA(200) to take long trades
  2. ENTRY: Buy when RSI(2) drops below rsi_entry threshold
  3. EXIT:  Sell when RSI(2) rises above rsi_exit threshold
  4. SAFETY: Force exit if trend filter breaks (price drops below SMA)
  5. SIZING: Each position gets (allocation / max_positions) of portfolio

Why Multi-Instrument:
  - QQQ alone generates ~8 trades/year — too few for 50% capital allocation
  - Adding SPY, IWM, DIA provides 3-4x trade frequency (~25-35 trades/year)
  - These ETFs are correlated but NOT identical — different dip timings
  - More trades = more statistically significant results
  - Capital is deployed more of the time (less idle cash)

Parameters:
  - symbols:          Comma-separated list of symbols (default QQQ,SPY,IWM,DIA)
  - rsi-period:       RSI calculation period (default 2)
  - rsi-entry:        Buy when RSI drops below this (default 15)
  - rsi-exit:         Sell when RSI rises above this (default 90)
  - trend-sma:        SMA period for trend filter (default 200)
  - use-trend-filter: Whether to require price > SMA (default true)
  - allocation:       Total portfolio allocation for ALL positions (default 0.90)
  - max-hold-days:    Force exit after N days, 0=unlimited (default 0)

Author: Trading Plan Implementation
Version: 2.0.0 (Multi-ETF Mean Reversion)
"""


class TrendState(Enum):
    """Market trend classification for trade filtering"""
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    UNKNOWN = "unknown"


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


@dataclass
class SymbolState:
    """Per-symbol indicator state and position tracking"""
    symbol_obj: object           # LEAN Symbol object
    ticker: str                  # e.g. "QQQ"
    
    # Indicator state
    closes: deque                # Price history for SMA
    rsi_avg_gain: float = 0.0
    rsi_avg_loss: float = 0.0
    rsi_value: float = 50.0
    rsi_initialized: bool = False
    rsi_init_gains: list = None
    rsi_init_losses: list = None
    trend_sma_value: float = 0.0
    current_trend: TrendState = TrendState.UNKNOWN
    last_close: float = 0.0
    
    # Position state
    is_holding: bool = False
    entry_price: float = 0.0
    entry_time: Optional[datetime] = None
    entry_quantity: int = 0
    entry_rsi: float = 0.0
    hold_start_date: Optional[datetime] = None
    days_held: int = 0
    
    # Pending action
    pending_action: Optional[str] = None  # "BUY", "SELL", None
    last_action_date: Optional[datetime] = None
    
    def __post_init__(self):
        if self.rsi_init_gains is None:
            self.rsi_init_gains = []
        if self.rsi_init_losses is None:
            self.rsi_init_losses = []


class MultiETFMeanReversionAlgorithm(QCAlgorithm):
    """
    RSI(2) Mean Reversion Swing Trading across multiple ETFs.
    
    Independently tracks RSI(2) and SMA(200) for each symbol.
    Can hold multiple positions simultaneously.
    Equal allocation per position up to max_positions.
    """
    
    def Initialize(self):  # type: ignore
        """Initialize algorithm settings, securities, and indicators"""
        
        # =====================================================
        # BASIC SETTINGS
        # =====================================================
        start_date_str = str(self.GetParameter("start-date") or "2000-06-01")
        end_date_str = str(self.GetParameter("end-date") or "2026-02-05")
        
        try:
            start_parts = start_date_str.split("-")
            self.SetStartDate(int(start_parts[0]), int(start_parts[1]), int(start_parts[2]))
        except Exception:
            self.SetStartDate(2000, 6, 1)
        
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
        # SYMBOLS — Configurable basket
        # =====================================================
        symbols_str = str(self.GetParameter("symbols") or "QQQ,SPY,IWM,DIA")
        self.symbol_tickers = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
        
        # =====================================================
        # RSI MEAN REVERSION PARAMETERS
        # =====================================================
        self.rsi_period = int(float(self.GetParameter("rsi-period") or 2))
        self.rsi_entry = float(self.GetParameter("rsi-entry") or 15)
        self.rsi_exit = float(self.GetParameter("rsi-exit") or 90)
        
        # Trend filter
        self.trend_sma_period = int(float(self.GetParameter("trend-sma") or 200))
        self.use_trend_filter = str(self.GetParameter("use-trend-filter") or "true").lower() == "true"
        
        # Position sizing — total allocation shared across all positions
        self.allocation = float(self.GetParameter("allocation") or 0.90)
        self.max_positions = len(self.symbol_tickers)
        self.per_position_alloc = self.allocation / self.max_positions
        
        # Max hold days (0 = unlimited)
        self.max_hold_days = int(float(self.GetParameter("max-hold-days") or 0))
        
        # End-of-day execution window
        self.eod_hour = 15
        self.eod_minute = 50  # Execute trades at 3:50 PM ET
        
        # Log parameters
        self.Log(f"[PARAMS] Symbols: {self.symbol_tickers}")
        self.Log(f"[PARAMS] RSI Period: {self.rsi_period}, Entry < {self.rsi_entry}, Exit > {self.rsi_exit}")
        self.Log(f"[PARAMS] Trend SMA: {self.trend_sma_period}, Use Filter: {self.use_trend_filter}")
        self.Log(f"[PARAMS] Total Allocation: {self.allocation:.0%}, Per Position: {self.per_position_alloc:.1%}")
        self.Log(f"[PARAMS] Max Positions: {self.max_positions}, Max Hold Days: {self.max_hold_days}")
        
        # =====================================================
        # ADD SECURITIES & CREATE PER-SYMBOL STATE
        # =====================================================
        max_lookback = self.trend_sma_period + 10
        self.sym_states: Dict[str, SymbolState] = {}
        
        for ticker in self.symbol_tickers:
            equity = self.AddEquity(ticker, Resolution.Minute)
            symbol_obj = equity.Symbol
            
            state = SymbolState(
                symbol_obj=symbol_obj,
                ticker=ticker,
                closes=deque(maxlen=max_lookback),
            )
            self.sym_states[ticker] = state
            
            # Create daily consolidator for this symbol
            consolidator = TradeBarConsolidator(timedelta(days=1))
            # Use a closure to capture the ticker for the callback
            consolidator.DataConsolidated += lambda sender, bar, t=ticker: self._on_daily_bar(t, bar)
            self.SubscriptionManager.AddConsolidator(symbol_obj, consolidator)
            
            self.Log(f"[INIT] Added {ticker} with daily consolidator")
        
        # =====================================================
        # TRADE HISTORY & PERFORMANCE
        # =====================================================
        self.trade_history: List[SwingTradeRecord] = []
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
                    strategy_id="MULTI_ETF_MEAN_REVERSION"
                )
                
                session_type = "BACKTEST" if not self.LiveMode else "LIVE"
                params_snapshot = {
                    "strategy": "MULTI_ETF_MEAN_REVERSION",
                    "symbols": self.symbol_tickers,
                    "rsi_period": self.rsi_period,
                    "rsi_entry": self.rsi_entry,
                    "rsi_exit": self.rsi_exit,
                    "trend_sma": self.trend_sma_period,
                    "use_trend_filter": self.use_trend_filter,
                    "allocation": self.allocation,
                    "per_position_alloc": self.per_position_alloc,
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
        
        self.Debug(f"MultiETFMeanReversionAlgorithm v2.0 Initialized — {len(self.symbol_tickers)} symbols")
    
    # =========================================================
    # DAILY BAR HANDLER — PER-SYMBOL RSI & TREND
    # =========================================================
    
    def _on_daily_bar(self, ticker: str, bar: TradeBar) -> None:
        """
        Handle completed daily bar for a specific symbol.
        Calculate RSI, SMA, determine trend, generate signals.
        """
        state = self.sym_states[ticker]
        close = float(bar.Close)
        state.closes.append(close)
        state.last_close = close
        
        # ---- Calculate SMA for trend filter ----
        if len(state.closes) >= self.trend_sma_period:
            closes_list = list(state.closes)
            state.trend_sma_value = sum(closes_list[-self.trend_sma_period:]) / self.trend_sma_period
        
        # ---- Calculate RSI (Wilder's smoothing) ----
        if len(state.closes) >= 2:
            prev_close = list(state.closes)[-2]
            change = close - prev_close
            gain = max(change, 0.0)
            loss = abs(min(change, 0.0))
            
            if not state.rsi_initialized:
                state.rsi_init_gains.append(gain)
                state.rsi_init_losses.append(loss)
                
                if len(state.rsi_init_gains) >= self.rsi_period:
                    state.rsi_avg_gain = sum(state.rsi_init_gains[-self.rsi_period:]) / self.rsi_period
                    state.rsi_avg_loss = sum(state.rsi_init_losses[-self.rsi_period:]) / self.rsi_period
                    state.rsi_initialized = True
                    
                    if state.rsi_avg_loss == 0:
                        state.rsi_value = 100.0
                    else:
                        rs = state.rsi_avg_gain / state.rsi_avg_loss
                        state.rsi_value = 100.0 - (100.0 / (1.0 + rs))
            else:
                state.rsi_avg_gain = (state.rsi_avg_gain * (self.rsi_period - 1) + gain) / self.rsi_period
                state.rsi_avg_loss = (state.rsi_avg_loss * (self.rsi_period - 1) + loss) / self.rsi_period
                
                if state.rsi_avg_loss == 0:
                    state.rsi_value = 100.0
                else:
                    rs = state.rsi_avg_gain / state.rsi_avg_loss
                    state.rsi_value = 100.0 - (100.0 / (1.0 + rs))
        
        # ---- Determine trend ----
        if state.trend_sma_value > 0:
            if close > state.trend_sma_value:
                state.current_trend = TrendState.UPTREND
            else:
                state.current_trend = TrendState.DOWNTREND
        
        # ---- Track holding days ----
        if state.is_holding:
            state.days_held += 1
        
        # ---- Skip if warming up ----
        if self.IsWarmingUp:
            return
        
        if not state.rsi_initialized:
            return
        
        # ---- Generate signal for this symbol ----
        self._generate_signal(state)
        
        self.Log(f"[DAILY] {ticker}={close:.2f} | RSI({self.rsi_period})={state.rsi_value:.1f} | "
                 f"SMA{self.trend_sma_period}={state.trend_sma_value:.2f} | "
                 f"Trend={state.current_trend.value} | Holding={state.is_holding} | "
                 f"Days={state.days_held} | Action={state.pending_action}")
    
    # =========================================================
    # SIGNAL GENERATION — PER SYMBOL
    # =========================================================
    
    def _generate_signal(self, state: SymbolState) -> None:
        """
        Generate buy/sell signal for a specific symbol.
        
        ENTRY: RSI < entry_threshold AND (price > SMA or no filter) AND room for new position
        EXIT:  RSI > exit_threshold OR trend break OR max hold exceeded
        """
        if state.is_holding:
            # === CHECK EXIT CONDITIONS ===
            
            # Exit 1: RSI overbought — primary exit
            if state.rsi_value > self.rsi_exit:
                state.pending_action = "SELL"
                self.Log(f"[SIGNAL] {state.ticker} RSI EXIT: RSI={state.rsi_value:.1f} > {self.rsi_exit}")
                return
            
            # Exit 2: Trend break — safety exit
            if self.use_trend_filter and state.current_trend == TrendState.DOWNTREND:
                state.pending_action = "SELL"
                self.Log(f"[SIGNAL] {state.ticker} TREND BREAK EXIT: {state.last_close:.2f} < SMA={state.trend_sma_value:.2f}")
                return
            
            # Exit 3: Max hold days exceeded
            if self.max_hold_days > 0 and state.days_held >= self.max_hold_days:
                state.pending_action = "SELL"
                self.Log(f"[SIGNAL] {state.ticker} MAX HOLD EXIT: {state.days_held} days >= {self.max_hold_days}")
                return
            
            # No exit signal — hold
            state.pending_action = None
        
        else:
            # === CHECK ENTRY CONDITIONS ===
            
            # Check if we have room for another position
            current_positions = sum(1 for s in self.sym_states.values() if s.is_holding)
            if current_positions >= self.max_positions:
                state.pending_action = None
                return
            
            # Trend filter must be satisfied (if enabled)
            if self.use_trend_filter and state.current_trend != TrendState.UPTREND:
                state.pending_action = None
                return
            
            # RSI oversold — entry signal
            if state.rsi_value < self.rsi_entry:
                state.pending_action = "BUY"
                self.Log(f"[SIGNAL] {state.ticker} RSI ENTRY: RSI={state.rsi_value:.1f} < {self.rsi_entry}")
                return
            
            # No entry signal
            state.pending_action = None
    
    # =========================================================
    # MINUTE BAR HANDLER — END-OF-DAY EXECUTION
    # =========================================================
    
    def OnData(self, data: Slice) -> None:
        """Process minute data — execute trades at 3:50 PM ET."""
        if self.IsWarmingUp:
            return
        
        current_time = self.Time
        
        # Only execute in the EOD window
        if current_time.hour != self.eod_hour or current_time.minute != self.eod_minute:
            return
        
        # Process each symbol's pending action
        for ticker, state in self.sym_states.items():
            if state.pending_action is None:
                continue
            
            # Don't execute twice on the same day for this symbol
            if state.last_action_date and state.last_action_date.date() == current_time.date():
                continue
            
            # Get current price
            if not data.ContainsKey(state.symbol_obj):
                continue
            
            price = float(data[state.symbol_obj].Close)
            
            if state.pending_action == "BUY":
                self._execute_buy(state, price, current_time)
            elif state.pending_action == "SELL":
                self._execute_sell(state, price, current_time)
            
            state.last_action_date = current_time
            state.pending_action = None
    
    # =========================================================
    # TRADE EXECUTION
    # =========================================================
    
    def _execute_buy(self, state: SymbolState, price: float, timestamp: datetime) -> None:
        """Buy a symbol at per-position allocation."""
        if state.is_holding:
            return
        
        target_value = self.Portfolio.TotalPortfolioValue * self.per_position_alloc
        quantity = int(target_value / price)
        
        if quantity <= 0:
            return
        
        self.SetHoldings(state.symbol_obj, self.per_position_alloc)
        
        state.is_holding = True
        state.entry_price = price
        state.entry_time = timestamp
        state.entry_quantity = quantity
        state.entry_rsi = state.rsi_value
        state.hold_start_date = timestamp
        state.days_held = 0
        
        current_positions = sum(1 for s in self.sym_states.values() if s.is_holding)
        self.Log(f"[BUY] {state.ticker} @ {price:.2f} | Qty≈{quantity} | RSI={state.rsi_value:.1f} | "
                 f"Alloc={self.per_position_alloc:.1%} | Positions={current_positions}/{self.max_positions}")
    
    def _execute_sell(self, state: SymbolState, price: float, timestamp: datetime) -> None:
        """Sell a symbol position — close swing trade."""
        if not state.is_holding:
            return
        
        # Determine exit reason
        exit_reason = "rsi_exit"
        if self.use_trend_filter and state.current_trend == TrendState.DOWNTREND:
            exit_reason = "trend_break"
        if self.max_hold_days > 0 and state.days_held >= self.max_hold_days:
            exit_reason = "max_hold"
        
        # Calculate PnL
        pnl = (price - state.entry_price) * state.entry_quantity
        pnl_pct = (price - state.entry_price) / state.entry_price if state.entry_price > 0 else 0
        
        # Track performance
        if pnl > 0:
            self.total_wins += 1
            self.gross_profit += pnl
        else:
            self.total_losses += 1
            self.gross_loss += abs(pnl)
        
        # Record trade
        trade_record = SwingTradeRecord(
            symbol=state.ticker,
            entry_time=state.entry_time,
            exit_time=timestamp,
            entry_price=state.entry_price,
            exit_price=price,
            quantity=state.entry_quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            hold_days=state.days_held,
            entry_rsi=state.entry_rsi,
            exit_rsi=state.rsi_value,
            exit_reason=exit_reason,
        )
        self.trade_history.append(trade_record)
        
        win_label = "WIN" if pnl > 0 else "LOSS"
        current_positions = sum(1 for s in self.sym_states.values() if s.is_holding) - 1  # -1 because this one is closing
        self.Log(f"[SELL] {state.ticker} @ {price:.2f} | {win_label} ${pnl:+,.2f} ({pnl_pct:+.2%}) | "
                 f"Held {state.days_held}d | RSI={state.rsi_value:.1f} | Reason={exit_reason} | "
                 f"Positions={current_positions}/{self.max_positions}")
        
        # Liquidate this symbol's position
        self.Liquidate(state.symbol_obj)
        
        # Reset position state
        state.is_holding = False
        state.entry_price = 0.0
        state.entry_time = None
        state.entry_quantity = 0
        state.entry_rsi = 0.0
        state.days_held = 0
        
        # SQL logging
        if self.db:
            try:
                self.db.log_trade(
                    symbol=state.ticker,
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
        
        # Close any open positions — record but don't place orders
        # (Liquidate at 16:00 causes MarketOnOpen error)
        for ticker, state in self.sym_states.items():
            if state.is_holding and state.last_close > 0:
                pnl = (state.last_close - state.entry_price) * state.entry_quantity
                pnl_pct = (state.last_close - state.entry_price) / state.entry_price if state.entry_price > 0 else 0
                if pnl > 0:
                    self.total_wins += 1
                    self.gross_profit += pnl
                else:
                    self.total_losses += 1
                    self.gross_loss += abs(pnl)
                trade_record = SwingTradeRecord(
                    symbol=ticker, entry_time=state.entry_time, exit_time=self.Time,
                    entry_price=state.entry_price, exit_price=state.last_close,
                    quantity=state.entry_quantity, pnl=pnl, pnl_pct=pnl_pct,
                    hold_days=state.days_held, entry_rsi=state.entry_rsi,
                    exit_rsi=state.rsi_value, exit_reason="end_of_algo"
                )
                self.trade_history.append(trade_record)
                state.is_holding = False
        
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
        
        # Per-symbol breakdown
        per_symbol_trades: Dict[str, int] = {}
        per_symbol_pnl: Dict[str, float] = {}
        for t in self.trade_history:
            per_symbol_trades[t.symbol] = per_symbol_trades.get(t.symbol, 0) + 1
            per_symbol_pnl[t.symbol] = per_symbol_pnl.get(t.symbol, 0.0) + t.pnl
        
        # Largest win/loss
        if self.trade_history:
            largest_win = max(t.pnl for t in self.trade_history)
            largest_loss = min(t.pnl for t in self.trade_history)
        else:
            largest_win = 0
            largest_loss = 0
        
        self.Log(f"\n{'='*60}")
        self.Log(f"MULTI-ETF MEAN REVERSION SUMMARY")
        self.Log(f"{'='*60}")
        self.Log(f"Symbols:        {self.symbol_tickers}")
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
        self.Log(f"--- Per Symbol ---")
        for sym in self.symbol_tickers:
            trades = per_symbol_trades.get(sym, 0)
            pnl = per_symbol_pnl.get(sym, 0.0)
            self.Log(f"  {sym:5s}: {trades:3d} trades, PnL ${pnl:+,.2f}")
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
