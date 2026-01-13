"""
Recommendation Engine for the Learning Store.

Generates actionable recommendations based on patterns and learnings.
"""

from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
import numpy as np

from .models import (
    Pattern, PatternType, Recommendation, MarketRegime,
    MarketConditions, ParameterPerformance
)
from .database import (
    get_patterns, get_active_recommendations, save_recommendation,
    mark_recommendation_applied, get_parameter_performance, get_db
)
from .patterns import PatternRecognizer
from .config import learning_config


class RecommendationEngine:
    """
    Generates trading recommendations based on learned patterns.
    
    The engine:
    1. Analyzes current market conditions
    2. Matches against known patterns
    3. Generates parameter adjustment recommendations
    4. Tracks recommendation outcomes
    """
    
    def __init__(self):
        self._pattern_recognizer = PatternRecognizer()
        self._recommendation_cache: dict[str, Recommendation] = {}
    
    def get_recommendations(
        self,
        conditions: MarketConditions,
        limit: int = 5
    ) -> list[Recommendation]:
        """
        Get recommendations for current market conditions.
        
        Returns list of recommendations sorted by confidence.
        """
        recommendations = []
        
        # Get pattern-based recommendations
        pattern_recs = self._get_pattern_recommendations(conditions)
        recommendations.extend(pattern_recs)
        
        # Get parameter optimization recommendations
        param_recs = self._get_parameter_recommendations(conditions.regime)
        recommendations.extend(param_recs)
        
        # Get timing recommendations
        timing_recs = self._get_timing_recommendations(conditions)
        recommendations.extend(timing_recs)
        
        # Deduplicate by parameter name, keeping highest confidence
        unique_recs = {}
        for rec in recommendations:
            key = f"{rec.parameter_name}:{rec.recommended_value}"
            if key not in unique_recs or rec.confidence > unique_recs[key].confidence:
                unique_recs[key] = rec
        
        # Sort by confidence
        sorted_recs = sorted(
            unique_recs.values(),
            key=lambda r: r.confidence * r.expected_improvement,
            reverse=True
        )
        
        return sorted_recs[:limit]
    
    def _get_pattern_recommendations(
        self,
        conditions: MarketConditions
    ) -> list[Recommendation]:
        """Generate recommendations based on pattern matches."""
        recommendations = []
        
        # Find matching patterns
        matches = self._pattern_recognizer.match_conditions(conditions)
        
        for match in matches[:5]:  # Top 5 matches
            pattern = match.pattern
            
            if pattern.win_rate < 0.5:
                continue  # Skip underperforming patterns
            
            # Generate recommendation based on pattern type
            if pattern.pattern_type == PatternType.ENTRY_TIMING:
                rec = Recommendation(
                    parameter_name="entry_timing",
                    current_value=str(conditions.hour_of_day),
                    recommended_value=str(pattern.conditions.get("entry_hour", conditions.hour_of_day)),
                    confidence=pattern.confidence * match.match_score,
                    expected_improvement=pattern.win_rate - 0.5,
                    reasoning=f"Pattern '{pattern.name}' suggests favorable entry timing. "
                              f"Historical win rate: {pattern.win_rate:.1%}",
                    supporting_patterns=[pattern.pattern_id] if pattern.pattern_id else [],
                    regime=conditions.regime
                )
                recommendations.append(rec)
            
            elif pattern.pattern_type == PatternType.REGIME_DETECTION:
                symbol = pattern.conditions.get("symbol", "TQQQ")
                rec = Recommendation(
                    parameter_name="preferred_symbol",
                    current_value="TQQQ",
                    recommended_value=symbol,
                    confidence=pattern.confidence * match.match_score,
                    expected_improvement=pattern.avg_pnl / 100 if pattern.avg_pnl else 0.05,
                    reasoning=f"In {conditions.regime.value} regime, {symbol} shows "
                              f"{pattern.win_rate:.1%} win rate",
                    supporting_patterns=[pattern.pattern_id] if pattern.pattern_id else [],
                    regime=conditions.regime
                )
                recommendations.append(rec)
            
            elif pattern.pattern_type == PatternType.POSITION_SIZING:
                # Recommend holding period adjustment
                hold_min = pattern.conditions.get("holding_min_minutes", 5)
                hold_max = pattern.conditions.get("holding_max_minutes", 30)
                
                rec = Recommendation(
                    parameter_name="target_holding_minutes",
                    current_value="15",
                    recommended_value=f"{hold_min}-{hold_max}",
                    confidence=pattern.confidence * match.match_score,
                    expected_improvement=pattern.win_rate - 0.5,
                    reasoning=f"Optimal holding period: {hold_min}-{hold_max} minutes. "
                              f"Win rate: {pattern.win_rate:.1%}",
                    supporting_patterns=[pattern.pattern_id] if pattern.pattern_id else [],
                    regime=conditions.regime
                )
                recommendations.append(rec)
        
        return recommendations
    
    def _get_parameter_recommendations(
        self,
        regime: Optional[MarketRegime] = None
    ) -> list[Recommendation]:
        """Generate recommendations based on parameter performance."""
        recommendations = []
        
        # Parameters to analyze
        parameters = [
            "RSI_OVERSOLD",
            "RSI_OVERBOUGHT", 
            "PROFIT_TARGET_PCT",
            "STOP_LOSS_PCT",
            "POSITION_SIZE_PCT"
        ]
        
        for param_name in parameters:
            performances = get_parameter_performance(param_name)
            
            if not performances:
                continue
            
            # Filter by regime if specified
            if regime:
                regime_perfs = [p for p in performances if p.regime == regime or p.regime is None]
                if regime_perfs:
                    performances = regime_perfs
            
            # Need minimum sample size
            qualified = [
                p for p in performances 
                if p.trade_count >= learning_config.recommendation_min_samples
            ]
            
            if len(qualified) < 2:
                continue
            
            # Find best performer
            qualified.sort(
                key=lambda p: p.win_rate * (1 + max(0, p.total_pnl) / 1000),
                reverse=True
            )
            
            best = qualified[0]
            
            # Get current value (assume first in sorted list without high performance)
            current = qualified[-1] if len(qualified) > 1 else qualified[0]
            
            if best.parameter_value == current.parameter_value:
                continue
            
            improvement = best.win_rate - current.win_rate
            if improvement < 0.05:
                continue  # Not significant enough
            
            rec = Recommendation(
                parameter_name=param_name,
                current_value=str(current.parameter_value),
                recommended_value=str(best.parameter_value),
                confidence=min(0.9, 0.5 + (best.trade_count / 200) + improvement),
                expected_improvement=improvement,
                reasoning=f"Parameter {param_name}={best.parameter_value} shows "
                          f"{best.win_rate:.1%} win rate ({best.trade_count} trades) vs "
                          f"{current.win_rate:.1%} for current value",
                regime=regime,
                valid_until=datetime.now() + timedelta(days=7)
            )
            recommendations.append(rec)
        
        return recommendations
    
    def _get_timing_recommendations(
        self,
        conditions: MarketConditions
    ) -> list[Recommendation]:
        """Generate timing-specific recommendations."""
        recommendations = []
        
        # Get entry timing patterns
        timing_patterns = self._pattern_recognizer.get_top_patterns(
            pattern_type=PatternType.ENTRY_TIMING,
            regime=conditions.regime,
            limit=5
        )
        
        # Find best hours
        best_hours = []
        for pattern in timing_patterns:
            if pattern.win_rate >= 0.55:
                hour = pattern.conditions.get("entry_hour")
                if hour is not None:
                    best_hours.append((hour, pattern.win_rate, pattern.confidence))
        
        if best_hours:
            best_hours.sort(key=lambda x: x[1] * x[2], reverse=True)
            best = best_hours[0]
            
            if best[0] != conditions.hour_of_day:
                rec = Recommendation(
                    parameter_name="active_trading_hours",
                    current_value=str(conditions.hour_of_day),
                    recommended_value=str(best[0]),
                    confidence=best[2],
                    expected_improvement=best[1] - 0.5,
                    reasoning=f"Hour {best[0]} shows {best[1]:.1%} win rate. "
                              f"Current hour {conditions.hour_of_day} may be suboptimal.",
                    regime=conditions.regime
                )
                recommendations.append(rec)
        
        # RSI-based recommendations
        if conditions.rsi < 30:
            rec = Recommendation(
                parameter_name="entry_signal",
                current_value="neutral",
                recommended_value="long_oversold",
                confidence=0.7,
                expected_improvement=0.1,
                reasoning=f"RSI at {conditions.rsi:.1f} indicates oversold. "
                          f"Consider long entry on TQQQ.",
                regime=conditions.regime
            )
            recommendations.append(rec)
        elif conditions.rsi > 70:
            rec = Recommendation(
                parameter_name="entry_signal",
                current_value="neutral", 
                recommended_value="long_overbought",
                confidence=0.7,
                expected_improvement=0.1,
                reasoning=f"RSI at {conditions.rsi:.1f} indicates overbought. "
                          f"Consider long entry on SQQQ or reduce exposure.",
                regime=conditions.regime
            )
            recommendations.append(rec)
        
        return recommendations
    
    def suggest_corrections(
        self,
        recent_performance: dict,
        current_params: dict
    ) -> list[Recommendation]:
        """
        Suggest corrections based on recent underperformance.
        
        Args:
            recent_performance: Dict with keys like win_rate, avg_pnl, etc.
            current_params: Dict of current parameter values
        
        Returns:
            List of correction recommendations
        """
        recommendations = []
        
        win_rate = recent_performance.get("win_rate", 0.5)
        avg_pnl = recent_performance.get("avg_pnl", 0)
        trade_count = recent_performance.get("trade_count", 0)
        
        if trade_count < 10:
            return []  # Not enough data
        
        # If win rate is low, suggest parameter adjustments
        if win_rate < 0.45:
            # Suggest tighter stop loss
            current_stop = current_params.get("STOP_LOSS_PCT", 0.02)
            rec = Recommendation(
                parameter_name="STOP_LOSS_PCT",
                current_value=str(current_stop),
                recommended_value=str(current_stop * 0.8),
                confidence=0.7,
                expected_improvement=0.05,
                reasoning=f"Win rate at {win_rate:.1%} is below target. "
                          f"Tighter stop loss may reduce losing trades."
            )
            recommendations.append(rec)
            
            # Suggest smaller position size
            current_size = current_params.get("POSITION_SIZE_PCT", 0.1)
            rec = Recommendation(
                parameter_name="POSITION_SIZE_PCT",
                current_value=str(current_size),
                recommended_value=str(current_size * 0.75),
                confidence=0.6,
                expected_improvement=0.03,
                reasoning=f"Reducing position size during low win rate period "
                          f"({win_rate:.1%}) to manage risk."
            )
            recommendations.append(rec)
        
        # If avg P&L is negative despite decent win rate
        if avg_pnl < 0 and win_rate >= 0.45:
            # Winners may be too small
            current_target = current_params.get("PROFIT_TARGET_PCT", 0.01)
            rec = Recommendation(
                parameter_name="PROFIT_TARGET_PCT",
                current_value=str(current_target),
                recommended_value=str(current_target * 1.3),
                confidence=0.65,
                expected_improvement=0.07,
                reasoning=f"Average P&L (${avg_pnl:.2f}) is negative despite "
                          f"{win_rate:.1%} win rate. Increase profit target to "
                          f"let winners run longer."
            )
            recommendations.append(rec)
        
        return recommendations
    
    def apply_recommendation(
        self,
        recommendation: Recommendation,
        outcome: Optional[str] = None
    ) -> bool:
        """Mark a recommendation as applied and track outcome."""
        if recommendation.recommendation_id:
            return mark_recommendation_applied(
                recommendation.recommendation_id,
                outcome
            )
        return False
    
    def save_new_recommendation(self, recommendation: Recommendation) -> Optional[int]:
        """Save a new recommendation to the database."""
        return save_recommendation(recommendation)
    
    def get_pending_recommendations(
        self,
        parameter_name: Optional[str] = None,
        regime: Optional[MarketRegime] = None,
        min_confidence: float = 0.5
    ) -> list[Recommendation]:
        """Get recommendations that haven't been applied yet."""
        return get_active_recommendations(
            parameter_name=parameter_name,
            regime=regime,
            min_confidence=min_confidence
        )
    
    def get_recommendation_effectiveness(self, days: int = 30) -> dict:
        """
        Analyze how effective past recommendations have been.
        
        Returns dict with effectiveness metrics.
        """
        db = get_db()
        
        sql = """
            SELECT 
                ParameterName,
                COUNT(*) as TotalRecs,
                SUM(CASE WHEN Applied = 1 THEN 1 ELSE 0 END) as AppliedRecs,
                AVG(Confidence) as AvgConfidence,
                AVG(ExpectedImprovement) as AvgExpectedImprovement
            FROM dbo.Recommendations
            WHERE CreatedAt >= DATEADD(day, -?, GETDATE())
            GROUP BY ParameterName
        """
        
        df = db.query(sql, (days,))
        
        if df.empty:
            return {"period_days": days, "parameters": {}}
        
        parameters = {}
        for _, row in df.iterrows():
            parameters[row["ParameterName"]] = {
                "total": row["TotalRecs"],
                "applied": row["AppliedRecs"],
                "application_rate": row["AppliedRecs"] / row["TotalRecs"] if row["TotalRecs"] > 0 else 0,
                "avg_confidence": row["AvgConfidence"],
                "avg_expected_improvement": row["AvgExpectedImprovement"]
            }
        
        return {
            "period_days": days,
            "total_recommendations": sum(p["total"] for p in parameters.values()),
            "total_applied": sum(p["applied"] for p in parameters.values()),
            "parameters": parameters
        }
