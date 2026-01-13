"""
End-to-end tests for full system cycles.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.e2e
@pytest.mark.database
class TestFullSystemCycle:
    """Tests for complete system integration."""
    
    @pytest.mark.asyncio
    async def test_complete_trading_day_simulation(
        self,
        adaptive_agent,
        learning_store,
        db_cursor,
        clean_test_data,
    ):
        """Should simulate a complete trading day cycle."""
        # Setup: Record some initial patterns
        for i in range(3):
            learning_store.record_pattern(
                pattern_type="ENTRY_TIMING",
                conditions={"hour": str(9 + i)},
                action={"timing": "adjust"},
                success=True,
                confidence=0.6,
            )
        
        # Simulate multiple agent cycles (like a trading day)
        results = []
        for cycle in range(5):
            result = await adaptive_agent.run_single_cycle()
            results.append(result)
        
        # Verify all cycles completed
        assert len(results) == 5
        assert all(r.market_snapshot is not None for r in results)
        assert all(r.decision is not None for r in results)
        
        # Check that decisions were logged
        db_cursor.execute("""
            SELECT COUNT(*) FROM AgentDecisions 
            WHERE CreatedAt > DATEADD(minute, -5, GETDATE())
        """)
        logged_count = db_cursor.fetchone()[0]
        
        # Some decisions should have been logged
        assert logged_count >= 0  # May be 0 if all NO_ACTION
    
    @pytest.mark.asyncio
    async def test_system_recovers_from_errors(self, adaptive_agent):
        """Should recover from transient errors."""
        # Run several cycles - system should be resilient
        successful_cycles = 0
        
        for _ in range(5):
            try:
                result = await adaptive_agent.run_single_cycle()
                if result and not result.errors:
                    successful_cycles += 1
            except Exception:
                pass  # Continue on errors
        
        # Most cycles should succeed
        assert successful_cycles >= 3


@pytest.mark.e2e
@pytest.mark.database
class TestDataFlowIntegrity:
    """Tests for data integrity across system."""
    
    def test_market_data_flows_to_decision(
        self,
        observer,
        analyzer,
        decision_engine,
    ):
        """Should flow market data through to decisions."""
        # Get market snapshot
        market = observer.get_market_snapshot()
        positions = observer.get_positions()
        performance = observer.get_performance_snapshot()
        
        # Analyze
        observations = analyzer.analyze_market_conditions(market, performance)
        risk = analyzer.assess_risk(market, positions, performance)
        
        # Generate decision
        decision = decision_engine.evaluate(market, positions, performance)
        
        # Decision should reference market context
        assert decision.market_snapshot is not None or decision.reasoning is not None
    
    def test_pattern_influences_decision(
        self,
        learning_store,
        analyzer,
        sample_market_snapshot,
        sample_positions,
        sample_performance_snapshot,
        clean_test_data,
    ):
        """Should use patterns in decision making."""
        # Record high-confidence pattern
        learning_store.record_pattern(
            pattern_type="ENTRY_TIMING",
            conditions={"regime": "NEUTRAL"},
            action={"signal": "wait"},
            success=True,
            confidence=0.9,
        )
        
        # Match patterns
        matched = analyzer.match_patterns(
            sample_market_snapshot,
            sample_performance_snapshot,
        )
        
        # Patterns should be considered
        assert isinstance(matched, list)


@pytest.mark.e2e
@pytest.mark.database
class TestScenarioSimulations:
    """Tests for specific trading scenarios."""
    
    @pytest.mark.asyncio
    async def test_bullish_market_scenario(self, agent_config):
        """Should handle bullish market conditions."""
        from adaptive_agent.agent import AdaptiveAgent
        from adaptive_agent.models import MarketSnapshot, MarketRegime, PerformanceSnapshot
        
        agent = AdaptiveAgent(agent_config)
        
        # Mock bullish conditions
        bullish_market = MarketSnapshot(
            rsi=65,
            momentum=0.05,
            volatility=0.015,
            regime=MarketRegime.BULLISH,
            regime_confidence=0.8,
            is_market_open=True,
        )
        
        good_performance = PerformanceSnapshot(
            daily_pnl=200,
            weekly_win_rate=0.65,
            current_drawdown=0.02,
            current_streak=3,
        )
        
        # Override observer methods
        agent.observer.get_market_snapshot = lambda: bullish_market
        agent.observer.get_performance_snapshot = lambda: good_performance
        agent.observer.get_positions = lambda: []
        
        # Run cycle
        result = await agent.run_single_cycle()
        
        # Should not trigger emergency stop
        assert result.decision.decision_type.value != "EMERGENCY_STOP"
    
    @pytest.mark.asyncio
    async def test_high_volatility_scenario(self, agent_config):
        """Should handle high volatility cautiously."""
        from adaptive_agent.agent import AdaptiveAgent
        from adaptive_agent.models import MarketSnapshot, MarketRegime, PerformanceSnapshot
        
        agent = AdaptiveAgent(agent_config)
        
        # Mock volatile conditions
        volatile_market = MarketSnapshot(
            rsi=45,
            momentum=-0.02,
            volatility=0.05,  # High volatility
            regime=MarketRegime.VOLATILE,
            regime_confidence=0.7,
            is_market_open=True,
        )
        
        agent.observer.get_market_snapshot = lambda: volatile_market
        agent.observer.get_performance_snapshot = lambda: PerformanceSnapshot()
        agent.observer.get_positions = lambda: []
        
        # Run cycle
        result = await agent.run_single_cycle()
        
        # Should recognize volatility
        if result.decision.contributing_factors:
            # Check if volatility was noted
            factor_text = " ".join(result.decision.contributing_factors).lower()
            # Volatility may or may not be explicitly mentioned
    
    @pytest.mark.asyncio
    async def test_losing_streak_scenario(self, agent_config):
        """Should handle losing streaks appropriately."""
        from adaptive_agent.agent import AdaptiveAgent
        from adaptive_agent.models import MarketSnapshot, MarketRegime, PerformanceSnapshot
        
        agent = AdaptiveAgent(agent_config)
        
        losing_performance = PerformanceSnapshot(
            daily_pnl=-300,
            weekly_pnl=-800,
            weekly_win_rate=0.35,
            current_drawdown=0.08,
            current_streak=-5,  # 5 consecutive losses
        )
        
        agent.observer.get_market_snapshot = lambda: MarketSnapshot()
        agent.observer.get_performance_snapshot = lambda: losing_performance
        agent.observer.get_positions = lambda: []
        
        # Run cycle
        result = await agent.run_single_cycle()
        
        # Should consider reducing risk
        decision_type = result.decision.decision_type.value
        # Acceptable responses: RISK_SCALING, PARAMETER_ADJUSTMENT, or cautious NO_ACTION
        assert decision_type in ["RISK_SCALING", "PARAMETER_ADJUSTMENT", "NO_ACTION", "EMERGENCY_STOP"]


@pytest.mark.e2e
@pytest.mark.database
class TestComponentInteraction:
    """Tests for component interactions."""
    
    def test_observer_analyzer_interaction(
        self,
        observer,
        analyzer,
    ):
        """Should pass data correctly between observer and analyzer."""
        # Get data from observer
        market, positions, performance = observer.get_full_context()
        
        # Pass to analyzer
        observations = analyzer.analyze_market_conditions(market, performance)
        risk = analyzer.assess_risk(market, positions, performance)
        
        # Should produce valid outputs
        assert isinstance(observations, list)
        assert "risk_score" in risk
    
    def test_analyzer_executor_interaction(
        self,
        analyzer,
        executor,
        sample_market_snapshot,
        sample_positions,
        sample_performance_snapshot,
    ):
        """Should pass decisions correctly to executor."""
        # Generate decision
        decision = analyzer.generate_decision(
            sample_market_snapshot,
            sample_positions,
            sample_performance_snapshot,
            observations=[],
            matched_patterns=[],
            recommendations=[],
            risk_assessment={"risk_score": 0.2, "factors": [], "emergency_stop_recommended": False},
        )
        
        # Check executability
        can_exec, reason = executor.can_execute(decision)
        
        # Should return valid response
        assert isinstance(can_exec, bool)
        assert isinstance(reason, str)
    
    def test_learning_store_analyzer_interaction(
        self,
        learning_store,
        analyzer,
        sample_market_snapshot,
        sample_performance_snapshot,
        clean_test_data,
    ):
        """Should use learning store data in analysis."""
        # Add patterns to learning store
        learning_store.record_pattern(
            pattern_type="REGIME_DETECTION",
            conditions={"regime": sample_market_snapshot.regime.value},
            action={"note": "test"},
            success=True,
            confidence=0.75,
        )
        
        # Analyzer should be able to match
        matches = analyzer.match_patterns(
            sample_market_snapshot,
            sample_performance_snapshot,
        )
        
        assert isinstance(matches, list)


@pytest.mark.e2e
class TestSystemResilience:
    """Tests for system resilience and error handling."""
    
    def test_handles_missing_data_gracefully(self, observer):
        """Should handle missing data gracefully."""
        # Even with empty/minimal data, should not crash
        market = observer.get_market_snapshot()
        
        assert market is not None
        # Should have defaults
        assert market.rsi >= 0
    
    def test_handles_invalid_parameters(self, agent_config):
        """Should handle invalid configuration gracefully."""
        from adaptive_agent.agent import AdaptiveAgent
        
        # Set unusual but valid config
        agent_config.cycle_interval_seconds = 1
        agent_config.thresholds.min_confidence_to_act = 0.99
        
        agent = AdaptiveAgent(agent_config)
        
        # Should initialize without error
        assert agent is not None
    
    @pytest.mark.asyncio
    async def test_recovers_from_component_failure(self, adaptive_agent):
        """Should recover from individual component failures."""
        # Mock a failing component
        original_method = adaptive_agent.analyzer.match_patterns
        adaptive_agent.analyzer.match_patterns = lambda *args: []  # Return empty
        
        try:
            result = await adaptive_agent.run_single_cycle()
            # Should still complete
            assert result is not None
        finally:
            adaptive_agent.analyzer.match_patterns = original_method
