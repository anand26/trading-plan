"""
Utility functions for the Adaptive Agent.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Optional


def generate_id(prefix: str = "dec") -> str:
    """Generate a unique ID with a prefix."""
    from uuid import uuid4
    return f"{prefix}_{uuid4().hex[:12]}"


def safe_json_dumps(obj: Any) -> str:
    """Safely serialize an object to JSON."""
    def default_serializer(o):
        if isinstance(o, datetime):
            return o.isoformat()
        if hasattr(o, 'value'):  # Enum
            return o.value
        if hasattr(o, 'model_dump'):  # Pydantic model
            return o.model_dump()
        if hasattr(o, '__dict__'):
            return o.__dict__
        return str(o)
    
    return json.dumps(obj, default=default_serializer)


def safe_json_loads(s: str) -> Any:
    """Safely deserialize JSON."""
    try:
        return json.loads(s) if s else None
    except (json.JSONDecodeError, TypeError):
        return None


def hash_conditions(conditions: dict) -> str:
    """Create a hash of conditions for pattern matching."""
    normalized = json.dumps(conditions, sort_keys=True)
    return hashlib.md5(normalized.encode()).hexdigest()


def format_pct(value: float, decimals: int = 1) -> str:
    """Format a decimal as percentage."""
    return f"{value * 100:.{decimals}f}%"


def format_currency(value: float) -> str:
    """Format a number as currency."""
    return f"${value:,.2f}"


def time_ago(dt: datetime) -> str:
    """Get a human-readable time difference."""
    now = datetime.now()
    diff = now - dt
    
    if diff < timedelta(minutes=1):
        return "just now"
    elif diff < timedelta(hours=1):
        mins = int(diff.total_seconds() / 60)
        return f"{mins}m ago"
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f"{hours}h ago"
    else:
        days = diff.days
        return f"{days}d ago"


def is_market_hours(dt: Optional[datetime] = None) -> bool:
    """
    Check if given time is during market hours.
    
    Market hours: 9:30 AM - 4:00 PM ET, weekdays only.
    Note: Does not account for holidays.
    """
    if dt is None:
        dt = datetime.now()
    
    # Check weekday (0=Monday, 6=Sunday)
    if dt.weekday() >= 5:
        return False
    
    # Check time (assumes ET timezone)
    market_open = dt.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = dt.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_open <= dt <= market_close


def is_first_hour(dt: Optional[datetime] = None) -> bool:
    """Check if in first hour of trading (9:30-10:30 AM)."""
    if dt is None:
        dt = datetime.now()
    return dt.hour == 9 and dt.minute >= 30 or dt.hour == 10 and dt.minute < 30


def is_last_hour(dt: Optional[datetime] = None) -> bool:
    """Check if in last hour of trading (3:00-4:00 PM)."""
    if dt is None:
        dt = datetime.now()
    return dt.hour == 15


def calculate_confidence_decay(
    base_confidence: float,
    hours_since_update: float,
    half_life_hours: float = 24.0
) -> float:
    """
    Calculate decayed confidence based on time since update.
    
    Uses exponential decay with configurable half-life.
    """
    import math
    decay_rate = math.log(2) / half_life_hours
    decayed = base_confidence * math.exp(-decay_rate * hours_since_update)
    return max(0.0, min(1.0, decayed))


def weighted_average(values: list[float], weights: list[float]) -> float:
    """Calculate weighted average."""
    if not values or not weights or len(values) != len(weights):
        return 0.0
    
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    
    return sum(v * w for v, w in zip(values, weights)) / total_weight


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to a range."""
    return max(min_val, min(max_val, value))


def exponential_moving_average(
    current_value: float,
    previous_ema: float,
    alpha: float = 0.1
) -> float:
    """Calculate exponential moving average."""
    return alpha * current_value + (1 - alpha) * previous_ema


class RateLimiter:
    """Simple rate limiter for actions."""
    
    def __init__(self, max_actions: int, window_seconds: int):
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self.actions: list[datetime] = []
    
    def can_act(self) -> bool:
        """Check if an action is allowed."""
        self._cleanup()
        return len(self.actions) < self.max_actions
    
    def record_action(self):
        """Record an action."""
        self._cleanup()
        self.actions.append(datetime.now())
    
    def _cleanup(self):
        """Remove old actions outside the window."""
        cutoff = datetime.now() - timedelta(seconds=self.window_seconds)
        self.actions = [a for a in self.actions if a > cutoff]
    
    def remaining(self) -> int:
        """Get remaining actions in current window."""
        self._cleanup()
        return max(0, self.max_actions - len(self.actions))
    
    def seconds_until_available(self) -> float:
        """Get seconds until next action is available."""
        if self.can_act():
            return 0.0
        
        oldest = min(self.actions)
        cutoff = oldest + timedelta(seconds=self.window_seconds)
        return max(0.0, (cutoff - datetime.now()).total_seconds())


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure: Optional[datetime] = None
        self.is_open = False
    
    def record_success(self):
        """Record a successful operation."""
        self.failure_count = 0
        self.is_open = False
    
    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
    
    def can_execute(self) -> bool:
        """Check if operations are allowed."""
        if not self.is_open:
            return True
        
        # Check if recovery timeout has passed
        if self.last_failure:
            elapsed = (datetime.now() - self.last_failure).total_seconds()
            if elapsed >= self.recovery_timeout:
                # Allow a test request
                return True
        
        return False
    
    def reset(self):
        """Manually reset the circuit breaker."""
        self.failure_count = 0
        self.is_open = False
        self.last_failure = None
