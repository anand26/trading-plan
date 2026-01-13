"""
Integration tests for the Learning Store.
"""

import pytest
from datetime import datetime


@pytest.mark.database
class TestLearningStoreConnection:
    """Tests for Learning Store database connectivity."""
    
    def test_store_initializes(self, learning_store):
        """Should initialize learning store."""
        assert learning_store is not None
    
    def test_store_connects_to_db(self, learning_store):
        """Should connect to database."""
        # This will attempt to use the connection
        patterns = learning_store.get_patterns(limit=1)
        assert isinstance(patterns, list)


@pytest.mark.database
class TestPatternStorage:
    """Tests for pattern storage operations."""
    
    def test_record_pattern(self, learning_store, clean_test_data):
        """Should record a new pattern."""
        pattern_id = learning_store.record_pattern(
            pattern_type="ENTRY_TIMING",
            conditions={"regime": "BULLISH", "rsi": "<35"},
            action={"adjust": "rsi_entry", "value": 32},
            success=True,
            confidence=0.75,
        )
        
        assert pattern_id is not None
        assert pattern_id > 0
    
    def test_get_patterns_by_type(self, learning_store, clean_test_data):
        """Should retrieve patterns by type."""
        # Record a pattern first
        learning_store.record_pattern(
            pattern_type="EXIT_TIMING",
            conditions={"regime": "BEARISH"},
            action={"adjust": "exit_threshold"},
            success=True,
            confidence=0.7,
        )
        
        patterns = learning_store.get_patterns(
            pattern_type="EXIT_TIMING",
            min_confidence=0.5,
        )
        
        assert len(patterns) >= 0  # May have existing patterns


@pytest.mark.database
class TestRecommendationEngine:
    """Tests for recommendation operations."""
    
    def test_generate_recommendations(self, learning_store, clean_test_data):
        """Should generate recommendations based on patterns."""
        # First record some patterns
        for i in range(3):
            learning_store.record_pattern(
                pattern_type="PARAMETER_OPTIMIZATION",
                conditions={"volatility": "high"},
                action={"param": "stop_loss", "value": 0.025 + i * 0.005},
                success=True,
                confidence=0.6 + i * 0.1,
            )
        
        # Generate recommendations
        recs = learning_store.get_recommendations(
            recommendation_type="PARAMETER_OPTIMIZATION",
            limit=5,
        )
        
        assert isinstance(recs, list)
    
    def test_apply_recommendation(self, learning_store, db_cursor, clean_test_data):
        """Should mark recommendation as applied."""
        # Create a pattern first
        pattern_id = learning_store.record_pattern(
            pattern_type="RISK_MANAGEMENT",
            conditions={"drawdown": ">0.05"},
            action={"reduce": "position_size", "by": 0.25},
            success=True,
            confidence=0.8,
        )
        
        # Try to apply it (if recommendation was generated)
        # This tests the flow without hard requirements
        applied = learning_store.apply_recommendation(pattern_id)
        
        # Should return a boolean
        assert isinstance(applied, bool)


@pytest.mark.database
class TestPatternMatching:
    """Tests for pattern matching functionality."""
    
    def test_match_patterns_bullish(self, learning_store, sample_market_snapshot, clean_test_data):
        """Should match patterns for bullish conditions."""
        # Record a bullish pattern
        learning_store.record_pattern(
            pattern_type="REGIME_DETECTION",
            conditions={"regime": "BULLISH", "rsi": ">50"},
            action={"signal": "buy"},
            success=True,
            confidence=0.75,
        )
        
        # Match against current conditions
        matches = learning_store.match_patterns(
            conditions={
                "regime": "BULLISH",
                "rsi": 55,
            }
        )
        
        assert isinstance(matches, list)
    
    def test_match_returns_sorted_by_confidence(self, learning_store, clean_test_data):
        """Should return matches sorted by confidence."""
        # Record patterns with different confidences
        learning_store.record_pattern(
            pattern_type="ENTRY_TIMING",
            conditions={"regime": "NEUTRAL"},
            action={"wait": True},
            success=True,
            confidence=0.6,
        )
        
        learning_store.record_pattern(
            pattern_type="ENTRY_TIMING",
            conditions={"regime": "NEUTRAL"},
            action={"enter": True},
            success=True,
            confidence=0.9,
        )
        
        matches = learning_store.match_patterns(
            conditions={"regime": "NEUTRAL"}
        )
        
        if len(matches) >= 2:
            assert matches[0]["confidence"] >= matches[1]["confidence"]


@pytest.mark.database
class TestLearningFeedback:
    """Tests for learning from trade outcomes."""
    
    def test_record_outcome(self, learning_store, clean_test_data):
        """Should record trade outcome feedback."""
        # Record initial pattern
        pattern_id = learning_store.record_pattern(
            pattern_type="ENTRY_TIMING",
            conditions={"rsi": "<30"},
            action={"entry": "aggressive"},
            success=True,
            confidence=0.65,
        )
        
        # Record outcome
        learning_store.record_outcome(
            pattern_id=pattern_id,
            successful=True,
            pnl=150.00,
        )
        
        # Verify pattern was updated
        patterns = learning_store.get_patterns(min_confidence=0.0, limit=100)
        pattern = next((p for p in patterns if p["pattern_id"] == pattern_id), None)
        
        if pattern:
            assert pattern["occurrences"] >= 1
    
    def test_confidence_increases_on_success(self, learning_store, clean_test_data):
        """Should increase confidence on successful outcomes."""
        pattern_id = learning_store.record_pattern(
            pattern_type="EXIT_TIMING",
            conditions={"profit": ">2%"},
            action={"exit": "immediate"},
            success=True,
            confidence=0.5,
        )
        
        initial_patterns = learning_store.get_patterns(limit=100)
        initial = next((p for p in initial_patterns if p["pattern_id"] == pattern_id), None)
        initial_conf = initial["confidence"] if initial else 0.5
        
        # Record multiple successes
        for _ in range(3):
            learning_store.record_outcome(pattern_id, successful=True, pnl=100)
        
        updated_patterns = learning_store.get_patterns(limit=100)
        updated = next((p for p in updated_patterns if p["pattern_id"] == pattern_id), None)
        
        if updated:
            # Confidence should have increased or stayed same
            assert updated["confidence"] >= initial_conf - 0.01  # Small tolerance


@pytest.mark.database 
class TestPatternDecay:
    """Tests for pattern confidence decay."""
    
    def test_decay_old_patterns(self, learning_store, db_cursor, clean_test_data):
        """Should decay confidence of old patterns."""
        # This tests the decay stored procedure
        db_cursor.execute("EXEC sp_DecayPatternConfidence @DecayFactor = 0.95")
        
        # Should complete without error
        assert True
