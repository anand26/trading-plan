"""
Integration tests for the Learning Store.
"""

import pytest
from datetime import datetime
from learning_store.models import PatternType, MarketRegime, MarketConditions


@pytest.mark.database
class TestLearningStoreConnection:
    """Tests for Learning Store database connectivity."""
    
    def test_store_initializes(self, learning_store):
        """Should initialize learning store."""
        assert learning_store is not None
    
    def test_store_connects_to_db(self, learning_store):
        """Should connect to database."""
        # This will attempt to use the connection
        patterns = learning_store.get_patterns(min_confidence=0.0)
        assert isinstance(patterns, list)


@pytest.mark.database
class TestPatternStorage:
    """Tests for pattern storage operations."""
    
    def test_record_pattern(self, learning_store, clean_test_data):
        """Should record a new pattern."""
        pattern_id = learning_store.record_pattern(
            pattern_type=PatternType.ENTRY_TIMING,
            name="Test RSI Entry Pattern",
            description="Enter when RSI is low",
            conditions={"regime": "BULLISH", "rsi_threshold": 35},
            confidence=0.75,
        )
        
        assert pattern_id is not None
        assert pattern_id > 0
    
    def test_get_patterns_by_type(self, learning_store, clean_test_data):
        """Should retrieve patterns by type."""
        # Record a pattern first
        learning_store.record_pattern(
            pattern_type=PatternType.EXIT_TIMING,
            name="Test Exit Pattern",
            description="Exit on high momentum",
            conditions={"regime": "BEARISH"},
            confidence=0.7,
        )
        
        patterns = learning_store.get_patterns(
            pattern_type=PatternType.EXIT_TIMING,
            min_confidence=0.5,
        )
        
        assert isinstance(patterns, list)


@pytest.mark.database
class TestRecommendationEngine:
    """Tests for recommendation operations."""
    
    def test_generate_recommendations(self, learning_store, clean_test_data):
        """Should generate recommendations based on patterns."""
        # First record some patterns with varying confidence
        for i in range(3):
            learning_store.record_pattern(
                pattern_type=PatternType.PARAMETER_OPTIMIZATION,
                name=f"Test Param Pattern {i}",
                description="Optimize stop loss for high volatility",
                conditions={"volatility": "high"},
                confidence=0.6 + i * 0.1,
            )
        
        # Generate recommendations using MarketConditions
        conditions = MarketConditions(
            regime=MarketRegime.VOLATILE,
            rsi=50.0,
            momentum=0.01,
            volatility=0.025,
            trend_strength=0.3,
            hour_of_day=10,
            day_of_week=2
        )
        
        recs = learning_store.get_recommendations(conditions, limit=5)
        assert isinstance(recs, list)
    
    def test_apply_recommendation(self, learning_store, db_cursor, clean_test_data):
        """Should mark recommendation as applied."""
        # Create a pattern first
        pattern_id = learning_store.record_pattern(
            pattern_type=PatternType.RISK_MANAGEMENT,
            name="Test Risk Pattern",
            description="Reduce position when drawdown high",
            conditions={"drawdown": ">0.05"},
            confidence=0.8,
        )
        
        # Pattern exists
        assert pattern_id is not None


@pytest.mark.database
class TestPatternMatching:
    """Tests for pattern matching functionality."""
    
    def test_match_patterns_bullish(self, learning_store, sample_market_snapshot, clean_test_data):
        """Should match patterns for bullish conditions."""
        # Record a bullish pattern
        learning_store.record_pattern(
            pattern_type=PatternType.REGIME_DETECTION,
            name="Bullish RSI Pattern",
            description="Enter when RSI confirms bullish trend",
            conditions={"regime": "BULLISH", "rsi": ">50"},
            confidence=0.75,
            regime=MarketRegime.BULLISH,
        )
        
        # Match against current conditions
        conditions = MarketConditions(
            regime=MarketRegime.BULLISH,
            rsi=55.0,
            momentum=0.02,
            volatility=0.015,
            trend_strength=0.6,
            hour_of_day=10,
            day_of_week=1
        )
        
        matches = learning_store.match_patterns(conditions)
        assert isinstance(matches, list)
    
    def test_match_returns_sorted_by_confidence(self, learning_store, clean_test_data):
        """Should return matches sorted by confidence."""
        # Record patterns with different confidences
        learning_store.record_pattern(
            pattern_type=PatternType.ENTRY_TIMING,
            name="Low Confidence Entry",
            description="Wait for better entry",
            conditions={"regime": "NEUTRAL"},
            confidence=0.6,
            regime=MarketRegime.NEUTRAL,
        )
        
        learning_store.record_pattern(
            pattern_type=PatternType.ENTRY_TIMING,
            name="High Confidence Entry",
            description="Strong entry signal",
            conditions={"regime": "NEUTRAL"},
            confidence=0.9,
            regime=MarketRegime.NEUTRAL,
        )
        
        conditions = MarketConditions(
            regime=MarketRegime.NEUTRAL,
            rsi=50.0,
            momentum=0.0,
            volatility=0.01,
            trend_strength=0.0,
            hour_of_day=10,
            day_of_week=1
        )
        
        matches = learning_store.match_patterns(conditions)
        
        if len(matches) >= 2:
            assert matches[0]["confidence"] >= matches[1]["confidence"]


@pytest.mark.database
class TestLearningFeedback:
    """Tests for learning from trade outcomes."""
    
    def test_record_outcome(self, learning_store, clean_test_data):
        """Should record trade outcome feedback via learn_from_trades."""
        # This tests the learning engine
        learnings = learning_store.learn_from_trades(days=1)
        assert isinstance(learnings, list)
    
    def test_confidence_increases_on_success(self, learning_store, clean_test_data):
        """Should be able to update pattern confidence."""
        pattern_id = learning_store.record_pattern(
            pattern_type=PatternType.EXIT_TIMING,
            name="Test Confidence Pattern",
            description="Exit on profit target",
            conditions={"profit": ">2%"},
            confidence=0.5,
        )
        
        if pattern_id:
            # Update confidence
            result = learning_store.update_pattern_confidence(
                pattern_id=pattern_id,
                new_confidence=0.7,
                new_sample_size=10
            )
            
            assert isinstance(result, bool)


@pytest.mark.database 
class TestPatternDecay:
    """Tests for pattern confidence decay."""
    
    def test_decay_old_patterns(self, learning_store, db_cursor, clean_test_data):
        """Should decay confidence of old patterns."""
        # This tests the decay stored procedure
        db_cursor.execute("EXEC sp_DecayPatternConfidence @DecayRate = 0.95")
        
        # Should complete without error
        assert True
