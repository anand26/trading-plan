"""
Main Learning Store interface.

Unified API for pattern recognition, learning, and recommendations.
"""

from datetime import datetime
from typing import Optional, Any

from .models import (
    Pattern, PatternType, Learning, LearningType,
    Recommendation, MarketConditions, MarketRegime,
    LearningSnapshot, ParameterPerformance
)
from .patterns import PatternRecognizer
from .learner import AdaptiveLearner
from .recommender import RecommendationEngine
from .database import (
    get_patterns, save_pattern, update_pattern,
    save_learning, get_learnings,
    get_parameter_performance, update_parameter_performance,
    get_db
)
from .config import learning_config


class LearningStore:
    """
    Main interface for the Learning Store intelligence layer.
    
    Provides a unified API for:
    - Pattern recognition and storage
    - Adaptive learning from trade outcomes
    - Generating parameter recommendations
    - Tracking learning history
    
    Example:
        store = LearningStore()
        
        # Analyze trades and learn
        learnings = store.learn_from_trades(days=7)
        
        # Get recommendations for current conditions
        conditions = MarketConditions(
            regime=MarketRegime.BULLISH,
            rsi=35.0,
            momentum=0.02,
            volatility=0.015,
            trend_strength=0.6,
            hour_of_day=10,
            day_of_week=1
        )
        recommendations = store.get_recommendations(conditions)
        
        # Record a pattern
        store.record_pattern(
            pattern_type=PatternType.ENTRY_TIMING,
            name="Morning Dip Buy",
            description="Buy TQQQ on morning RSI dip",
            conditions={"rsi_oversold": True, "entry_hour": 10},
            confidence=0.75
        )
    """
    
    def __init__(self):
        self._pattern_recognizer = PatternRecognizer()
        self._learner = AdaptiveLearner()
        self._recommender = RecommendationEngine()
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        Initialize the learning store and verify database connection.
        
        Returns True if initialization successful.
        """
        db = get_db()
        if not db.is_connected:
            db.connect()
        
        self._initialized = db.is_connected
        return self._initialized
    
    @property
    def is_initialized(self) -> bool:
        """Check if the store is initialized."""
        return self._initialized
    
    # ==================== Pattern Operations ====================
    
    def record_pattern(
        self,
        pattern_type: PatternType,
        name: str,
        description: str,
        conditions: dict[str, Any],
        confidence: float,
        expected_outcome: str = "PROFITABLE",
        regime: Optional[MarketRegime] = None
    ) -> Optional[int]:
        """
        Record a new pattern in the store.
        
        Returns the pattern ID if successful.
        """
        pattern = Pattern(
            pattern_type=pattern_type,
            name=name,
            description=description,
            conditions=conditions,
            expected_outcome=expected_outcome,
            confidence=confidence,
            regime=regime
        )
        
        return save_pattern(pattern)
    
    def get_patterns(
        self,
        pattern_type: Optional[PatternType] = None,
        regime: Optional[MarketRegime] = None,
        min_confidence: float = 0.3,
        active_only: bool = True
    ) -> list[Pattern]:
        """Get patterns matching the specified criteria."""
        return get_patterns(
            pattern_type=pattern_type,
            regime=regime,
            min_confidence=min_confidence,
            active_only=active_only
        )
    
    def update_pattern_confidence(
        self,
        pattern_id: int,
        new_confidence: float,
        new_sample_size: Optional[int] = None
    ) -> bool:
        """Update a pattern's confidence score."""
        patterns = get_patterns(active_only=False)
        pattern = next((p for p in patterns if p.pattern_id == pattern_id), None)
        
        if not pattern:
            return False
        
        pattern.confidence = new_confidence
        if new_sample_size is not None:
            pattern.sample_size = new_sample_size
        
        return update_pattern(pattern)
    
    def analyze_patterns(self, days: int = 30) -> list[Pattern]:
        """
        Analyze recent trades to discover or update patterns.
        
        Returns list of discovered/updated patterns.
        """
        return self._pattern_recognizer.analyze_trades(days=days)
    
    def match_patterns(self, conditions: MarketConditions) -> list[dict]:
        """
        Find patterns that match current market conditions.
        
        Returns list of matches with scores.
        """
        matches = self._pattern_recognizer.match_conditions(conditions)
        return [
            {
                "pattern_id": m.pattern.pattern_id,
                "name": m.pattern.name,
                "type": m.pattern.pattern_type.value,
                "match_score": m.match_score,
                "confidence": m.pattern.confidence,
                "win_rate": m.pattern.win_rate,
                "matching_conditions": m.matching_conditions
            }
            for m in matches
        ]
    
    # ==================== Learning Operations ====================
    
    def learn_from_trades(self, days: int = 7) -> list[Learning]:
        """
        Analyze recent trades and generate learnings.
        
        Returns list of learning events generated.
        """
        return self._learner.learn_from_trades(days=days)
    
    def record_learning(
        self,
        learning_type: LearningType,
        description: str,
        confidence_score: float,
        source: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        related_pattern_id: Optional[int] = None,
        metadata: Optional[dict] = None
    ) -> Optional[int]:
        """
        Record a learning event manually.
        
        Returns the learning ID if successful.
        """
        learning = Learning(
            learning_type=learning_type,
            description=description,
            old_value=old_value,
            new_value=new_value,
            confidence_score=confidence_score,
            source=source,
            related_pattern_id=related_pattern_id,
            metadata=metadata or {}
        )
        
        return save_learning(learning)
    
    def get_learning_history(
        self,
        learning_type: Optional[LearningType] = None,
        days: int = 30,
        limit: int = 100
    ) -> list[Learning]:
        """Get recent learning events."""
        return get_learnings(
            learning_type=learning_type,
            days=days,
            limit=limit
        )
    
    def get_learning_summary(self, days: int = 30) -> dict:
        """Get a summary of learning activity."""
        return self._learner.get_learning_summary(days=days)
    
    # ==================== Recommendation Operations ====================
    
    def get_recommendations(
        self,
        conditions: MarketConditions,
        limit: int = 5
    ) -> list[Recommendation]:
        """
        Get parameter recommendations for current conditions.
        
        Returns list of recommendations sorted by confidence.
        """
        return self._recommender.get_recommendations(
            conditions=conditions,
            limit=limit
        )
    
    def suggest_corrections(
        self,
        recent_performance: dict,
        current_params: dict
    ) -> list[Recommendation]:
        """
        Suggest corrections based on recent underperformance.
        
        Args:
            recent_performance: Dict with win_rate, avg_pnl, trade_count
            current_params: Dict of current parameter values
        
        Returns:
            List of correction recommendations
        """
        return self._recommender.suggest_corrections(
            recent_performance=recent_performance,
            current_params=current_params
        )
    
    def get_pending_recommendations(
        self,
        parameter_name: Optional[str] = None,
        regime: Optional[MarketRegime] = None,
        min_confidence: float = 0.5
    ) -> list[Recommendation]:
        """Get recommendations that haven't been applied yet."""
        return self._recommender.get_pending_recommendations(
            parameter_name=parameter_name,
            regime=regime,
            min_confidence=min_confidence
        )
    
    def apply_recommendation(
        self,
        recommendation: Recommendation,
        outcome: Optional[str] = None
    ) -> bool:
        """Mark a recommendation as applied."""
        return self._recommender.apply_recommendation(
            recommendation=recommendation,
            outcome=outcome
        )
    
    # ==================== Parameter Performance ====================
    
    def get_parameter_performance(
        self,
        parameter_name: str
    ) -> list[ParameterPerformance]:
        """Get performance data for a parameter across different values."""
        return get_parameter_performance(parameter_name)
    
    def update_parameter_performance(
        self,
        parameter_name: str,
        parameter_value: Any,
        trade_count: int,
        win_rate: float,
        avg_pnl: float,
        total_pnl: float,
        regime: Optional[MarketRegime] = None
    ) -> bool:
        """Update performance tracking for a parameter value."""
        perf = ParameterPerformance(
            parameter_name=parameter_name,
            parameter_value=parameter_value,
            regime=regime,
            trade_count=trade_count,
            win_rate=win_rate,
            avg_pnl=avg_pnl,
            total_pnl=total_pnl
        )
        
        return update_parameter_performance(perf)
    
    def suggest_parameter_adjustment(
        self,
        parameter_name: str,
        current_value: str,
        regime: Optional[MarketRegime] = None
    ) -> Optional[tuple[str, float]]:
        """
        Suggest a parameter adjustment based on learning.
        
        Returns (suggested_value, confidence) or None.
        """
        return self._learner.suggest_parameter_adjustment(
            parameter_name=parameter_name,
            current_value=current_value,
            regime=regime
        )
    
    # ==================== Snapshots ====================
    
    def create_snapshot(self) -> LearningSnapshot:
        """
        Create a point-in-time snapshot of the learning state.
        
        Useful for tracking progress over time.
        """
        patterns = self.get_patterns(active_only=True)
        learnings = self.get_learning_history(days=7)
        
        active_patterns = [p for p in patterns if p.is_active]
        avg_confidence = (
            sum(p.confidence for p in active_patterns) / len(active_patterns)
            if active_patterns else 0
        )
        
        # Get top patterns by win rate
        top_patterns = sorted(
            active_patterns,
            key=lambda p: p.win_rate * p.confidence,
            reverse=True
        )[:5]
        
        return LearningSnapshot(
            timestamp=datetime.now(),
            total_patterns=len(patterns),
            active_patterns=len(active_patterns),
            total_learnings=len(learnings),
            avg_pattern_confidence=avg_confidence,
            top_patterns=top_patterns,
            recent_learnings=learnings[:10],
            metadata={
                "learning_config": {
                    "min_confidence": learning_config.min_confidence_threshold,
                    "decay_rate": learning_config.pattern_decay_rate,
                    "min_samples": learning_config.recommendation_min_samples
                }
            }
        )
    
    # ==================== Utilities ====================
    
    def health_check(self) -> dict:
        """
        Check the health of the learning store.
        
        Returns dict with health status.
        """
        db = get_db()
        
        health = {
            "status": "healthy" if db.is_connected else "unhealthy",
            "database_connected": db.is_connected,
            "timestamp": datetime.now().isoformat()
        }
        
        if db.is_connected:
            # Check table counts
            tables = {
                "patterns": "Patterns",
                "learnings": "LearningStore",
                "recommendations": "Recommendations",
                "parameter_performance": "ParameterPerformance"
            }
            
            health["tables"] = {}
            for key, table in tables.items():
                try:
                    df = db.query(f"SELECT COUNT(*) as cnt FROM dbo.{table}")
                    health["tables"][key] = df.iloc[0]["cnt"] if not df.empty else 0
                except:
                    health["tables"][key] = -1
            
            # Get learning stats
            summary = self.get_learning_summary(days=7)
            health["recent_learnings"] = summary.get("total_learnings", 0)
            health["active_patterns"] = summary.get("high_confidence_patterns", 0)
        
        return health
    
    def reset_patterns(self, deactivate_only: bool = True) -> int:
        """
        Reset patterns - either deactivate or delete.
        
        Returns count of affected patterns.
        """
        db = get_db()
        
        if deactivate_only:
            sql = "UPDATE dbo.Patterns SET IsActive = 0"
        else:
            sql = "DELETE FROM dbo.Patterns"
        
        cursor = db._connection.cursor()
        cursor.execute(sql)
        count = cursor.rowcount
        db._connection.commit()
        
        return count


# Convenience function for quick access
def get_learning_store() -> LearningStore:
    """Get a configured LearningStore instance."""
    store = LearningStore()
    store.initialize()
    return store
