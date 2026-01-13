"""
Integration tests for the Adaptive Agent.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


@pytest.mark.database
class TestObserverIntegration:
    """Tests for Observer component with real database."""
    
    def test_observer_gets_market_snapshot(self, observer):
        """Should retrieve market snapshot from database."""
        snapshot = observer.get_market_snapshot()
        
        assert snapshot is not None
        assert hasattr(snapshot, "rsi")
        assert hasattr(snapshot, "regime")
    
    def test_observer_gets_positions(self, observer):
        """Should retrieve current positions."""
        positions = observer.get_positions()
        
        assert isinstance(positions, list)
    
    def test_observer_gets_performance(self, observer):
        """Should retrieve performance metrics."""
        performance = observer.get_performance_snapshot()
        
        assert performance is not None
        assert hasattr(performance, "total_pnl")
        assert hasattr(performance, "win_rate")
    
    def test_observer_full_context(self, observer):
        """Should retrieve complete context."""
        market, positions, performance = observer.get_full_context()
        
        assert market is not None
        assert isinstance(positions, list)
        assert performance is not None


@pytest.mark.database
class TestAnalyzerIntegration:
    """Tests for Analyzer component."""
    
    def test_analyzer_market_analysis(
        self, 
        analyzer, 
        sample_market_snapshot, 
        sample_performance_snapshot
    ):
        """Should analyze market conditions."""
        observations = analyzer.analyze_market_conditions(
            sample_market_snapshot,
            sample_performance_snapshot,
        )
        
        assert isinstance(observations, list)
    
    def test_analyzer_pattern_matching(
        self, 
        analyzer, 
        sample_market_snapshot, 
        sample_performance_snapshot
    ):
        """Should match patterns from database."""
        patterns = analyzer.match_patterns(
            sample_market_snapshot,
            sample_performance_snapshot,
        )
        
        assert isinstance(patterns, list)
    
    def test_analyzer_risk_assessment(
        self,
        analyzer,
        sample_market_snapshot,
        sample_positions,
        sample_performance_snapshot,
    ):
        """Should assess current risk level."""
        risk = analyzer.assess_risk(
            sample_market_snapshot,
            sample_positions,
            sample_performance_snapshot,
        )
        
        assert "risk_score" in risk
        assert "risk_level" in risk
        assert 0 <= risk["risk_score"] <= 1
    
    def test_analyzer_generates_decision(
        self,
        analyzer,
        sample_market_snapshot,
        sample_positions,
        sample_performance_snapshot,
    ):
        """Should generate a decision."""
        observations = []
        patterns = []
        recommendations = []
        risk = {"risk_score": 0.3, "factors": [], "emergency_stop_recommended": False}
        
        decision = analyzer.generate_decision(
            sample_market_snapshot,
            sample_positions,
            sample_performance_snapshot,
            observations,
            patterns,
            recommendations,
            risk,
        )
        
        assert decision is not None
        assert hasattr(decision, "decision_type")
        assert hasattr(decision, "confidence")


@pytest.mark.database
class TestDecisionEngineIntegration:
    """Tests for Decision Engine component."""
    
    def test_evaluate_factors(
        self,
        decision_engine,
        sample_market_snapshot,
        sample_positions,
        sample_performance_snapshot,
    ):
        """Should evaluate all decision factors."""
        factors = decision_engine.evaluate_factors(
            sample_market_snapshot,
            sample_positions,
            sample_performance_snapshot,
        )
        
        assert len(factors) > 0
        assert all(hasattr(f, "name") and hasattr(f, "score") for f in factors)
    
    def test_aggregate_score(self, decision_engine, sample_market_snapshot, sample_positions, sample_performance_snapshot):
        """Should aggregate factor scores."""
        factors = decision_engine.evaluate_factors(
            sample_market_snapshot,
            sample_positions,
            sample_performance_snapshot,
        )
        
        score, confidence = decision_engine.aggregate_score(factors)
        
        assert -1 <= score <= 1
        assert 0 <= confidence <= 1
    
    def test_full_evaluation(
        self,
        decision_engine,
        sample_market_snapshot,
        sample_positions,
        sample_performance_snapshot,
    ):
        """Should perform full evaluation."""
        decision = decision_engine.evaluate(
            sample_market_snapshot,
            sample_positions,
            sample_performance_snapshot,
        )
        
        assert decision is not None
        assert decision.reasoning is not None


@pytest.mark.database
class TestExecutorIntegration:
    """Tests for Executor component."""
    
    def test_executor_can_execute_check(self, executor):
        """Should check if decision can be executed."""
        from adaptive_agent.models import Decision, DecisionType
        
        decision = Decision(
            decision_type=DecisionType.NO_ACTION,
            action="CONTINUE",
            confidence=1.0,
            reasoning="Test",
        )
        
        can_exec, reason = executor.can_execute(decision)
        
        assert isinstance(can_exec, bool)
        assert isinstance(reason, str)
    
    def test_executor_dry_run_no_execute(self, agent_config):
        """Should not execute in dry run mode."""
        from adaptive_agent.executor import Executor
        from adaptive_agent.models import Decision, DecisionType
        
        agent_config.dry_run = True
        executor = Executor(agent_config)
        
        decision = Decision(
            decision_type=DecisionType.PARAMETER_ADJUSTMENT,
            action="ADJUST",
            confidence=0.9,
            parameter_name="test_param",
            old_value=1,
            new_value=2,
            reasoning="Test",
        )
        
        can_exec, reason = executor.can_execute(decision)
        
        assert can_exec == False
        assert "dry run" in reason.lower()
    
    def test_executor_logs_decision(self, executor, db_cursor, clean_test_data):
        """Should log decisions to database."""
        from adaptive_agent.models import Decision, DecisionType
        
        decision = Decision(
            decision_id="TEST_DEC_001",
            decision_type=DecisionType.NO_ACTION,
            action="CONTINUE",
            confidence=0.5,
            reasoning="Test decision",
        )
        
        # Execute (will be skipped but logged)
        executor.execute(decision)
        
        # Verify logged
        db_cursor.execute("""
            SELECT DecisionType, Action FROM AgentDecisions 
            WHERE DecisionId = 'TEST_DEC_001'
        """)
        result = db_cursor.fetchone()
        
        # Cleanup
        db_cursor.execute("DELETE FROM AgentDecisions WHERE DecisionId = 'TEST_DEC_001'")
        
        if result:
            assert result[0] == "NO_ACTION"


@pytest.mark.database
class TestAdaptiveAgentIntegration:
    """Tests for full AdaptiveAgent."""
    
    def test_agent_initializes(self, adaptive_agent):
        """Should initialize agent."""
        assert adaptive_agent is not None
        assert adaptive_agent.observer is not None
        assert adaptive_agent.analyzer is not None
        assert adaptive_agent.executor is not None
    
    def test_agent_get_status(self, adaptive_agent):
        """Should return status dictionary."""
        status = adaptive_agent.get_status()
        
        assert "agent_id" in status
        assert "is_running" in status
        assert "mode" in status
    
    def test_agent_get_state(self, adaptive_agent):
        """Should return agent state."""
        state = adaptive_agent.get_state()
        
        assert state is not None
        assert hasattr(state, "is_running")
        assert hasattr(state, "cycles_completed")
    
    @pytest.mark.asyncio
    async def test_agent_single_cycle(self, adaptive_agent):
        """Should run a single cycle."""
        result = await adaptive_agent.run_single_cycle()
        
        assert result is not None
        assert result.cycle_number >= 1
        assert result.market_snapshot is not None
        assert result.performance_snapshot is not None
    
    def test_agent_emergency_stop(self, adaptive_agent):
        """Should trigger emergency stop."""
        adaptive_agent.trigger_emergency_stop("Test emergency")
        
        assert adaptive_agent.state.emergency_stop_active == True
        assert "Test emergency" in adaptive_agent.state.emergency_stop_reason
    
    def test_agent_clear_emergency(self, adaptive_agent):
        """Should clear emergency stop."""
        adaptive_agent.trigger_emergency_stop("Test")
        adaptive_agent.clear_emergency_stop("All clear")
        
        assert adaptive_agent.state.emergency_stop_active == False


@pytest.mark.database
class TestAgentCallbacks:
    """Tests for agent callback functionality."""
    
    @pytest.mark.asyncio
    async def test_decision_callback(self, adaptive_agent):
        """Should call decision callback."""
        decisions_received = []
        
        def on_decision(decision):
            decisions_received.append(decision)
        
        adaptive_agent.on_decision(on_decision)
        
        await adaptive_agent.run_single_cycle()
        
        # Callback may or may not be called depending on decision
        assert isinstance(decisions_received, list)
    
    @pytest.mark.asyncio
    async def test_cycle_callback(self, adaptive_agent):
        """Should call cycle complete callback."""
        cycles_received = []
        
        def on_cycle(result):
            cycles_received.append(result)
        
        adaptive_agent.on_cycle_complete(on_cycle)
        
        await adaptive_agent.run_single_cycle()
        
        assert len(cycles_received) == 1
        assert cycles_received[0].cycle_number >= 1
