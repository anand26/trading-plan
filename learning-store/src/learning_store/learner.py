"""
Adaptive Learning Engine for the Learning Store.

Continuously learns from trade outcomes to improve pattern confidence
and generate insights.
"""

from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
import numpy as np

from .models import (
    Pattern, PatternType, Learning, LearningType,
    MarketRegime, TradeFeatures, ParameterPerformance
)
from .database import (
    get_trade_features, get_patterns, update_pattern,
    save_learning, get_learnings, get_parameter_performance,
    update_parameter_performance, get_db
)
from .config import learning_config


class AdaptiveLearner:
    """
    Adaptive learning engine that continuously improves from trade outcomes.
    
    The learner:
    1. Observes trade outcomes
    2. Updates pattern confidence based on results
    3. Identifies parameter performance trends
    4. Generates learning events for audit
    """
    
    def __init__(self):
        self._last_analysis: Optional[datetime] = None
        self._learning_buffer: list[Learning] = []
    
    def learn_from_trades(self, days: int = 7) -> list[Learning]:
        """
        Analyze recent trades and generate learnings.
        
        Returns list of learning events generated.
        """
        features = get_trade_features(days=days)
        if not features:
            return []
        
        learnings = []
        
        # Learn from trade outcomes
        outcome_learnings = self._learn_from_outcomes(features)
        learnings.extend(outcome_learnings)
        
        # Learn parameter effectiveness
        param_learnings = self._learn_parameter_effectiveness(features)
        learnings.extend(param_learnings)
        
        # Detect regime transitions
        regime_learnings = self._learn_regime_transitions(features)
        learnings.extend(regime_learnings)
        
        # Update pattern confidence based on outcomes
        self._update_pattern_confidence(features)
        
        self._last_analysis = datetime.now()
        return learnings
    
    def _learn_from_outcomes(self, features: list[TradeFeatures]) -> list[Learning]:
        """Generate learnings from trade outcomes."""
        learnings = []
        
        # Calculate overall performance
        total_pnl = sum(f.pnl for f in features)
        win_rate = sum(1 for f in features if f.is_winner) / len(features)
        
        # Compare to previous period
        previous_learnings = get_learnings(
            learning_type=LearningType.TRADE_OUTCOME,
            days=14
        )
        
        # Generate learning if significant change
        if len(features) >= 10:
            learning = Learning(
                learning_type=LearningType.TRADE_OUTCOME,
                description=f"Period analysis: {len(features)} trades, {win_rate:.1%} win rate, ${total_pnl:.2f} P&L",
                old_value=str(len(previous_learnings)),
                new_value=str(len(features)),
                confidence_score=min(0.9, 0.5 + len(features) / 100),
                source="adaptive_learner",
                metadata={
                    "trade_count": len(features),
                    "win_rate": win_rate,
                    "total_pnl": total_pnl,
                    "avg_pnl": total_pnl / len(features)
                }
            )
            learning.learning_id = save_learning(learning)
            learnings.append(learning)
        
        # Learn from losing streaks
        losing_streak = self._find_losing_streaks(features)
        for streak in losing_streak:
            if len(streak) >= 3:
                learning = Learning(
                    learning_type=LearningType.TRADE_OUTCOME,
                    description=f"Losing streak detected: {len(streak)} consecutive losses",
                    confidence_score=0.7,
                    source="adaptive_learner",
                    metadata={
                        "streak_length": len(streak),
                        "total_loss": sum(f.pnl for f in streak),
                        "trade_ids": [f.trade_id for f in streak]
                    }
                )
                learning.learning_id = save_learning(learning)
                learnings.append(learning)
        
        return learnings
    
    def _learn_parameter_effectiveness(self, features: list[TradeFeatures]) -> list[Learning]:
        """Learn which parameters are working well."""
        learnings = []
        
        # Analyze by entry reason (proxy for parameters used)
        by_reason = defaultdict(list)
        for f in features:
            if f.entry_reason:
                by_reason[f.entry_reason].append(f)
        
        for reason, trades in by_reason.items():
            if len(trades) < 5:
                continue
            
            win_rate = sum(1 for t in trades if t.is_winner) / len(trades)
            avg_pnl = np.mean([t.pnl for t in trades])
            
            # Compare to overall performance
            overall_win_rate = sum(1 for f in features if f.is_winner) / len(features)
            
            if abs(win_rate - overall_win_rate) > 0.1:
                better_worse = "outperforming" if win_rate > overall_win_rate else "underperforming"
                
                learning = Learning(
                    learning_type=LearningType.PARAMETER_ADJUSTED,
                    description=f"Entry reason '{reason}' {better_worse}: {win_rate:.1%} vs {overall_win_rate:.1%} overall",
                    old_value=f"{overall_win_rate:.1%}",
                    new_value=f"{win_rate:.1%}",
                    confidence_score=min(0.9, 0.5 + len(trades) / 50),
                    source="adaptive_learner",
                    metadata={
                        "entry_reason": reason,
                        "trade_count": len(trades),
                        "win_rate": win_rate,
                        "avg_pnl": avg_pnl,
                        "comparison": better_worse
                    }
                )
                learning.learning_id = save_learning(learning)
                learnings.append(learning)
        
        return learnings
    
    def _learn_regime_transitions(self, features: list[TradeFeatures]) -> list[Learning]:
        """Learn from market regime transitions."""
        learnings = []
        
        # Group by regime
        by_regime = defaultdict(list)
        for f in features:
            if f.regime_at_entry:
                by_regime[f.regime_at_entry].append(f)
        
        # Compare performance across regimes
        regime_performance = {}
        for regime, trades in by_regime.items():
            if len(trades) >= 5:
                regime_performance[regime] = {
                    "count": len(trades),
                    "win_rate": sum(1 for t in trades if t.is_winner) / len(trades),
                    "avg_pnl": np.mean([t.pnl for t in trades]),
                    "total_pnl": sum(t.pnl for t in trades)
                }
        
        if len(regime_performance) >= 2:
            # Find best and worst regimes
            sorted_regimes = sorted(
                regime_performance.items(),
                key=lambda x: x[1]["win_rate"],
                reverse=True
            )
            
            best = sorted_regimes[0]
            worst = sorted_regimes[-1]
            
            if best[1]["win_rate"] - worst[1]["win_rate"] > 0.1:
                learning = Learning(
                    learning_type=LearningType.REGIME_TRANSITION,
                    description=f"Regime performance gap: {best[0].value} ({best[1]['win_rate']:.1%}) vs {worst[0].value} ({worst[1]['win_rate']:.1%})",
                    old_value=worst[0].value,
                    new_value=best[0].value,
                    confidence_score=0.7,
                    source="adaptive_learner",
                    metadata={
                        "regime_performance": {
                            k.value: v for k, v in regime_performance.items()
                        },
                        "best_regime": best[0].value,
                        "worst_regime": worst[0].value
                    }
                )
                learning.learning_id = save_learning(learning)
                learnings.append(learning)
        
        return learnings
    
    def _update_pattern_confidence(self, features: list[TradeFeatures]):
        """Update pattern confidence based on recent trade outcomes."""
        patterns = get_patterns(active_only=True)
        
        for pattern in patterns:
            # Find trades that match this pattern's conditions
            matching_trades = self._find_matching_trades(pattern, features)
            
            if len(matching_trades) < 3:
                # Apply decay for patterns without recent data
                pattern.confidence *= learning_config.pattern_decay_rate
                update_pattern(pattern)
                continue
            
            # Calculate new metrics
            new_win_rate = sum(1 for t in matching_trades if t.is_winner) / len(matching_trades)
            new_avg_pnl = np.mean([t.pnl for t in matching_trades])
            
            # Update confidence based on outcome match
            expected_profitable = pattern.expected_outcome == "PROFITABLE"
            actual_profitable = new_avg_pnl > 0
            
            if expected_profitable == actual_profitable:
                # Pattern prediction was correct - increase confidence
                pattern.confidence = min(0.95, pattern.confidence * 1.05)
            else:
                # Pattern prediction was wrong - decrease confidence
                pattern.confidence = max(0.1, pattern.confidence * 0.9)
            
            # Update statistics
            pattern.sample_size += len(matching_trades)
            pattern.win_rate = (pattern.win_rate + new_win_rate) / 2  # Moving average
            pattern.avg_pnl = float((pattern.avg_pnl + new_avg_pnl) / 2)
            
            update_pattern(pattern)
    
    def _find_matching_trades(
        self,
        pattern: Pattern,
        features: list[TradeFeatures]
    ) -> list[TradeFeatures]:
        """Find trades that match a pattern's conditions."""
        matching = []
        
        for f in features:
            matches = True
            
            for key, value in pattern.conditions.items():
                if key == "entry_hour" and f.entry_hour != value:
                    matches = False
                    break
                elif key == "exit_hour" and f.exit_hour != value:
                    matches = False
                    break
                elif key == "regime" and f.regime_at_entry and f.regime_at_entry.value != value:
                    matches = False
                    break
                elif key == "symbol" and f.symbol != value:
                    matches = False
                    break
                elif key == "holding_min_minutes" and f.holding_minutes < value:
                    matches = False
                    break
                elif key == "holding_max_minutes" and f.holding_minutes >= value:
                    matches = False
                    break
            
            if matches:
                matching.append(f)
        
        return matching
    
    def _find_losing_streaks(
        self,
        features: list[TradeFeatures]
    ) -> list[list[TradeFeatures]]:
        """Find sequences of losing trades."""
        # Sort by trade_id (proxy for time order)
        sorted_features = sorted(features, key=lambda f: f.trade_id)
        
        streaks = []
        current_streak = []
        
        for f in sorted_features:
            if not f.is_winner:
                current_streak.append(f)
            else:
                if len(current_streak) >= 3:
                    streaks.append(current_streak)
                current_streak = []
        
        if len(current_streak) >= 3:
            streaks.append(current_streak)
        
        return streaks
    
    def analyze_parameter(
        self,
        parameter_name: str,
        values: list[str],
        days: int = 30
    ) -> dict[str, ParameterPerformance]:
        """
        Analyze performance of different parameter values.
        
        Returns dict mapping value to performance metrics.
        """
        db = get_db()
        
        # Get trades with different parameter values
        # This would need to join with a parameters history table
        # For now, use the stored parameter performance
        
        performances = get_parameter_performance(parameter_name)
        return {p.parameter_value: p for p in performances}
    
    def suggest_parameter_adjustment(
        self,
        parameter_name: str,
        current_value: str,
        regime: Optional[MarketRegime] = None
    ) -> Optional[tuple[str, float]]:
        """
        Suggest a parameter adjustment based on learning.
        
        Returns (suggested_value, confidence) or None if no suggestion.
        """
        performances = get_parameter_performance(parameter_name)
        
        if not performances:
            return None
        
        # Filter by regime if specified
        if regime:
            regime_perfs = [p for p in performances if p.regime == regime or p.regime is None]
            if regime_perfs:
                performances = regime_perfs
        
        # Find best performing value with sufficient sample size
        min_samples = learning_config.recommendation_min_samples
        qualified = [p for p in performances if p.trade_count >= min_samples]
        
        if not qualified:
            return None
        
        # Sort by win_rate * avg_pnl factor
        qualified.sort(
            key=lambda p: p.win_rate * (1 + p.avg_pnl / 100),
            reverse=True
        )
        
        best = qualified[0]
        
        if str(best.parameter_value) == current_value:
            return None  # Already using best value
        
        # Calculate confidence based on sample size and performance gap
        current_perf = next(
            (p for p in performances if str(p.parameter_value) == current_value),
            None
        )
        
        if current_perf:
            improvement = best.win_rate - current_perf.win_rate
            confidence = min(0.9, 0.5 + improvement + (best.trade_count / 200))
        else:
            confidence = min(0.8, 0.4 + (best.trade_count / 200))
        
        return (str(best.parameter_value), confidence)
    
    def get_learning_summary(self, days: int = 30) -> dict:
        """Get a summary of recent learning activity."""
        learnings = get_learnings(days=days)
        patterns = get_patterns(active_only=True)
        
        # Categorize learnings
        by_type = defaultdict(list)
        for l in learnings:
            by_type[l.learning_type.value].append(l)
        
        # Calculate pattern statistics
        high_conf_patterns = [p for p in patterns if p.confidence >= 0.7]
        avg_confidence = np.mean([p.confidence for p in patterns]) if patterns else 0
        
        return {
            "period_days": days,
            "total_learnings": len(learnings),
            "learnings_by_type": {k: len(v) for k, v in by_type.items()},
            "total_patterns": len(patterns),
            "high_confidence_patterns": len(high_conf_patterns),
            "avg_pattern_confidence": avg_confidence,
            "last_analysis": self._last_analysis.isoformat() if self._last_analysis else None,
            "recent_learnings": [
                {
                    "type": l.learning_type.value,
                    "description": l.description,
                    "confidence": l.confidence_score,
                    "timestamp": l.timestamp.isoformat()
                }
                for l in learnings[:10]
            ]
        }
