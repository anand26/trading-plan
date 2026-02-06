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


class TrendRegime(Enum):
    """Daily trend regime based on QQQ 50/200-day SMA"""
    UPTREND = "uptrend"        # QQQ above both 50 & 200 SMA → only TQQQ entries
    DOWNTREND = "downtrend"    # QQQ below both 50 & 200 SMA → only SQQQ entries
    NEUTRAL = "neutral"        # QQQ between the two SMAs → both directions allowed
    UNKNOWN = "unknown"        # Not enough data yet


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
        
        # =====================================================
        # TREND FILTER PARAMETERS (QQQ 50/200-day SMA)
        # =====================================================
        self.trend_filter_enabled = str(self.GetParameter("trend-filter-enabled") or self.GetParameter("trend_filter_enabled") or "true").lower() == "true"  # type: ignore
        self.sma_fast_period = int(float(self.GetParameter("sma-fast-period") or self.GetParameter("sma_fast_period") or 50))  # type: ignore
        self.sma_slow_period = int(float(self.GetParameter("sma-slow-period") or self.GetParameter("sma_slow_period") or 200))  # type: ignore
        self.current_trend = TrendRegime.UNKNOWN
        
        # =====================================================
        # DRAWDOWN CIRCUIT BREAKER PARAMETERS
        # =====================================================
        self.daily_loss_limit_pct = float(self.GetParameter("daily-loss-limit-pct") or self.GetParameter("daily_loss_limit_pct") or 0.02)  # type: ignore
        self.max_drawdown_pct = float(self.GetParameter("max-drawdown-pct") or self.GetParameter("max_drawdown_pct") or 0.25)  # type: ignore
        self.drawdown_position_scale = float(self.GetParameter("drawdown-position-scale") or self.GetParameter("drawdown_position_scale") or 0.50)  # type: ignore
        self.daily_halt = False
        self.daily_pnl = 0.0
        self.peak_equity = 0.0
        self.in_drawdown_mode = False
        
        # =====================================================
        # VOLATILITY SCALING PARAMETERS (configurable)
        # =====================================================
        self.enable_vol_scaling = str(self.GetParameter("enable-vol-scaling") or self.GetParameter("enable_vol_scaling") or "false").lower() == "true"  # type: ignore
        self.vol_scale_high_thresh = float(self.GetParameter("vol-scale-high-thresh") or self.GetParameter("vol_scale_high_thresh") or 30.0)  # type: ignore
        self.vol_scale_med_thresh = float(self.GetParameter("vol-scale-med-thresh") or self.GetParameter("vol_scale_med_thresh") or 20.0)  # type: ignore
        self.vol_scale_high_factor = float(self.GetParameter("vol-scale-high-factor") or self.GetParameter("vol_scale_high_factor") or 0.44)  # type: ignore  # 25% / 57% ≈ 0.44
        self.vol_scale_med_factor = float(self.GetParameter("vol-scale-med-factor") or self.GetParameter("vol_scale_med_factor") or 0.70)  # type: ignore  # 40% / 57% ≈ 0.70
        
        # Log parameters
        self.Log(f"[PARAMS] Z-score Lookback: {self.zscore_lookback} bars")  # type: ignore
        self.Log(f"[PARAMS] Entry Z-score: ±{self.entry_zscore}, Exit Z-score: ±{self.exit_zscore}")  # type: ignore
        self.Log(f"[PARAMS] Stop Z-score: ±{self.stop_zscore}, Stop Loss: {self.stop_loss_pct:.1%}")  # type: ignore
        self.Log(f"[PARAMS] Position Size: {self.position_size:.0%}")  # type: ignore
        self.Log(f"[PARAMS] Trend Filter: {'ON' if self.trend_filter_enabled else 'OFF'} (SMA {self.sma_fast_period}/{self.sma_slow_period})")  # type: ignore
        self.Log(f"[PARAMS] Daily Loss Limit: {self.daily_loss_limit_pct:.1%}, Max Drawdown: {self.max_drawdown_pct:.0%}")  # type: ignore
        self.Log(f"[PARAMS] Vol Scaling: {'ON' if self.enable_vol_scaling else 'OFF'}")  # type: ignore
        
        # =====================================================
        # ADD SECURITIES (Raw normalization - Databento data is unadjusted)
        # =====================================================
        tqqq_security = self.AddEquity("TQQQ", Resolution.Minute)
        tqqq_security.SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.tqqq = tqqq_security.Symbol
        
        sqqq_security = self.AddEquity("SQQQ", Resolution.Minute)
        sqqq_security.SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.sqqq = sqqq_security.Symbol
        
        # =====================================================
        # QQQ for TREND FILTER + VOL SCALING (minute data → daily consolidator)
        # =====================================================
        if self.trend_filter_enabled or self.enable_vol_scaling:
            qqq_security = self.AddEquity("QQQ", Resolution.Minute)
            qqq_security.SetDataNormalizationMode(DataNormalizationMode.Raw)
            self.qqq = qqq_security.Symbol
            
            # Daily consolidator: aggregates minute bars → daily bars
            self.qqq_daily_consolidator = TradeBarConsolidator(timedelta(days=1))
            self.qqq_daily_consolidator.DataConsolidated += self.OnQQQDailyBarConsolidated
            self.SubscriptionManager.AddConsolidator(self.qqq, self.qqq_daily_consolidator)
            
            # Manual rolling SMAs (deque-based, fed by daily consolidator)
            self.qqq_daily_closes: deque = deque(maxlen=self.sma_slow_period)  # sized to the larger SMA
            self.qqq_sma_fast_value: float = 0.0
            self.qqq_sma_slow_value: float = 0.0
            self.qqq_sma_ready: bool = False
            
            # Manual ATR tracking for vol scaling (20-day)
            self.qqq_daily_highs: deque = deque(maxlen=20)
            self.qqq_daily_lows: deque = deque(maxlen=20)
            self.qqq_daily_prev_close: float = 0.0
            self.qqq_atr_value: float = 0.0
            self.qqq_atr_ready: bool = False
            
            self.Log(f"[INIT] QQQ subscribed at Minute resolution, consolidating to Daily")
            self.Log(f"[INIT] Trend filter: SMA({self.sma_fast_period}) / SMA({self.sma_slow_period})")
        else:
            self.qqq = None
            self.qqq_daily_closes = deque()
            self.qqq_sma_ready = False
            self.qqq_atr_ready = False
        
        # =====================================================
        # CONSOLIDATORS (5-minute bars for TQQQ/SQQQ)
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
        # WARMUP (need 200+ days for SMA200 if trend filter is on)
        # =====================================================
        default_warmup = 210 if self.trend_filter_enabled else 0
        warmup_days = int(self.GetParameter("warmup-days") or str(default_warmup))
        self.SetWarmUp(timedelta(days=warmup_days))
        
        # Initialize peak equity tracking
        self.peak_equity = float(initial_cash)
        
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
            trend_str = self.current_trend.value if hasattr(self, 'current_trend') else 'n/a'
            dd_str = ' [HALTED]' if self.daily_halt else (' [DD-MODE]' if self.in_drawdown_mode else '')
            self.Debug(f"{self.Time} Ratio: {ratio:.4f}, Z-score: {zscore:.2f}, State: {self.position_state.value}, Trend: {trend_str}{dd_str}")
        
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
        """Calculate Z-score of current ratio vs historical mean.
        Uses population stdev (pstdev) to match TradingView Pine Script ta.stdev()."""
        if len(self.ratio_history) < 2:
            return 0.0
        
        ratios = list(self.ratio_history)
        mean = statistics.mean(ratios)
        stdev = statistics.pstdev(ratios)  # Population stdev to match Pine Script ta.stdev()
        
        if stdev == 0:
            return 0.0
        
        current_ratio = ratios[-1]
        return (current_ratio - mean) / stdev
    
    # =========================================================
    # ENTRY LOGIC
    # =========================================================
    
    def UpdateTrendRegime(self) -> None:
        """Update trend regime from QQQ daily SMAs.
        Uptrend: QQQ > SMA50 AND QQQ > SMA200 → only TQQQ entries
        Downtrend: QQQ < SMA50 AND QQQ < SMA200 → only SQQQ entries
        Neutral: between the two → both directions allowed
        """
        if not self.trend_filter_enabled or self.qqq_sma_fast is None or self.qqq_sma_slow is None:
            self.current_trend = TrendRegime.NEUTRAL
            return
        
        if not self.qqq_sma_fast.IsReady or not self.qqq_sma_slow.IsReady:
            self.current_trend = TrendRegime.UNKNOWN
            return
        
        qqq_price = self.Securities[self.qqq].Price
        sma_fast = self.qqq_sma_fast.Current.Value
        sma_slow = self.qqq_sma_slow.Current.Value
        
        if qqq_price > sma_fast and qqq_price > sma_slow:
            self.current_trend = TrendRegime.UPTREND
        elif qqq_price < sma_fast and qqq_price < sma_slow:
            self.current_trend = TrendRegime.DOWNTREND
        else:
            self.current_trend = TrendRegime.NEUTRAL
    
    def GetEffectivePositionSize(self) -> float:
        """Get position size adjusted for drawdown mode and volatility scaling."""
        size = self.position_size
        
        # Drawdown mode: reduce position size
        if self.in_drawdown_mode:
            size *= self.drawdown_position_scale
            self.Log(f"[RISK] Drawdown mode active, position size reduced to {size:.0%}")
        
        # Volatility scaling (optional, configurable)
        if self.enable_vol_scaling and self.qqq_atr is not None and self.qqq_atr.IsReady:
            qqq_price = self.Securities[self.qqq].Price
            if qqq_price > 0:
                # ATR as % of price = realized volatility proxy
                atr_pct = (self.qqq_atr.Current.Value / qqq_price) * 100
                # Scale: >30% vol → high factor, >20% → med factor, else full
                if atr_pct > self.vol_scale_high_thresh:
                    size *= self.vol_scale_high_factor
                    self.Log(f"[VOL] High vol ({atr_pct:.1f}%), position scaled to {size:.0%}")
                elif atr_pct > self.vol_scale_med_thresh:
                    size *= self.vol_scale_med_factor
                    self.Log(f"[VOL] Med vol ({atr_pct:.1f}%), position scaled to {size:.0%}")
        
        return size
    
    def ProcessEntrySignals(self, zscore: float) -> None:
        """Check for entry signals based on Z-score, gated by trend filter and risk controls"""
        
        # Check trade limits
        if self.daily_trades_count >= self.max_daily_trades:
            return
        
        # Minimum bars between trades
        if self.bars_since_trade < self.min_bars_between_trades:
            return
        
        # Daily drawdown circuit breaker
        if self.daily_halt:
            return
        
        # Update trend regime from daily QQQ SMAs
        self.UpdateTrendRegime()
        
        # Don't trade if trend is unknown (indicators not ready)
        if self.current_trend == TrendRegime.UNKNOWN:
            return
        
        # Z-score LOW (negative) → TQQQ is cheap → Buy TQQQ
        # Only allowed in UPTREND or NEUTRAL regime
        if zscore < -self.entry_zscore:
            if self.current_trend in (TrendRegime.UPTREND, TrendRegime.NEUTRAL):
                self.EnterPosition(self.tqqq, "TQQQ", zscore)
            else:
                if self.Time.minute == 0:  # Log hourly to avoid spam
                    self.Debug(f"{self.Time} [TREND] Blocked TQQQ entry (Z={zscore:.2f}) - regime is {self.current_trend.value}")
        
        # Z-score HIGH (positive) → SQQQ is cheap → Buy SQQQ
        # Only allowed in DOWNTREND or NEUTRAL regime
        elif zscore > self.entry_zscore:
            if self.current_trend in (TrendRegime.DOWNTREND, TrendRegime.NEUTRAL):
                self.EnterPosition(self.sqqq, "SQQQ", zscore)
            else:
                if self.Time.minute == 0:
                    self.Debug(f"{self.Time} [TREND] Blocked SQQQ entry (Z={zscore:.2f}) - regime is {self.current_trend.value}")
    
    def EnterPosition(self, symbol, symbol_name: str, zscore: float) -> None:
        """Enter a long position with dynamic position sizing"""
        effective_size = self.GetEffectivePositionSize()
        self.SetHoldings(symbol, effective_size, liquidateExistingHoldings=True, tag=f"{symbol_name} Entry: Z={zscore:.2f} Regime={self.current_trend.value}")  # type: ignore
        
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
        """Exit current position and update risk tracking"""
        current_price = self.Securities[symbol].Price
        quantity = self.Portfolio[symbol].Quantity
        
        self.Liquidate(symbol, tag=f"{symbol_name} Exit: {reason}")
        
        # Record trade
        if self.entry_time:
            hold_minutes = int((self.Time - self.entry_time).total_seconds() / 60)
            pnl = (current_price - self.entry_price) * quantity
            
            # === DRAWDOWN CIRCUIT BREAKER: track daily P&L ===
            self.daily_pnl += pnl
            nav = self.Portfolio.TotalPortfolioValue
            daily_loss_pct = -self.daily_pnl / nav if nav > 0 and self.daily_pnl < 0 else 0
            if daily_loss_pct > self.daily_loss_limit_pct:
                self.daily_halt = True
                self.Log(f"[RISK] DAILY HALT: Daily loss {daily_loss_pct:.2%} exceeds {self.daily_loss_limit_pct:.1%} limit. No more trades today.")
            
            # === EQUITY DRAWDOWN TRACKING ===
            if nav > self.peak_equity:
                self.peak_equity = nav
                if self.in_drawdown_mode:
                    self.in_drawdown_mode = False
                    self.Log(f"[RISK] New equity high ${nav:,.0f} - exiting drawdown mode")
            elif self.peak_equity > 0:
                drawdown = (self.peak_equity - nav) / self.peak_equity
                if drawdown > self.max_drawdown_pct and not self.in_drawdown_mode:
                    self.in_drawdown_mode = True
                    self.Log(f"[RISK] DRAWDOWN MODE: {drawdown:.1%} from peak ${self.peak_equity:,.0f}. Position size reduced by {(1-self.drawdown_position_scale):.0%}")
            
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
        
        # SQL logging - log completed trade with entry and exit info
        if self.db and self.entry_time:
            self.db.log_trade(
                symbol=symbol_name,
                side="BUY",  # We always go long
                quantity=quantity,
                entry_price=self.entry_price,
                exit_price=current_price,
                entry_time=self.entry_time,
                exit_time=self.Time,
                entry_reason=f"Z-score entry: {self.entry_zscore:.2f}",
                exit_reason=reason
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
        self.daily_halt = False
        self.daily_pnl = 0.0
        
        # Update peak equity at start of day
        nav = self.Portfolio.TotalPortfolioValue
        if nav > self.peak_equity:
            self.peak_equity = nav
        
        # Log trend regime for the day
        self.UpdateTrendRegime()
        trend_str = self.current_trend.value
        dd_pct = ((self.peak_equity - nav) / self.peak_equity * 100) if self.peak_equity > 0 else 0
        self.Log(f"[NEW DAY] Reset. NAV: ${nav:,.0f}, Peak: ${self.peak_equity:,.0f}, DD: {dd_pct:.1f}%, Trend: {trend_str}, DD-Mode: {self.in_drawdown_mode}")
    
    def OnEndOfAlgorithm(self) -> None:
        """Log summary at end of backtest"""
        if not self.trade_history:
            self.Log("[SUMMARY] No trades executed")
            return
        
        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t.pnl > 0)
        total_pnl = sum(t.pnl for t in self.trade_history)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        total_return = (self.Portfolio.TotalPortfolioValue - 100000) / 100000
        
        self.Log(f"[SUMMARY] Total Trades: {total_trades}")
        self.Log(f"[SUMMARY] Winning: {winning_trades}, Losing: {total_trades - winning_trades}")
        self.Log(f"[SUMMARY] Win Rate: {win_rate:.1%}")
        self.Log(f"[SUMMARY] Total P&L: ${total_pnl:.2f}")
        self.Log(f"[SUMMARY] Peak Equity: ${self.peak_equity:,.0f}, Final: ${self.Portfolio.TotalPortfolioValue:,.0f}")
        if self.trend_filter_enabled:
            self.Log(f"[SUMMARY] Trend Filter: ON (SMA {self.sma_fast_period}/{self.sma_slow_period})")
        
        # SQL session end
        if self.db:
            self.db.end_session(
                total_return=total_return,
                total_trades=total_trades,
                win_rate=win_rate
            )
