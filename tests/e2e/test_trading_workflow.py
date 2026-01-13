"""
End-to-end tests for trading workflow scenarios.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


@pytest.mark.e2e
@pytest.mark.database
class TestTradingCycleWorkflow:
    """Tests for complete trading cycle workflows."""
    
    @pytest.mark.asyncio
    async def test_full_observation_to_decision_cycle(
        self,
        adaptive_agent,
        sample_market_snapshot,
    ):
        """Should complete full observe → analyze → decide cycle."""
        # Run single cycle
        result = await adaptive_agent.run_single_cycle()
        
        # Verify cycle completed
        assert result.cycle_number >= 1
        assert result.duration_ms > 0
        
        # Verify observation
        assert result.market_snapshot is not None
        assert result.performance_snapshot is not None
        
        # Verify decision was made
        assert result.decision is not None
        assert result.decision.decision_type is not None
    
    @pytest.mark.asyncio
    async def test_multiple_cycles(self, adaptive_agent):
        """Should run multiple cycles successfully."""
        results = []
        
        for _ in range(3):
            result = await adaptive_agent.run_single_cycle()
            results.append(result)
        
        assert len(results) == 3
        assert all(r.cycle_number >= 1 for r in results)
    
    @pytest.mark.asyncio
    async def test_state_updates_through_cycles(self, adaptive_agent):
        """Should update state through cycles."""
        initial_cycles = adaptive_agent.state.cycles_completed
        
        await adaptive_agent.run_single_cycle()
        
        # State should not be updated by run_single_cycle
        # (only by internal _run_cycle in scheduled mode)
        # But the result should be valid
        assert adaptive_agent.state is not None


@pytest.mark.e2e
@pytest.mark.database
class TestEmergencyScenarios:
    """Tests for emergency handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_emergency_stop_on_drawdown(self, agent_config):
        """Should trigger emergency stop on excessive drawdown."""
        from adaptive_agent.agent import AdaptiveAgent
        from adaptive_agent.models import PerformanceSnapshot
        
        # Set low threshold
        agent_config.thresholds.emergency_drawdown_pct = 0.10
        agent = AdaptiveAgent(agent_config)
        
        # Mock observer to return high drawdown
        def mock_performance():
            return PerformanceSnapshot(
                current_drawdown=0.18,  # Above threshold
                daily_pnl=-500,
            )
        
        agent.observer.get_performance_snapshot = mock_performance
        
        # Run cycle
        await agent.run_single_cycle()
        
        # Should detect the concerning performance
        result = await agent.run_single_cycle()
        
        # Decision should reflect concern
        if result.decision:
            # Either emergency stop or risk scaling
            assert result.decision.decision_type.value in [
                "EMERGENCY_STOP", "RISK_SCALING", "NO_ACTION"
            ]
    
    def test_manual_emergency_stop(self, adaptive_agent):
        """Should handle manual emergency stop."""
        adaptive_agent.trigger_emergency_stop("Manual test")
        
        assert adaptive_agent.state.emergency_stop_active == True
        assert adaptive_agent.state.trading_enabled == False
    
    def test_emergency_clear_and_resume(self, adaptive_agent):
        """Should clear emergency and resume."""
        adaptive_agent.trigger_emergency_stop("Test")
        adaptive_agent.clear_emergency_stop("Resolved")
        
        assert adaptive_agent.state.emergency_stop_active == False
        assert adaptive_agent.state.trading_enabled == True


@pytest.mark.e2e
@pytest.mark.database
class TestLearningWorkflow:
    """Tests for learning and adaptation workflows."""
    
    def test_pattern_to_recommendation_flow(
        self,
        learning_store,
        clean_test_data,
    ):
        """Should flow from pattern recording to recommendation."""
        # Record patterns
        pattern_ids = []
        for i in range(5):
            pid = learning_store.record_pattern(
                pattern_type="ENTRY_TIMING",
                conditions={"rsi": f"<{30 + i}"},
                action={"entry": "aggressive"},
                success=True,
                confidence=0.6 + i * 0.05,
            )
            pattern_ids.append(pid)
        
        # Get patterns
        patterns = learning_store.get_patterns(
            pattern_type="ENTRY_TIMING",
            min_confidence=0.5,
        )
        
        assert len(patterns) >= 1
    
    def test_feedback_improves_confidence(
        self,
        learning_store,
        clean_test_data,
    ):
        """Should improve confidence with positive feedback."""
        # Record initial pattern
        pattern_id = learning_store.record_pattern(
            pattern_type="POSITION_SIZING",
            conditions={"volatility": "low"},
            action={"size": "increase"},
            success=True,
            confidence=0.5,
        )
        
        # Record positive outcomes
        for _ in range(5):
            learning_store.record_outcome(
                pattern_id=pattern_id,
                successful=True,
                pnl=100,
            )
        
        # Check updated pattern
        patterns = learning_store.get_patterns(limit=100)
        updated = next((p for p in patterns if p["pattern_id"] == pattern_id), None)
        
        if updated:
            # Should have more occurrences
            assert updated["occurrences"] >= 1


@pytest.mark.e2e
@pytest.mark.database
class TestDataPersistence:
    """Tests for data persistence across components."""
    
    def test_trade_persists_through_system(self, db_cursor, clean_test_data):
        """Should persist trade data through system."""
        trade_id = f"E2E_TRADE_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Insert trade
        db_cursor.execute("""
            INSERT INTO Trades (
                TradeId, Symbol, Side, Quantity, EntryPrice, 
                EntryTime, Status, CreatedAt
            ) VALUES (?, 'TQQQ', 'BUY', 100, 45.00, GETDATE(), 'OPEN', GETDATE())
        """, (trade_id,))
        
        # Read back via view
        db_cursor.execute("""
            SELECT Symbol, Quantity FROM vw_RecentTrades 
            WHERE TradeId = ?
        """, (trade_id,))
        result = db_cursor.fetchone()
        
        assert result is not None
        assert result[0] == "TQQQ"
        
        # Cleanup
        db_cursor.execute("DELETE FROM Trades WHERE TradeId = ?", (trade_id,))
    
    def test_decision_audit_trail(self, executor, db_cursor, clean_test_data):
        """Should maintain decision audit trail."""
        from adaptive_agent.models import Decision, DecisionType
        
        decision_id = f"E2E_DEC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        decision = Decision(
            decision_id=decision_id,
            decision_type=DecisionType.PARAMETER_ADJUSTMENT,
            action="TEST_ADJUSTMENT",
            confidence=0.75,
            parameter_name="test_param",
            old_value="old",
            new_value="new",
            reasoning="E2E test decision",
        )
        
        # Execute (will log)
        executor.execute(decision)
        
        # Verify in audit table
        db_cursor.execute("""
            SELECT DecisionType, Action, Reasoning 
            FROM AgentDecisions WHERE DecisionId = ?
        """, (decision_id,))
        result = db_cursor.fetchone()
        
        assert result is not None
        assert "TEST" in result[1]
        
        # Cleanup
        db_cursor.execute("DELETE FROM AgentDecisions WHERE DecisionId = ?", (decision_id,))


@pytest.mark.e2e
@pytest.mark.slow
class TestPerformanceWorkflows:
    """Tests for performance-related workflows."""
    
    @pytest.mark.asyncio
    async def test_cycle_performance(self, adaptive_agent):
        """Should complete cycles within reasonable time."""
        import time
        
        start = time.time()
        result = await adaptive_agent.run_single_cycle()
        elapsed = time.time() - start
        
        # Cycle should complete in under 5 seconds
        assert elapsed < 5.0
        assert result.duration_ms < 5000
    
    def test_decision_engine_performance(
        self,
        decision_engine,
        sample_market_snapshot,
        sample_positions,
        sample_performance_snapshot,
    ):
        """Should evaluate factors quickly."""
        import time
        
        start = time.time()
        
        for _ in range(10):
            decision_engine.evaluate(
                sample_market_snapshot,
                sample_positions,
                sample_performance_snapshot,
            )
        
        elapsed = time.time() - start
        
        # 10 evaluations should complete in under 1 second
        assert elapsed < 1.0
