"""
Webhook Simulation for Backtester
===================================
Simulates TradingView webhook triggers during backtesting to match live behavior.

In Live Trading:
- TradingView sends webhooks at configured intervals (e.g., every 5 minutes)
- Algorithm processes data and makes decisions
- Webhooks contain market conditions at that specific time

In Backtesting:
- This simulator logs when webhooks WOULD fire
- Helps validate strategy behavior matches live expectations
- Ensures timing, frequency, and data alignment
"""

from datetime import datetime, time, timedelta
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging


class WebhookType(Enum):
    """Types of webhook triggers"""
    SCHEDULED = "scheduled"  # Regular interval (e.g., every 5 min)
    SIGNAL = "signal"  # On trading signal detected
    ALERT = "alert"  # Price alert / stop loss
    STATUS = "status"  # Health check


@dataclass
class WebhookEvent:
    """Represents a simulated webhook trigger"""
    timestamp: datetime
    webhook_type: WebhookType
    symbol: str
    trigger_reason: str
    market_data: Dict
    
    # Metadata
    bar_time: datetime  # Time of the bar that triggered this
    trigger_price: float
    trigger_conditions: Dict
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.webhook_type.value,
            "symbol": self.symbol,
            "reason": self.trigger_reason,
            "bar_time": self.bar_time.isoformat(),
            "price": self.trigger_price,
            "conditions": self.trigger_conditions,
            "market_data": self.market_data
        }


class WebhookSimulator:
    """
    Simulates TradingView webhook triggers during backtesting.
    
    Usage:
        simulator = WebhookSimulator(
            interval_minutes=5,
            trading_hours=(time(9, 30), time(16, 0))
        )
        
        # In OnData or consolidated bar handler:
        if simulator.should_trigger(current_time):
            webhook_event = simulator.create_webhook_event(
                timestamp=current_time,
                symbol="TQQQ",
                market_data={"rsi": 35.0, "price": 45.50, ...}
            )
            simulator.log_webhook(webhook_event)
    """
    
    def __init__(
        self,
        interval_minutes: int = 5,
        trading_hours: tuple = (time(9, 30), time(16, 0)),
        enable_signal_webhooks: bool = True,
        enable_status_webhooks: bool = True,
        log_file: Optional[str] = None,
        log_scheduled_webhooks: bool = False  # NEW: Skip logging scheduled webhooks (too many)
    ):
        """
        Initialize webhook simulator.
        
        Args:
            interval_minutes: How often scheduled webhooks fire (matches TradingView alert interval)
            trading_hours: (start_time, end_time) for active webhooks
            enable_signal_webhooks: Trigger webhooks on trading signals
            enable_status_webhooks: Trigger status webhooks (e.g., position updates)
            log_file: Optional file path to write webhook log
            log_scheduled_webhooks: Whether to log SCHEDULED webhooks (set False for faster backtests)
        """
        self.interval = timedelta(minutes=interval_minutes)
        self.trading_hours = trading_hours
        self.enable_signal_webhooks = enable_signal_webhooks
        self.enable_status_webhooks = enable_status_webhooks
        self.log_scheduled_webhooks = log_scheduled_webhooks
        
        # State
        self.last_scheduled_trigger: Optional[datetime] = None
        self.webhook_events: List[WebhookEvent] = []
        self.webhook_count = 0
        
        # Logging
        self.logger = logging.getLogger(__name__)
        self.log_file = log_file
        if log_file:
            # Ensure directory exists
            import os
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(file_handler)
            self.logger.setLevel(logging.INFO)
    
    def is_trading_hours(self, current_time: datetime) -> bool:
        """Check if current time is within trading hours."""
        t = current_time.time()
        return self.trading_hours[0] <= t <= self.trading_hours[1]
    
    def should_trigger_scheduled(self, current_time: datetime) -> bool:
        """
        Determine if a scheduled webhook should trigger.
        
        Scheduled webhooks fire at regular intervals during trading hours,
        matching TradingView alert frequency.
        """
        if not self.is_trading_hours(current_time):
            return False
        
        if self.last_scheduled_trigger is None:
            # First trigger - align to interval boundary
            self.last_scheduled_trigger = current_time
            return True
        
        time_since_last = current_time - self.last_scheduled_trigger
        
        if time_since_last >= self.interval:
            self.last_scheduled_trigger = current_time
            return True
        
        return False
    
    def create_webhook_event(
        self,
        timestamp: datetime,
        webhook_type: WebhookType,
        symbol: str,
        trigger_reason: str,
        market_data: Dict,
        trigger_conditions: Optional[Dict] = None
    ) -> WebhookEvent:
        """
        Create a webhook event.
        
        Args:
            timestamp: When webhook fires
            webhook_type: Type of webhook (SCHEDULED, SIGNAL, etc.)
            symbol: Trading symbol
            trigger_reason: Why webhook fired (e.g., "5-minute interval")
            market_data: Current market conditions (price, RSI, volume, etc.)
            trigger_conditions: Specific conditions that triggered webhook
        
        Returns:
            WebhookEvent object
        """
        return WebhookEvent(
            timestamp=timestamp,
            webhook_type=webhook_type,
            symbol=symbol,
            trigger_reason=trigger_reason,
            market_data=market_data,
            bar_time=timestamp,
            trigger_price=market_data.get("price", 0.0),
            trigger_conditions=trigger_conditions or {}
        )
    
    def log_webhook(self, event: WebhookEvent) -> None:
        """
        Log a webhook event.
        
        This simulates what would appear in TradingView webhook logs
        or server request logs in live trading.
        """
        self.webhook_events.append(event)
        self.webhook_count += 1
        
        # Skip file logging for SCHEDULED webhooks if disabled (performance optimization)
        if event.webhook_type == WebhookType.SCHEDULED and not self.log_scheduled_webhooks:
            return
        
        # Format log message
        msg = (
            f"[WEBHOOK #{self.webhook_count}] "
            f"{event.webhook_type.value.upper()} | "
            f"{event.symbol} @ {event.trigger_price:.2f} | "
            f"{event.trigger_reason}"
        )
        
        self.logger.info(msg)
        self.logger.debug(f"Market Data: {event.market_data}")
        self.logger.debug(f"Conditions: {event.trigger_conditions}")
    
    def trigger_scheduled_webhook(
        self,
        current_time: datetime,
        symbol: str,
        market_data: Dict
    ) -> Optional[WebhookEvent]:
        """
        Check and trigger scheduled webhook if due.
        
        Returns:
            WebhookEvent if triggered, None otherwise
        """
        # PERFORMANCE: Skip scheduled webhooks entirely in backtests
        # They create ~40,000 events per year which slows everything down
        if not self.log_scheduled_webhooks:
            return None
        
        if self.should_trigger_scheduled(current_time):
            event = self.create_webhook_event(
                timestamp=current_time,
                webhook_type=WebhookType.SCHEDULED,
                symbol=symbol,
                trigger_reason=f"{self.interval.total_seconds() / 60:.0f}-minute interval",
                market_data=market_data
            )
            self.log_webhook(event)
            return event
        return None
    
    def trigger_signal_webhook(
        self,
        current_time: datetime,
        symbol: str,
        signal_type: str,
        market_data: Dict,
        trigger_conditions: Dict
    ) -> Optional[WebhookEvent]:
        """
        Trigger webhook for trading signal.
        
        Args:
            signal_type: Type of signal (e.g., "BUY", "SELL", "STOP_LOSS")
            trigger_conditions: Conditions that generated signal
        
        Returns:
            WebhookEvent if enabled, None otherwise
        """
        if not self.enable_signal_webhooks:
            return None
        
        event = self.create_webhook_event(
            timestamp=current_time,
            webhook_type=WebhookType.SIGNAL,
            symbol=symbol,
            trigger_reason=f"{signal_type} signal detected",
            market_data=market_data,
            trigger_conditions=trigger_conditions
        )
        self.log_webhook(event)
        return event
    
    def trigger_alert_webhook(
        self,
        current_time: datetime,
        symbol: str,
        alert_type: str,
        market_data: Dict,
        alert_message: str
    ) -> Optional[WebhookEvent]:
        """
        Trigger webhook for price alert or stop loss.
        
        Args:
            alert_type: Type of alert (e.g., "STOP_LOSS", "TAKE_PROFIT", "PRICE_ALERT")
            alert_message: Human-readable alert message
        """
        event = self.create_webhook_event(
            timestamp=current_time,
            webhook_type=WebhookType.ALERT,
            symbol=symbol,
            trigger_reason=alert_message,
            market_data=market_data,
            trigger_conditions={"alert_type": alert_type}
        )
        self.log_webhook(event)
        return event
    
    def trigger_status_webhook(
        self,
        current_time: datetime,
        symbol: str,
        status_type: str,
        market_data: Dict
    ) -> Optional[WebhookEvent]:
        """
        Trigger status webhook (position opened, closed, etc.).
        """
        if not self.enable_status_webhooks:
            return None
        
        event = self.create_webhook_event(
            timestamp=current_time,
            webhook_type=WebhookType.STATUS,
            symbol=symbol,
            trigger_reason=status_type,
            market_data=market_data
        )
        self.log_webhook(event)
        return event
    
    def get_summary(self) -> Dict:
        """Get summary of webhook activity."""
        webhook_counts = {}
        for wtype in WebhookType:
            count = sum(1 for e in self.webhook_events if e.webhook_type == wtype)
            webhook_counts[wtype.value] = count
        
        return {
            "total_webhooks": self.webhook_count,
            "by_type": webhook_counts,
            "interval_minutes": self.interval.total_seconds() / 60,
            "trading_hours": f"{self.trading_hours[0]} - {self.trading_hours[1]}",
            "events": [e.to_dict() for e in self.webhook_events]
        }
    
    def reset(self) -> None:
        """Reset webhook simulator state."""
        self.last_scheduled_trigger = None
        self.webhook_events = []
        self.webhook_count = 0
