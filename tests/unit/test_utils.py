"""
Unit tests for utility functions.
"""

import pytest
from datetime import datetime, timedelta


class TestIdGeneration:
    """Tests for ID generation utilities."""
    
    def test_generate_id_with_prefix(self):
        """Should generate ID with prefix."""
        from adaptive_agent.utils import generate_id
        
        id1 = generate_id("dec")
        id2 = generate_id("dec")
        
        assert id1.startswith("dec_")
        assert id2.startswith("dec_")
        assert id1 != id2
    
    def test_generate_id_unique(self):
        """Should generate unique IDs."""
        from adaptive_agent.utils import generate_id
        
        ids = [generate_id() for _ in range(100)]
        
        assert len(set(ids)) == 100


class TestJsonUtils:
    """Tests for JSON utilities."""
    
    def test_safe_json_dumps_datetime(self):
        """Should serialize datetime objects."""
        from adaptive_agent.utils import safe_json_dumps
        
        data = {"timestamp": datetime(2024, 1, 15, 10, 30)}
        result = safe_json_dumps(data)
        
        assert "2024-01-15" in result
    
    def test_safe_json_dumps_enum(self):
        """Should serialize enum values."""
        from adaptive_agent.utils import safe_json_dumps
        from adaptive_agent.models import MarketRegime
        
        data = {"regime": MarketRegime.BULLISH}
        result = safe_json_dumps(data)
        
        assert "BULLISH" in result
    
    def test_safe_json_loads_valid(self):
        """Should parse valid JSON."""
        from adaptive_agent.utils import safe_json_loads
        
        result = safe_json_loads('{"key": "value"}')
        
        assert result == {"key": "value"}
    
    def test_safe_json_loads_invalid(self):
        """Should return None for invalid JSON."""
        from adaptive_agent.utils import safe_json_loads
        
        result = safe_json_loads("not json")
        
        assert result is None


class TestFormatUtils:
    """Tests for formatting utilities."""
    
    def test_format_pct(self):
        """Should format as percentage."""
        from adaptive_agent.utils import format_pct
        
        assert format_pct(0.1234) == "12.3%"
        assert format_pct(0.1234, 2) == "12.34%"
    
    def test_format_currency(self):
        """Should format as currency."""
        from adaptive_agent.utils import format_currency
        
        assert format_currency(1234.56) == "$1,234.56"
        assert format_currency(0) == "$0.00"
    
    def test_time_ago_minutes(self):
        """Should format minutes ago."""
        from adaptive_agent.utils import time_ago
        
        dt = datetime.now() - timedelta(minutes=5)
        result = time_ago(dt)
        
        assert "5m ago" in result
    
    def test_time_ago_hours(self):
        """Should format hours ago."""
        from adaptive_agent.utils import time_ago
        
        dt = datetime.now() - timedelta(hours=3)
        result = time_ago(dt)
        
        assert "3h ago" in result


class TestMarketHours:
    """Tests for market hours utilities."""
    
    def test_is_market_hours_weekday(self):
        """Should return True during market hours."""
        from adaptive_agent.utils import is_market_hours
        
        # Wednesday at 11 AM
        dt = datetime(2024, 1, 17, 11, 0)
        
        assert is_market_hours(dt) == True
    
    def test_is_market_hours_weekend(self):
        """Should return False on weekends."""
        from adaptive_agent.utils import is_market_hours
        
        # Saturday at 11 AM
        dt = datetime(2024, 1, 20, 11, 0)
        
        assert is_market_hours(dt) == False
    
    def test_is_market_hours_after_close(self):
        """Should return False after market close."""
        from adaptive_agent.utils import is_market_hours
        
        # Wednesday at 5 PM
        dt = datetime(2024, 1, 17, 17, 0)
        
        assert is_market_hours(dt) == False


class TestMathUtils:
    """Tests for math utilities."""
    
    def test_weighted_average(self):
        """Should calculate weighted average."""
        from adaptive_agent.utils import weighted_average
        
        result = weighted_average([10, 20, 30], [1, 2, 3])
        
        # (10*1 + 20*2 + 30*3) / (1+2+3) = 140/6 ≈ 23.33
        assert abs(result - 23.33) < 0.01
    
    def test_weighted_average_empty(self):
        """Should return 0 for empty lists."""
        from adaptive_agent.utils import weighted_average
        
        assert weighted_average([], []) == 0
    
    def test_clamp(self):
        """Should clamp values to range."""
        from adaptive_agent.utils import clamp
        
        assert clamp(5, 0, 10) == 5
        assert clamp(-5, 0, 10) == 0
        assert clamp(15, 0, 10) == 10
    
    def test_exponential_moving_average(self):
        """Should calculate EMA."""
        from adaptive_agent.utils import exponential_moving_average
        
        result = exponential_moving_average(100, 90, alpha=0.2)
        
        # 0.2 * 100 + 0.8 * 90 = 20 + 72 = 92
        assert result == 92.0


class TestConfidenceDecay:
    """Tests for confidence decay."""
    
    def test_confidence_decay_no_time(self):
        """Should not decay with 0 hours."""
        from adaptive_agent.utils import calculate_confidence_decay
        
        result = calculate_confidence_decay(0.8, 0)
        
        assert result == 0.8
    
    def test_confidence_decay_half_life(self):
        """Should decay to half at half-life."""
        from adaptive_agent.utils import calculate_confidence_decay
        
        result = calculate_confidence_decay(1.0, 24, half_life_hours=24)
        
        assert abs(result - 0.5) < 0.01


class TestRateLimiter:
    """Tests for RateLimiter."""
    
    def test_rate_limiter_allows_actions(self):
        """Should allow actions under limit."""
        from adaptive_agent.utils import RateLimiter
        
        limiter = RateLimiter(max_actions=5, window_seconds=60)
        
        assert limiter.can_act() == True
        assert limiter.remaining() == 5
    
    def test_rate_limiter_blocks_excess(self):
        """Should block actions over limit."""
        from adaptive_agent.utils import RateLimiter
        
        limiter = RateLimiter(max_actions=3, window_seconds=60)
        
        for _ in range(3):
            limiter.record_action()
        
        assert limiter.can_act() == False
        assert limiter.remaining() == 0


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""
    
    def test_circuit_breaker_closed(self):
        """Should allow execution when closed."""
        from adaptive_agent.utils import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3)
        
        assert cb.can_execute() == True
        assert cb.is_open == False
    
    def test_circuit_breaker_opens_on_failures(self):
        """Should open after threshold failures."""
        from adaptive_agent.utils import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3)
        
        for _ in range(3):
            cb.record_failure()
        
        assert cb.is_open == True
        assert cb.can_execute() == False
    
    def test_circuit_breaker_resets_on_success(self):
        """Should reset on success."""
        from adaptive_agent.utils import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        
        assert cb.failure_count == 0
        assert cb.is_open == False
