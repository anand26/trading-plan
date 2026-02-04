# region imports
from AlgorithmImports import *  # type: ignore
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# SQL Persistence for Trade-Mind MCP integration
try:
    from sql_connector import TradingDBConnector, create_connector  # type: ignore
    HAS_SQL_CONNECTOR = True
except ImportError:
    HAS_SQL_CONNECTOR = False

# Webhook Simulation for backtest validation
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backtest'))
try:
    from webhook_simulator import WebhookSimulator, WebhookType  # type: ignore
    HAS_WEBHOOK_SIMULATOR = True
except ImportError:
    HAS_WEBHOOK_SIMULATOR = False
    WebhookSimulator = None  # type: ignore
# endregion

"""
TQQQ/SQQQ Momentum Scalping Algorithm
=====================================
Strategy: Momentum Breakout with QQQ Trend Filter
- Entry: Price breaks above N-bar high (TQQQ) or below N-bar low (SQQQ)
- Confirmation: RSI > 50 (momentum), Volume spike
- Exit: Trailing stop or fixed stop loss

Position Sizing: Single entry (no pyramiding for momentum)
Trading Hours: Intraday only (close by 3:50 PM EST)
Direction: TQQQ on QQQ uptrend, SQQQ on QQQ downtrend

Author: Trading Plan Implementation
Version: 2.0.0 - Momentum Strategy
"""


class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    MEAN_REVERTING = "mean_reverting"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class PositionEntry:
    """Represents a single entry in a pyramided position"""
    price: float
    quantity: float
    timestamp: datetime
    level: int  # 1, 2, or 3


@dataclass 
class PositionTracker:
    """
    Track multi-level pyramid entries for a symbol.
    Supports up to 3 pyramid levels: 50%, 30%, 20% of capital.
    """
    entries: List[PositionEntry] = field(default_factory=list)
    symbol: str = ""
    direction: str = ""  # "LONG" or "SHORT"
    
    @property
    def num_entries(self) -> int:
        return len(self.entries)
    
    @property
    def total_quantity(self) -> float:
        return sum(e.quantity for e in self.entries)
    
    @property
    def average_price(self) -> float:
        if not self.entries:
            return 0.0
        total_cost = sum(e.price * e.quantity for e in self.entries)
        return total_cost / self.total_quantity if self.total_quantity > 0 else 0.0
    
    def add_entry(self, price: float, quantity: float, timestamp: datetime) -> None:
        """Add a new pyramid entry"""
        level = self.num_entries + 1
        self.entries.append(PositionEntry(
            price=price,
            quantity=quantity,
            timestamp=timestamp,
            level=level
        ))
    
    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L based on current price"""
        if not self.entries:
            return 0.0
        if self.direction == "LONG":
            return (current_price - self.average_price) * self.total_quantity
        else:  # SHORT
            return (self.average_price - current_price) * self.total_quantity
    
    def calculate_profit_percent(self, current_price: float) -> float:
        """Calculate profit/loss as percentage of average entry"""
        if not self.entries or self.average_price == 0:
            return 0.0
        if self.direction == "LONG":
            return (current_price - self.average_price) / self.average_price
        else:  # SHORT
            return (self.average_price - current_price) / self.average_price
    
    def reset(self) -> None:
        """Clear all entries after position is closed"""
        self.entries = []
        self.direction = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/persistence"""
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "num_entries": self.num_entries,
            "total_quantity": self.total_quantity,
            "average_price": self.average_price,
            "entries": [
                {
                    "level": e.level,
                    "price": e.price,
                    "quantity": e.quantity,
                    "timestamp": str(e.timestamp)
                }
                for e in self.entries
            ]
        }


class TQQQScalpingAlgorithm(QCAlgorithm):
    """
    TQQQ/SQQQ Momentum Scalping Strategy (v2.0)
    
    Entry Conditions (TQQQ - Long QQQ Uptrend):
    - QQQ EMA(fast) > EMA(slow) (uptrend confirmed)
    - Price breaks above N-bar high (momentum breakout)
    - RSI > 50 (momentum confirmation, NOT oversold)
    - Volume > 1.2x average (optional)
    
    Entry Conditions (SQQQ - Short QQQ Downtrend):
    - QQQ EMA(fast) < EMA(slow) (downtrend confirmed)
    - Price breaks below N-bar low (momentum breakout)
    - RSI < 50 (momentum confirmation)
    - Volume > 1.2x average (optional)
    
    Position Sizing:
    - Single entry at configured position size (no pyramiding)
    - Clean momentum entries, ride the trend
    
    Exit Conditions:
    - Trailing Stop: Lock in profits as price moves favorably
    - Fixed Stop Loss: Maximum loss per trade
    - Time Stop: Close all positions at 3:50 PM EST
    """
    
    def Initialize(self):  # type: ignore
        """Initialize algorithm settings, securities, and indicators"""
        
        # =====================================================
        # BASIC SETTINGS
        # =====================================================
        # Read dates from parameters, default to 2026 YTD (matching our data)
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
        
        # Read cash from parameters
        initial_cash = float(self.GetParameter("cash") or 100000)  # type: ignore
        self.SetCash(initial_cash)  # type: ignore
        
        # Set Alpaca as brokerage for live trading
        self.SetBrokerageModel(BrokerageName.Alpaca, AccountType.Margin)  # type: ignore
        
        # =====================================================
        # STRATEGY PARAMETERS (can be overridden via GetParameter)
        # =====================================================
        # Helper to safely parse int from string (handles "14.0" -> 14)
        def safe_int(val, default):
            if val is None:
                return default
            try:
                return int(float(val))  # Convert through float to handle "14.0"
            except (ValueError, TypeError):
                return default
        
        # RSI Parameters (for momentum confirmation)
        self.rsi_period = safe_int(self.GetParameter("rsi-period") or self.GetParameter("rsi_period"), 14)  # type: ignore
        self.rsi_momentum_min = float(self.GetParameter("rsi-momentum-min") or self.GetParameter("rsi_momentum_min") or 50)  # type: ignore  # RSI must be above this for TQQQ
        self.rsi_momentum_max = float(self.GetParameter("rsi-momentum-max") or self.GetParameter("rsi_momentum_max") or 50)  # type: ignore  # RSI must be below this for SQQQ
        self.rsi_exit_overbought = float(self.GetParameter("rsi-exit-overbought") or self.GetParameter("rsi_exit_overbought") or 75)  # type: ignore  # Exit when too extended
        self.rsi_exit_oversold = float(self.GetParameter("rsi-exit-oversold") or self.GetParameter("rsi_exit_oversold") or 25)  # type: ignore
        
        # Breakout Parameters (NEW for momentum strategy)
        self.breakout_bars = safe_int(self.GetParameter("breakout-bars") or self.GetParameter("breakout_bars"), 3)  # type: ignore  # N-bar high/low
        self.require_volume_spike = str(self.GetParameter("require-volume-spike") or self.GetParameter("require_volume_spike") or "false").lower() == "true"  # type: ignore
        
        # Bollinger Bands Parameters
        self.bb_period = safe_int(self.GetParameter("bb-period") or self.GetParameter("bb_period"), 20)  # type: ignore
        self.bb_std_dev = float(self.GetParameter("bb-std-dev") or self.GetParameter("bb_std_dev") or 2.0)  # type: ignore
        
        # EMA Parameters (for QQQ trend filter)
        self.ema_fast_period = safe_int(self.GetParameter("ema-fast-period") or self.GetParameter("ema_fast_period"), 9)  # type: ignore
        self.ema_slow_period = safe_int(self.GetParameter("ema-slow-period") or self.GetParameter("ema_slow_period"), 21)  # type: ignore
        
        # Risk Management Parameters
        self.stop_loss_pct = float(self.GetParameter("stop-loss-pct") or self.GetParameter("stop_loss_pct") or 0.02)  # type: ignore  # 2%
        self.take_profit_pct = float(self.GetParameter("take-profit-pct") or self.GetParameter("take_profit_pct") or 0.03)  # type: ignore  # 3% take profit target
        self.take_profit_rsi_reversal = float(self.GetParameter("take-profit-rsi") or self.GetParameter("take_profit_rsi") or 0.01)  # type: ignore  # 1% above VWAP
        
        # Trailing Stop Parameters (NEW - for letting winners run)
        self.trailing_stop_pct = float(self.GetParameter("trailing-stop-pct") or self.GetParameter("trailing_stop_pct") or 0.0)  # type: ignore  # 0 = disabled, 0.02 = 2% trailing
        self.use_trailing_stop = self.trailing_stop_pct > 0
        
        # Position Sizing (single entry for momentum strategy)
        self.position_size = float(self.GetParameter("position-size") or self.GetParameter("position_size") or 0.60)  # type: ignore  # 60% of capital
        # Keep legacy params for compatibility but not used in momentum strategy
        self.position_size_level1 = self.position_size
        self.position_size_level2 = 0.0
        self.position_size_level3 = 0.0
        self.pyramid_level2_profit_threshold = 0.0
        
        # Volume filter
        self.volume_spike_multiplier = float(self.GetParameter("volume-spike-mult") or self.GetParameter("volume_spike_mult") or 1.5)  # type: ignore
        
        # Log parameter values for debugging
        self.Log(f"[PARAMS] Strategy: MOMENTUM v2.0")  # type: ignore
        self.Log(f"[PARAMS] Breakout Bars: {self.breakout_bars}, RSI Momentum Min: {self.rsi_momentum_min}")  # type: ignore
        self.Log(f"[PARAMS] Stop Loss: {self.stop_loss_pct}, Take Profit: {self.take_profit_pct}")  # type: ignore
        self.Log(f"[PARAMS] RSI Period: {self.rsi_period}, EMA Fast: {self.ema_fast_period}, EMA Slow: {self.ema_slow_period}")  # type: ignore
        self.Log(f"[PARAMS] Position Size: {self.position_size}")  # type: ignore
        self.Log(f"[PARAMS] Trailing Stop: {self.trailing_stop_pct} (enabled={self.use_trailing_stop})")  # type: ignore
        
        # =====================================================
        # TRAILING STOP RISK MANAGEMENT (if enabled)
        # =====================================================
        if self.use_trailing_stop:
            from Risk.TrailingStopRiskManagementModel import TrailingStopRiskManagementModel
            self.SetRiskManagement(TrailingStopRiskManagementModel(self.trailing_stop_pct))  # type: ignore
            self.Log(f"[RISK] Trailing Stop Risk Management enabled at {self.trailing_stop_pct*100:.1f}%")  # type: ignore
        
        # Consolidation to 5-minute bars
        self.bar_period = timedelta(minutes=5)
        
        # =====================================================
        # ADD SECURITIES
        # =====================================================
        # Main trading instruments
        self.tqqq = self.AddEquity("TQQQ", Resolution.Minute).Symbol
        self.sqqq = self.AddEquity("SQQQ", Resolution.Minute).Symbol
        
        # Trend filter instrument
        self.qqq = self.AddEquity("QQQ", Resolution.Minute).Symbol
        
        # =====================================================
        # CONSOLIDATORS (5-minute bars)
        # =====================================================
        # TQQQ consolidator
        self.tqqq_consolidator = TradeBarConsolidator(self.bar_period)
        self.tqqq_consolidator.DataConsolidated += self.OnTQQQBarConsolidated
        self.SubscriptionManager.AddConsolidator(self.tqqq, self.tqqq_consolidator)
        
        # SQQQ consolidator
        self.sqqq_consolidator = TradeBarConsolidator(self.bar_period)
        self.sqqq_consolidator.DataConsolidated += self.OnSQQQBarConsolidated
        self.SubscriptionManager.AddConsolidator(self.sqqq, self.sqqq_consolidator)
        
        # QQQ consolidator (for trend filter)
        self.qqq_consolidator = TradeBarConsolidator(self.bar_period)
        self.qqq_consolidator.DataConsolidated += self.OnQQQBarConsolidated
        self.SubscriptionManager.AddConsolidator(self.qqq, self.qqq_consolidator)
        
        # =====================================================
        # INDICATORS - TQQQ
        # =====================================================
        self.tqqq_rsi = RelativeStrengthIndex(self.rsi_period, MovingAverageType.Wilders)
        self.tqqq_bb = BollingerBands(self.bb_period, self.bb_std_dev, MovingAverageType.Simple)
        self.tqqq_vwap = IntradayVwap()
        self.tqqq_volume_sma = SimpleMovingAverage(20)  # 20-bar volume average
        
        # Register indicators with consolidator
        self.RegisterIndicator(self.tqqq, self.tqqq_rsi, self.tqqq_consolidator)
        self.RegisterIndicator(self.tqqq, self.tqqq_bb, self.tqqq_consolidator)
        self.RegisterIndicator(self.tqqq, self.tqqq_vwap, self.tqqq_consolidator)
        
        # =====================================================
        # INDICATORS - SQQQ
        # =====================================================
        self.sqqq_rsi = RelativeStrengthIndex(self.rsi_period, MovingAverageType.Wilders)
        self.sqqq_bb = BollingerBands(self.bb_period, self.bb_std_dev, MovingAverageType.Simple)
        self.sqqq_vwap = IntradayVwap()
        self.sqqq_volume_sma = SimpleMovingAverage(20)
        
        self.RegisterIndicator(self.sqqq, self.sqqq_rsi, self.sqqq_consolidator)
        self.RegisterIndicator(self.sqqq, self.sqqq_bb, self.sqqq_consolidator)
        self.RegisterIndicator(self.sqqq, self.sqqq_vwap, self.sqqq_consolidator)
        
        # =====================================================
        # INDICATORS - QQQ (Trend Filter)
        # =====================================================
        self.qqq_ema_fast = ExponentialMovingAverage(self.ema_fast_period)
        self.qqq_ema_slow = ExponentialMovingAverage(self.ema_slow_period)
        self.qqq_rsi = RelativeStrengthIndex(self.rsi_period, MovingAverageType.Wilders)
        
        self.RegisterIndicator(self.qqq, self.qqq_ema_fast, self.qqq_consolidator)
        self.RegisterIndicator(self.qqq, self.qqq_ema_slow, self.qqq_consolidator)
        self.RegisterIndicator(self.qqq, self.qqq_rsi, self.qqq_consolidator)
        
        # =====================================================
        # POSITION TRACKING
        # =====================================================
        self.position_trackers: Dict[str, PositionTracker] = {
            "TQQQ": PositionTracker(symbol="TQQQ"),
            "SQQQ": PositionTracker(symbol="SQQQ")
        }
        
        # =====================================================
        # STATE TRACKING
        # =====================================================
        self.last_qqq_bar: Optional[TradeBar] = None
        self.current_regime = MarketRegime.UNKNOWN
        self.daily_trades_count = 0
        self.max_daily_trades = int(self.GetParameter("max_daily_trades") or 20)  # Increased for momentum
        
        # Volume tracking for spike detection
        self.tqqq_volumes: List[float] = []
        self.sqqq_volumes: List[float] = []
        self.volume_lookback = 20
        
        # Price history for breakout detection (N-bar high/low)
        self.tqqq_highs: List[float] = []
        self.tqqq_lows: List[float] = []
        self.sqqq_highs: List[float] = []
        self.sqqq_lows: List[float] = []
        self.price_history_length = max(self.breakout_bars + 1, 10)  # Keep enough history
        
        # =====================================================
        # SCHEDULING
        # =====================================================
        # Close all positions at 3:50 PM EST
        self.Schedule.On(
            self.DateRules.EveryDay(self.tqqq),
            self.TimeRules.At(15, 50),
            self.CloseAllPositions
        )
        
        # Reset daily counters at market open
        self.Schedule.On(
            self.DateRules.EveryDay(self.tqqq),
            self.TimeRules.AfterMarketOpen(self.tqqq, 5),
            self.ResetDailyState
        )
        
        # =====================================================
        # WARMUP
        # =====================================================
        # Warmup period to ensure indicators are ready
        # Can be configured via parameter (default 0 for limited data scenarios)
        warmup_days = int(self.GetParameter("warmup-days") or "0")
        self.SetWarmUp(timedelta(days=warmup_days))
        self.Debug(f"Warmup period set to {warmup_days} days")
        
        # =====================================================
        # WEBHOOK SIMULATION (Backtest Validation)
        # =====================================================
        self.webhook_simulator: Optional[WebhookSimulator] = None
        webhook_enabled = str(self.GetParameter("webhook-simulation") or "true").lower() == "true"
        
        if HAS_WEBHOOK_SIMULATOR and webhook_enabled and not self.LiveMode:
            # Only enable in backtest mode
            # Note: Parameter names use hyphens to match LEAN config format
            webhook_log = str(self.GetParameter("webhook-log-path") or "")
            if not webhook_log:
                # Default to results folder using absolute path
                session_id = str(self.GetParameter("session-id") or "default")
                # Use absolute path based on algorithm location
                import os
                algo_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(algo_dir)
                webhook_log = os.path.join(project_root, "backtest", "results", session_id, "webhook_log.txt")
            
            self.webhook_simulator = WebhookSimulator(
                interval_minutes=5,  # Match TradingView alert interval
                trading_hours=(dt_time(9, 30), dt_time(16, 0)),
                enable_signal_webhooks=True,
                enable_status_webhooks=True,
                log_file=webhook_log
            )
            self.Log(f"[WEBHOOK] Simulation enabled - logging to {webhook_log}")
        
        # =====================================================
        # SQL PERSISTENCE (Trade-Mind MCP Integration)
        # =====================================================
        # Default to true so backtest results are saved to database
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
                
                # Determine session type
                session_type = "BACKTEST" if not self.LiveMode else "LIVE"
                if self.GetParameter("paper_trading"):
                    session_type = "PAPER"
                
                # Start session with parameter snapshot (v2.0 Momentum)
                params_snapshot = {
                    # Momentum v2.0 parameters
                    "breakout_bars": self.breakout_bars,
                    "rsi_period": self.rsi_period,
                    "rsi_momentum_min": self.rsi_momentum_min,
                    "rsi_momentum_max": self.rsi_momentum_max,
                    "rsi_exit_overbought": self.rsi_exit_overbought,
                    "rsi_exit_oversold": self.rsi_exit_oversold,
                    "position_size": self.position_size,
                    "stop_loss_pct": self.stop_loss_pct,
                    "take_profit_pct": self.take_profit_pct,
                    "trailing_stop_pct": self.trailing_stop_pct,
                    "ema_fast_period": self.ema_fast_period,
                    "ema_slow_period": self.ema_slow_period,
                    "bb_period": self.bb_period,
                    "bb_std_dev": self.bb_std_dev,
                }
                
                # Get session ID from parameters (passed by backtest runner)
                session_id = str(self.GetParameter("session-id") or "")  # type: ignore
                if not session_id or session_id == "default":
                    session_id = None  # Let sql_connector generate one
                
                self.db.start_session(session_type, params_snapshot, session_id)
                self.Debug(f"[SQL] Session started: {self.db.session_id}")
                
            except Exception as e:
                self.Debug(f"[SQL] Failed to initialize connector: {e}")
                self.db = None
        
        # Daily tracking for SQL persistence
        self.daily_realized_pnl = 0.0
        self.daily_win_count = 0
        self.daily_loss_count = 0
        self.daily_volume_traded = 0.0
        self.daily_start_balance = self.Portfolio.TotalPortfolioValue
        self.last_regime_logged: Optional[str] = None
        
        self.Debug(f"TQQQScalpingAlgorithm Initialized")
        self.Debug(f"Parameters: RSI={self.rsi_period}, BB={self.bb_period}/{self.bb_std_dev}")
        self.Debug(f"Position Sizing: L1={self.position_size_level1}, L2={self.position_size_level2}, L3={self.position_size_level3}")
        self.Debug(f"SQL Persistence: {'Enabled' if self.db else 'Disabled'}")
    
    # =========================================================
    # CONSOLIDATED BAR HANDLERS
    # =========================================================
    
    def OnQQQBarConsolidated(self, sender, bar: TradeBar) -> None:
        """Handle QQQ 5-minute bar - update trend regime"""
        self.last_qqq_bar = bar
        self.UpdateMarketRegime()
    
    def OnTQQQBarConsolidated(self, sender, bar: TradeBar) -> None:
        """Handle TQQQ 5-minute bar - main trading logic for TQQQ"""
        if self.IsWarmingUp:
            return
        
        # ===== WEBHOOK SIMULATION =====
        # Simulate scheduled webhook trigger (matches TradingView interval)
        if self.webhook_simulator:
            market_data = self._get_market_data_snapshot("TQQQ", bar)
            self.webhook_simulator.trigger_scheduled_webhook(
                current_time=self.Time,
                symbol="TQQQ",
                market_data=market_data
            )
        
        # Update volume tracking
        self.UpdateVolumeTracking("TQQQ", bar.Volume)
        
        # Skip if indicators not ready
        if not self.IndicatorsReady("TQQQ"):
            # Debug: Log indicator status periodically
            if self.Time.minute == 0:  # Once per hour
                self.Debug(f"{self.Time} Indicators NOT ready - EMA_fast: {self.qqq_ema_fast.IsReady}, EMA_slow: {self.qqq_ema_slow.IsReady}, RSI: {self.tqqq_rsi.IsReady}, BB: {self.tqqq_bb.IsReady}")
            return
        
        # Skip if outside trading hours (9:35 AM - 3:45 PM)
        if not self.IsWithinTradingHours():
            return
        
        # Debug: Log market regime and key indicators once per hour
        if self.Time.minute == 0:
            rsi = self.tqqq_rsi.Current.Value
            self.Debug(f"{self.Time} Regime: {self.current_regime.value}, RSI: {rsi:.1f}, Momentum Min: {self.rsi_momentum_min}")
        
        # Process TQQQ trading signals
        self.ProcessTQQQSignals(bar)
    
    def OnSQQQBarConsolidated(self, sender, bar: TradeBar) -> None:
        """Handle SQQQ 5-minute bar - main trading logic for SQQQ"""
        if self.IsWarmingUp:
            return
        
        # ===== WEBHOOK SIMULATION =====
        # Simulate scheduled webhook trigger (matches TradingView interval)
        if self.webhook_simulator:
            market_data = self._get_market_data_snapshot("SQQQ", bar)
            self.webhook_simulator.trigger_scheduled_webhook(
                current_time=self.Time,
                symbol="SQQQ",
                market_data=market_data
            )
        
        # Update volume tracking
        self.UpdateVolumeTracking("SQQQ", bar.Volume)
        
        # Skip if indicators not ready
        if not self.IndicatorsReady("SQQQ"):
            return
        
        # Skip if outside trading hours
        if not self.IsWithinTradingHours():
            return
        
        # Process SQQQ trading signals
        self.ProcessSQQQSignals(bar)
    
    # =========================================================
    # TRADING LOGIC
    # =========================================================
    
    def ProcessTQQQSignals(self, bar: TradeBar) -> None:
        """
        Process entry/exit signals for TQQQ (Long QQQ exposure).
        MOMENTUM STRATEGY v2.0: Enter on breakout above N-bar high with trend.
        """
        symbol = self.tqqq
        tracker = self.position_trackers["TQQQ"]
        
        # Update price history for breakout detection
        self.tqqq_highs.append(bar.High)
        self.tqqq_lows.append(bar.Low)
        if len(self.tqqq_highs) > self.price_history_length:
            self.tqqq_highs.pop(0)
            self.tqqq_lows.pop(0)
        
        # Get indicator values
        rsi = self.tqqq_rsi.Current.Value
        price = bar.Close
        
        # Get current position
        current_qty = self.Portfolio[symbol].Quantity
        
        # Check for volume spike (optional filter)
        volume_spike = self.CheckVolumeSpike("TQQQ", bar.Volume)
        
        # Calculate N-bar high for breakout detection
        n_bar_high = max(self.tqqq_highs[-self.breakout_bars-1:-1]) if len(self.tqqq_highs) > self.breakout_bars else None
        
        # =====================================================
        # EXIT LOGIC (check first)
        # =====================================================
        if current_qty > 0:
            profit_pct = tracker.calculate_profit_percent(price)
            
            # Exit Conditions for Momentum Strategy:
            # 1. Fixed take profit target
            # 2. RSI too extended (overbought exit)
            # 3. Stop loss
            # Note: Trailing stop is handled by QuantConnect's TrailingStopRiskManagementModel
            
            exit_trade = False
            exit_reason = ""
            
            # Take profit target hit
            if profit_pct >= self.take_profit_pct:
                exit_trade = True
                exit_reason = f"Take profit target ({profit_pct:.2%} >= {self.take_profit_pct:.2%})"
            # RSI too extended - momentum exhausted
            elif rsi > self.rsi_exit_overbought:
                exit_trade = True
                exit_reason = f"RSI overbought exit ({rsi:.1f} > {self.rsi_exit_overbought})"
            # Stop loss
            elif profit_pct < -self.stop_loss_pct:
                exit_trade = True
                exit_reason = f"Stop loss ({profit_pct:.2%})"
            
            if exit_trade:
                self.Liquidate(symbol, tag=f"TQQQ Exit: {exit_reason}")
                self.LogTrade("TQQQ", "EXIT", price, current_qty, profit_pct, exit_reason)
                
                # Webhook: Signal for exit
                if self.webhook_simulator:
                    self.webhook_simulator.trigger_signal_webhook(
                        current_time=self.Time,
                        symbol="TQQQ",
                        signal_type="EXIT",
                        market_data=self._get_market_data_snapshot("TQQQ", bar),
                        trigger_conditions={
                            "reason": exit_reason,
                            "profit_pct": profit_pct,
                            "rsi": rsi,
                            "price": price
                        }
                    )
                
                tracker.reset()
                return
        
        # =====================================================
        # ENTRY LOGIC - MOMENTUM BREAKOUT
        # =====================================================
        # Only enter TQQQ when QQQ is in uptrend
        if self.current_regime not in [MarketRegime.TRENDING_UP, MarketRegime.MEAN_REVERTING]:
            return  # Skip when bearish
        
        # Check daily trade limit
        if self.daily_trades_count >= self.max_daily_trades:
            return
        
        # Don't enter if already in SQQQ position
        if self.Portfolio[self.sqqq].Quantity > 0:
            return
        
        # Don't enter if already in position
        if current_qty > 0:
            return
        
        # Need enough price history for breakout detection
        if n_bar_high is None:
            return
        
        # MOMENTUM ENTRY CONDITIONS:
        # 1. Price breaks above N-bar high (breakout)
        # 2. RSI > momentum minimum (confirms momentum, not oversold reversal)
        # 3. Volume spike (optional, controlled by parameter)
        
        breakout_triggered = price > n_bar_high
        rsi_confirms_momentum = rsi > self.rsi_momentum_min
        volume_ok = not self.require_volume_spike or volume_spike
        
        if breakout_triggered and rsi_confirms_momentum and volume_ok:
            target_pct = self.position_size
            self.SetHoldings(symbol, target_pct, tag=f"TQQQ Breakout: Price={price:.2f} > {n_bar_high:.2f}")
            
            # Update tracker
            new_qty = self.CalculateOrderQuantity(symbol, target_pct)
            tracker.direction = "LONG"
            tracker.add_entry(price, new_qty, self.Time)
            
            self.LogTrade("TQQQ", "ENTRY_BREAKOUT", price, new_qty, 0, 
                         f"Breakout above {n_bar_high:.2f}, RSI={rsi:.1f}")
            
            # Webhook: BUY signal
            if self.webhook_simulator:
                self.webhook_simulator.trigger_signal_webhook(
                    current_time=self.Time,
                    symbol="TQQQ",
                    signal_type="BUY_BREAKOUT",
                    market_data=self._get_market_data_snapshot("TQQQ", bar),
                    trigger_conditions={
                        "rsi": rsi,
                        "price": price,
                        "n_bar_high": n_bar_high,
                        "breakout_bars": self.breakout_bars,
                        "quantity": new_qty,
                        "position_size": target_pct
                    }
                )
            
            self.daily_trades_count += 1
    
    def ProcessSQQQSignals(self, bar: TradeBar) -> None:
        """
        Process entry/exit signals for SQQQ (Short QQQ exposure).
        
        MOMENTUM STRATEGY v2.0:
        - Enter when QQQ is in downtrend (EMA fast < EMA slow)
        - Enter on BREAKDOWN: price < N-bar LOW (momentum down)
        - RSI < rsi_momentum_max confirms downward momentum (not overbought bounce)
        - Single position entry (no pyramiding)
        - Exit via: take profit, RSI oversold, stop loss, or trailing stop
        """
        symbol = self.sqqq
        tracker = self.position_trackers["SQQQ"]
        
        # Get indicator values
        rsi = self.sqqq_rsi.Current.Value
        price = bar.Close
        
        # Get current position
        current_qty = self.Portfolio[symbol].Quantity
        
        # Check for volume spike (optional filter)
        volume_spike = self.CheckVolumeSpike("SQQQ", bar.Volume)
        
        # Update price history for breakout detection
        self.sqqq_highs.append(bar.High)
        self.sqqq_lows.append(bar.Low)
        
        # Calculate N-bar low for breakdown detection
        n_bar_low = None
        if len(self.sqqq_lows) > self.breakout_bars:
            # Get the lowest low of the previous N bars (excluding current)
            n_bar_low = min(list(self.sqqq_lows)[-self.breakout_bars-1:-1])
        
        # =====================================================
        # EXIT LOGIC (check first)
        # =====================================================
        if current_qty > 0:
            profit_pct = tracker.calculate_profit_percent(price)
            
            exit_triggered = False
            exit_reason = ""
            
            # 1. Take Profit: Hit target percentage
            if profit_pct >= self.take_profit_pct:
                exit_triggered = True
                exit_reason = f"Take profit ({profit_pct:.2%} >= {self.take_profit_pct:.2%})"
            
            # 2. RSI Oversold Exit: Downward momentum exhausted
            elif rsi < self.rsi_exit_oversold:
                exit_triggered = True
                exit_reason = f"RSI oversold exit ({rsi:.1f} < {self.rsi_exit_oversold})"
            
            # 3. Stop Loss: Hard cutoff
            elif profit_pct < -self.stop_loss_pct:
                exit_triggered = True
                exit_reason = f"Stop loss ({profit_pct:.2%} < -{self.stop_loss_pct:.2%})"
            
            # Note: Trailing stop is managed by TrailingStopRiskManagementModel
            
            if exit_triggered:
                self.Liquidate(symbol, tag=f"SQQQ Exit: {exit_reason}")
                self.LogTrade("SQQQ", "EXIT", price, current_qty, profit_pct, exit_reason)
                
                # Webhook: SELL signal
                if self.webhook_simulator:
                    self.webhook_simulator.trigger_signal_webhook(
                        current_time=self.Time,
                        symbol="SQQQ",
                        signal_type="SELL_EXIT",
                        market_data=self._get_market_data_snapshot("SQQQ", bar),
                        trigger_conditions={
                            "rsi": rsi,
                            "profit_pct": profit_pct,
                            "exit_reason": exit_reason,
                            "quantity": current_qty
                        }
                    )
                
                tracker.reset()
                return
        
        # =====================================================
        # ENTRY LOGIC - MOMENTUM BREAKDOWN
        # =====================================================
        # Only enter SQQQ when QQQ is in DOWNTREND
        if self.current_regime != MarketRegime.TRENDING_DOWN:
            return
        
        # Check daily trade limit
        if self.daily_trades_count >= self.max_daily_trades:
            return
        
        # Don't enter if already in TQQQ position
        if self.Portfolio[self.tqqq].Quantity > 0:
            return
        
        # Don't enter if already in position
        if current_qty > 0:
            return
        
        # Need enough price history for breakdown detection
        if n_bar_low is None:
            return
        
        # MOMENTUM ENTRY CONDITIONS:
        # 1. Price breaks below N-bar low (breakdown)
        # 2. RSI < momentum max (confirms momentum, not overbought bounce)
        # 3. Volume spike (optional, controlled by parameter)
        
        breakdown_triggered = price < n_bar_low
        rsi_confirms_momentum = rsi < self.rsi_momentum_max  # For shorts, RSI should be declining
        volume_ok = not self.require_volume_spike or volume_spike
        
        if breakdown_triggered and rsi_confirms_momentum and volume_ok:
            target_pct = self.position_size
            self.SetHoldings(symbol, target_pct, tag=f"SQQQ Breakdown: Price={price:.2f} < {n_bar_low:.2f}")
            
            # Update tracker
            new_qty = self.CalculateOrderQuantity(symbol, target_pct)
            tracker.direction = "LONG"  # We're long SQQQ (profiting from QQQ decline)
            tracker.add_entry(price, new_qty, self.Time)
            
            self.LogTrade("SQQQ", "ENTRY_BREAKDOWN", price, new_qty, 0, 
                         f"Breakdown below {n_bar_low:.2f}, RSI={rsi:.1f}")
            
            # Webhook: BUY signal
            if self.webhook_simulator:
                self.webhook_simulator.trigger_signal_webhook(
                    current_time=self.Time,
                    symbol="SQQQ",
                    signal_type="BUY_BREAKDOWN",
                    market_data=self._get_market_data_snapshot("SQQQ", bar),
                    trigger_conditions={
                        "rsi": rsi,
                        "price": price,
                        "n_bar_low": n_bar_low,
                        "breakout_bars": self.breakout_bars,
                        "quantity": new_qty,
                        "position_size": target_pct
                    }
                )
            
            self.daily_trades_count += 1
    
    # =========================================================
    # HELPER METHODS
    # =========================================================
    
    def UpdateMarketRegime(self) -> None:
        """Update market regime based on QQQ trend indicators"""
        if not self.qqq_ema_fast.IsReady or not self.qqq_ema_slow.IsReady:
            self.current_regime = MarketRegime.UNKNOWN
            return
        
        ema_fast = self.qqq_ema_fast.Current.Value
        ema_slow = self.qqq_ema_slow.Current.Value
        
        # Calculate trend strength
        trend_strength = (ema_fast - ema_slow) / ema_slow if ema_slow > 0 else 0
        
        # Determine regime
        old_regime = self.current_regime
        
        if ema_fast > ema_slow and trend_strength > 0.001:
            self.current_regime = MarketRegime.TRENDING_UP
        elif ema_fast < ema_slow and trend_strength < -0.001:
            self.current_regime = MarketRegime.TRENDING_DOWN
        else:
            # Neutral/mean-reverting
            self.current_regime = MarketRegime.MEAN_REVERTING
        
        # Log regime change to SQL for Trade-Mind MCP
        if self.db and self.current_regime != old_regime and self.last_regime_logged != self.current_regime.value:
            trend_direction = "UP" if self.current_regime == MarketRegime.TRENDING_UP else \
                             "DOWN" if self.current_regime == MarketRegime.TRENDING_DOWN else "NEUTRAL"
            
            self.db.log_market_regime(
                symbol="QQQ",
                regime_type=self.current_regime.value.upper(),
                confidence=min(abs(trend_strength) * 100, 1.0),  # Scale to 0-1
                trend_direction=trend_direction,
                volatility=abs(trend_strength)
            )
            self.last_regime_logged = self.current_regime.value
            self.Debug(f"[REGIME] Changed to {self.current_regime.value} (strength: {trend_strength:.4f})")
    
    def IndicatorsReady(self, symbol_name: str) -> bool:
        """Check if all indicators for a symbol are ready"""
        if symbol_name == "TQQQ":
            return (self.tqqq_rsi.IsReady and 
                    self.tqqq_bb.IsReady and 
                    self.qqq_ema_fast.IsReady and 
                    self.qqq_ema_slow.IsReady)
        elif symbol_name == "SQQQ":
            return (self.sqqq_rsi.IsReady and 
                    self.sqqq_bb.IsReady and 
                    self.qqq_ema_fast.IsReady and 
                    self.qqq_ema_slow.IsReady)
        return False
    
    def IsWithinTradingHours(self) -> bool:
        """Check if current time is within trading hours (9:35 AM - 3:45 PM EST)"""
        current_time = self.Time.time()
        market_open = time(9, 35)
        market_close = time(15, 45)
        return market_open <= current_time <= market_close
    
    def UpdateVolumeTracking(self, symbol_name: str, volume: float) -> None:
        """Update rolling volume list for spike detection"""
        if symbol_name == "TQQQ":
            self.tqqq_volumes.append(volume)
            if len(self.tqqq_volumes) > self.volume_lookback:
                self.tqqq_volumes.pop(0)
        elif symbol_name == "SQQQ":
            self.sqqq_volumes.append(volume)
            if len(self.sqqq_volumes) > self.volume_lookback:
                self.sqqq_volumes.pop(0)
    
    def CheckVolumeSpike(self, symbol_name: str, current_volume: float) -> bool:
        """Check if current volume is a spike (> multiplier * average)"""
        volumes = self.tqqq_volumes if symbol_name == "TQQQ" else self.sqqq_volumes
        
        if len(volumes) < 10:
            return True  # Not enough data, assume valid
        
        avg_volume = sum(volumes) / len(volumes)
        return current_volume > avg_volume * self.volume_spike_multiplier
    
    def CalculateOrderQuantity(self, symbol, target_percentage: float) -> float:
        """Calculate order quantity for a target percentage of portfolio"""
        price = self.Securities[symbol].Price
        if price <= 0:
            return 0
        target_value = self.Portfolio.TotalPortfolioValue * target_percentage
        return target_value / price
    
    # =========================================================
    # SCHEDULED EVENTS
    # =========================================================
    
    def CloseAllPositions(self) -> None:
        """Close all positions at end of day (3:50 PM EST)"""
        self.Liquidate(tag="End of Day Close")
        
        # Log final positions
        for symbol_name, tracker in self.position_trackers.items():
            if tracker.num_entries > 0:
                self.Debug(f"EOD Close - {symbol_name}: Avg Price={tracker.average_price:.2f}, "
                          f"Entries={tracker.num_entries}")
                
                # Log EOD close as trade to SQL
                if self.db:
                    price = self.Securities[self.tqqq if symbol_name == "TQQQ" else self.sqqq].Price
                    self.db.log_trade(
                        symbol=symbol_name,
                        side="BUY" if tracker.direction == "LONG" else "SELL",
                        quantity=tracker.total_quantity,
                        entry_price=tracker.average_price,
                        exit_price=price,
                        entry_time=tracker.entries[0].timestamp,
                        exit_time=self.Time,
                        entry_reason=f"PYRAMID_L{tracker.num_entries}",
                        exit_reason="EOD_CLOSE"
                    )
                    
                    realized_pnl = (price - tracker.average_price) * tracker.total_quantity
                    if tracker.direction == "SHORT":
                        realized_pnl = (tracker.average_price - price) * tracker.total_quantity
                    self.daily_realized_pnl += realized_pnl
                    self.daily_volume_traded += tracker.total_quantity * tracker.average_price
                    if realized_pnl > 0:
                        self.daily_win_count += 1
                    elif realized_pnl < 0:
                        self.daily_loss_count += 1
                
                tracker.reset()
        
        # Update daily performance in SQL
        if self.db:
            self.db.update_daily_performance(
                trading_date=self.Time,
                opening_balance=self.daily_start_balance,
                closing_balance=self.Portfolio.TotalPortfolioValue,
                realized_pnl=self.daily_realized_pnl,
                unrealized_pnl=0.0,  # All closed at EOD
                trade_count=self.daily_trades_count,
                win_count=self.daily_win_count,
                loss_count=self.daily_loss_count,
                volume_traded=self.daily_volume_traded
            )
        
        self.Debug(f"All positions closed at {self.Time}. Daily trades: {self.daily_trades_count}")
    
    def ResetDailyState(self) -> None:
        """Reset daily counters at market open"""
        self.daily_trades_count = 0
        
        # Reset SQL daily tracking
        self.daily_realized_pnl = 0.0
        self.daily_win_count = 0
        self.daily_loss_count = 0
        self.daily_volume_traded = 0.0
        self.daily_start_balance = self.Portfolio.TotalPortfolioValue
        
        # Reset intraday VWAP
        self.tqqq_vwap.Reset()
        self.sqqq_vwap.Reset()
        
        self.Debug(f"Daily state reset at {self.Time}")
    
    # =========================================================
    # LOGGING & PERSISTENCE
    # =========================================================
    
    def LogTrade(self, symbol: str, action: str, price: float, quantity: float, 
                 profit_pct: float, reason: str) -> None:
        """Log trade details for analysis and persist to SQL"""
        self.Debug(f"[TRADE] {self.Time} | {symbol} | {action} | "
                  f"Price={price:.2f} | Qty={quantity:.0f} | "
                  f"P&L={profit_pct:.2%} | {reason}")
        
        # Plot for visualization
        self.Plot("Trades", f"{symbol}_{action}", price)
        
        # SQL Persistence for Trade-Mind MCP
        if self.db and action in ["EXIT", "STOP_LOSS"]:
            tracker = self.position_trackers.get(symbol)
            if tracker and tracker.entries:
                realized_pnl = (price - tracker.average_price) * tracker.total_quantity
                if tracker.direction == "SHORT":
                    realized_pnl = (tracker.average_price - price) * tracker.total_quantity
                
                self.db.log_trade(
                    symbol=symbol,
                    side="BUY" if tracker.direction == "LONG" else "SELL",
                    quantity=tracker.total_quantity,
                    entry_price=tracker.average_price,
                    exit_price=price,
                    entry_time=tracker.entries[0].timestamp,
                    exit_time=self.Time,
                    entry_reason=f"PYRAMID_L{tracker.num_entries}",
                    exit_reason=reason
                )
                
                # Update daily stats
                self.daily_realized_pnl += realized_pnl
                self.daily_volume_traded += tracker.total_quantity * tracker.average_price
                if realized_pnl > 0:
                    self.daily_win_count += 1
                elif realized_pnl < 0:
                    self.daily_loss_count += 1
    
    def LogSignal(self, symbol: str, signal_type: str, direction: str,
                   rsi_value: float, price: float, was_acted_on: bool,
                   reason_not_acted: str = None) -> None:
        """Log trading signal for Trade-Mind MCP analysis"""
        if not self.db:
            return
        
        # Calculate signal strength based on indicator values (v2.0 Momentum)
        strength = 0.5
        if signal_type == "ENTRY":
            # For momentum strategy, signal strength is based on RSI distance from threshold
            if direction == "LONG" and rsi_value > self.rsi_momentum_min:
                # Higher RSI = stronger upward momentum
                strength = min(0.9, 0.5 + (rsi_value - self.rsi_momentum_min) / 50)
            elif direction == "SHORT" and rsi_value < self.rsi_momentum_max:
                # Lower RSI = stronger downward momentum
                strength = min(0.9, 0.5 + (self.rsi_momentum_max - rsi_value) / 50)
        
        # Get additional indicator values
        vwap_distance = None
        bb_position = None
        
        if symbol == "TQQQ" and self.tqqq_vwap.IsReady:
            vwap = self.tqqq_vwap.Current.Value
            vwap_distance = (price - vwap) / vwap if vwap > 0 else 0
            if self.tqqq_bb.IsReady:
                bb_range = self.tqqq_bb.UpperBand.Current.Value - self.tqqq_bb.LowerBand.Current.Value
                if bb_range > 0:
                    bb_position = (price - self.tqqq_bb.LowerBand.Current.Value) / bb_range
        elif symbol == "SQQQ" and self.sqqq_vwap.IsReady:
            vwap = self.sqqq_vwap.Current.Value
            vwap_distance = (price - vwap) / vwap if vwap > 0 else 0
            if self.sqqq_bb.IsReady:
                bb_range = self.sqqq_bb.UpperBand.Current.Value - self.sqqq_bb.LowerBand.Current.Value
                if bb_range > 0:
                    bb_position = (price - self.sqqq_bb.LowerBand.Current.Value) / bb_range
        
        self.db.log_signal(
            symbol=symbol,
            signal_type=signal_type,
            direction=direction,
            strength=strength,
            rsi_value=rsi_value,
            vwap_distance=vwap_distance,
            bb_position=bb_position,
            qqq_trend=self.current_regime.value,
            price=price,
            was_acted_on=was_acted_on,
            reason_not_acted=reason_not_acted
        )
    
    def OnOrderEvent(self, orderEvent: OrderEvent) -> None:
        """Handle order events for logging and persistence"""
        if orderEvent.Status == OrderStatus.Filled:
            symbol = orderEvent.Symbol
            fill_price = orderEvent.FillPrice
            fill_qty = orderEvent.FillQuantity
            direction = "BUY" if orderEvent.Direction == OrderDirection.Buy else "SELL"
            
            self.Debug(f"[ORDER FILLED] {self.Time} | {symbol} | {direction} | "
                      f"Price={fill_price:.2f} | Qty={fill_qty}")
            
            # Log order to SQL
            if self.db:
                self.db.log_order(
                    order_id=str(orderEvent.OrderId),
                    symbol=str(symbol),
                    order_type="MARKET",
                    side=direction,
                    quantity=abs(fill_qty),
                    status="FILLED",
                    fill_price=fill_price,
                    fill_quantity=abs(fill_qty),
                    tag=orderEvent.Message or ""
                )
    
    def OnEndOfAlgorithm(self) -> None:
        """Called at the end of algorithm execution"""
        final_value = self.Portfolio.TotalPortfolioValue
        initial_value = 100000  # Default starting cash
        total_return = (final_value / initial_value) - 1
        
        self.Debug("=" * 60)
        self.Debug("ALGORITHM COMPLETED")
        self.Debug(f"Final Portfolio Value: ${final_value:,.2f}")
        self.Debug(f"Total Return: {total_return * 100:.2f}%")
        self.Debug("=" * 60)
        
        # Close SQL session with final statistics
        if self.db:
            # Calculate total trades (sum of daily trades would need proper tracking)
            total_trades = self.daily_win_count + self.daily_loss_count
            win_rate = self.daily_win_count / total_trades if total_trades > 0 else 0
            
            self.db.end_session(
                total_return=total_return,
                sharpe_ratio=0.0,  # Would need proper calculation
                max_drawdown=0.0,  # Would need proper calculation
                total_trades=total_trades,
                win_rate=win_rate
            )
            
            self.db.disconnect()
            self.Debug(f"[SQL] Session ended: {self.db.session_id}")
            self.Debug(f"[SQL] Data available for Trade-Mind MCP queries")
        
        # Log webhook summary
        if self.webhook_simulator:
            summary = self.webhook_simulator.get_summary()
            self.Debug("[WEBHOOK] Simulation Summary:")
            self.Debug(f"  Total webhooks fired: {summary['total_webhooks']}")
            self.Debug(f"  Scheduled: {summary['by_type'].get('scheduled', 0)}")
            self.Debug(f"  Signals: {summary['by_type'].get('signal', 0)}")
            self.Debug(f"  Alerts: {summary['by_type'].get('alert', 0)}")
            self.Debug(f"  Status: {summary['by_type'].get('status', 0)}")
            self.Debug(f"  Webhook log: See results folder")
    
    def _get_market_data_snapshot(self, symbol: str, bar: TradeBar) -> Dict:
        """
        Create market data snapshot for webhook simulation.
        Mimics the data structure that would be sent in a TradingView webhook.
        """
        data = {
            "symbol": symbol,
            "price": float(bar.Close),
            "open": float(bar.Open),
            "high": float(bar.High),
            "low": float(bar.Low),
            "volume": float(bar.Volume),
            "time": self.Time.isoformat()
        }
        
        # Add indicator values
        if symbol == "TQQQ":
            if self.tqqq_rsi.IsReady:
                data["rsi"] = float(self.tqqq_rsi.Current.Value)
            if self.tqqq_vwap.IsReady:
                data["vwap"] = float(self.tqqq_vwap.Current.Value)
            if self.tqqq_bb.IsReady:
                data["bb_upper"] = float(self.tqqq_bb.UpperBand.Current.Value)
                data["bb_middle"] = float(self.tqqq_bb.MiddleBand.Current.Value)
                data["bb_lower"] = float(self.tqqq_bb.LowerBand.Current.Value)
        elif symbol == "SQQQ":
            if self.sqqq_rsi.IsReady:
                data["rsi"] = float(self.sqqq_rsi.Current.Value)
            if self.sqqq_vwap.IsReady:
                data["vwap"] = float(self.sqqq_vwap.Current.Value)
            if self.sqqq_bb.IsReady:
                data["bb_upper"] = float(self.sqqq_bb.UpperBand.Current.Value)
                data["bb_middle"] = float(self.sqqq_bb.MiddleBand.Current.Value)
                data["bb_lower"] = float(self.sqqq_bb.LowerBand.Current.Value)
        
        # Add position info
        portfolio_position = self.Portfolio[self.tqqq if symbol == "TQQQ" else self.sqqq]
        data["position_quantity"] = float(portfolio_position.Quantity)
        data["position_value"] = float(portfolio_position.HoldingsValue)
        data["unrealized_pnl"] = float(portfolio_position.UnrealizedProfit)
        
        # Add market regime
        data["market_regime"] = self.current_regime.value
        
        return data
