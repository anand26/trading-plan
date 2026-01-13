"""
Unit tests for Pydantic models.
"""

import pytest
from datetime import datetime


class TestMarketSnapshot:
    """Tests for MarketSnapshot model."""
    
    def test_create_default_snapshot(self):
        """Should create snapshot with default values."""
        from adaptive_agent.models import MarketSnapshot
        
        snapshot = MarketSnapshot()
        
        assert snapshot.rsi == 50.0
        assert snapshot.momentum == 0.0
        assert snapshot.volatility == 0.0
        assert snapshot.is_market_open == True
    
    def test_create_snapshot_with_values(self, sample_market_snapshot):
        """Should create snapshot with provided values."""
        assert sample_market_snapshot.tqqq_price == 45.50
        assert sample_market_snapshot.rsi == 55.0
        assert sample_market_snapshot.regime.value == "NEUTRAL"
    
    def test_snapshot_serialization(self, sample_market_snapshot):
        """Should serialize to JSON correctly."""
        json_str = sample_market_snapshot.model_dump_json()
        
        assert "tqqq_price" in json_str
        assert "45.5" in json_str
        assert "NEUTRAL" in json_str


class TestPerformanceSnapshot:
    """Tests for PerformanceSnapshot model."""
    
    def test_create_default_performance(self):
        """Should create performance with default values."""
        from adaptive_agent.models import PerformanceSnapshot
        
        perf = PerformanceSnapshot()
        
        assert perf.daily_pnl == 0.0
        assert perf.total_trades == 0
        assert perf.current_streak == 0
    
    def test_create_performance_with_values(self, sample_performance_snapshot):
        """Should create performance with provided values."""
        assert sample_performance_snapshot.daily_pnl == 125.50
        assert sample_performance_snapshot.weekly_win_rate == 0.57
        assert sample_performance_snapshot.sharpe_ratio == 1.8


class TestDecision:
    """Tests for Decision model."""
    
    def test_create_no_action_decision(self):
        """Should create a NO_ACTION decision."""
        from adaptive_agent.models import Decision, DecisionType
        
        decision = Decision(
            decision_type=DecisionType.NO_ACTION,
            action="CONTINUE",
            confidence=1.0,
            reasoning="No signals",
        )
        
        assert decision.decision_type == DecisionType.NO_ACTION
        assert decision.executed == False
    
    def test_create_parameter_adjustment_decision(self):
        """Should create a PARAMETER_ADJUSTMENT decision."""
        from adaptive_agent.models import Decision, DecisionType
        
        decision = Decision(
            decision_type=DecisionType.PARAMETER_ADJUSTMENT,
            action="APPLY_RECOMMENDATION",
            confidence=0.85,
            parameter_name="stop_loss_pct",
            old_value=0.02,
            new_value=0.025,
            reasoning="Increased volatility",
        )
        
        assert decision.parameter_name == "stop_loss_pct"
        assert decision.old_value == 0.02
        assert decision.new_value == 0.025
    
    def test_confidence_validation(self):
        """Should validate confidence is between 0 and 1."""
        from adaptive_agent.models import Decision, DecisionType
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            Decision(
                decision_type=DecisionType.NO_ACTION,
                action="CONTINUE",
                confidence=1.5,  # Invalid
                reasoning="Test",
            )


class TestAgentState:
    """Tests for AgentState model."""
    
    def test_create_default_state(self):
        """Should create state with default values."""
        from adaptive_agent.models import AgentState, AgentMode
        
        state = AgentState()
        
        assert state.is_running == False
        assert state.mode == AgentMode.PAPER
        assert state.emergency_stop_active == False
        assert state.cycles_completed == 0
    
    def test_state_with_decisions(self):
        """Should store recent decisions."""
        from adaptive_agent.models import AgentState, Decision, DecisionType
        
        state = AgentState()
        
        decision = Decision(
            decision_type=DecisionType.NO_ACTION,
            action="CONTINUE",
            confidence=1.0,
            reasoning="Test",
        )
        
        state.recent_decisions.append(decision)
        
        assert len(state.recent_decisions) == 1


class TestPositionSnapshot:
    """Tests for PositionSnapshot model."""
    
    def test_create_position(self):
        """Should create a position snapshot."""
        from adaptive_agent.models import PositionSnapshot
        
        position = PositionSnapshot(
            symbol="TQQQ",
            quantity=100,
            avg_entry_price=44.50,
            current_price=45.50,
            unrealized_pnl=100.00,
            side="long",
        )
        
        assert position.symbol == "TQQQ"
        assert position.quantity == 100
        assert position.unrealized_pnl == 100.00


class TestCycleResult:
    """Tests for CycleResult model."""
    
    def test_create_cycle_result(self, sample_market_snapshot, sample_performance_snapshot):
        """Should create a cycle result."""
        from adaptive_agent.models import CycleResult
        
        now = datetime.now()
        
        result = CycleResult(
            cycle_number=1,
            started_at=now,
            completed_at=now,
            duration_ms=150.5,
            market_snapshot=sample_market_snapshot,
            performance_snapshot=sample_performance_snapshot,
            patterns_matched=3,
            recommendations_generated=1,
        )
        
        assert result.cycle_number == 1
        assert result.patterns_matched == 3
        assert result.errors == []
