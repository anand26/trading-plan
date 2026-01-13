"""
Analyzer Component - Decision Analysis and Pattern Matching

Analyzes market conditions, performance data, and learned patterns
to generate recommendations and identify opportunities.
"""

import logging
from datetime import datetime
from typing import Optional
import pyodbc

from .config import AgentConfig
from .models import (
    MarketSnapshot,
    MarketRegime,
    PositionSnapshot,
    PerformanceSnapshot,
    Decision,
    DecisionType,
)


logger = logging.getLogger(__name__)


class Analyzer:
    """
    Analyzes conditions and generates recommendations.
    
    Responsibilities:
    - Match current conditions against learned patterns
    - Assess risk levels
    - Generate parameter recommendations
    - Score potential decisions
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self._conn: Optional[pyodbc.Connection] = None
    
    def _get_connection(self) -> pyodbc.Connection:
        """Get or create database connection."""
        if self._conn is None or not self._is_connection_alive():
            self._conn = pyodbc.connect(
                self.config.database.connection_string,
                autocommit=True
            )
        return self._conn
    
    def _is_connection_alive(self) -> bool:
        """Check if the connection is still alive."""
        try:
            if self._conn is None:
                return False
            cursor = self._conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False
    
    def analyze_market_conditions(
        self,
        market: MarketSnapshot,
        performance: PerformanceSnapshot,
    ) -> list[dict]:
        """
        Analyze current market conditions and return observations.
        
        Returns:
            List of observation dictionaries with factors and scores.
        """
        observations = []
        
        # RSI analysis
        if market.rsi < 30:
            observations.append({
                "factor": "RSI_OVERSOLD",
                "description": f"RSI at {market.rsi:.1f} indicates oversold conditions",
                "signal": "bullish",
                "strength": (30 - market.rsi) / 30,
            })
        elif market.rsi > 70:
            observations.append({
                "factor": "RSI_OVERBOUGHT",
                "description": f"RSI at {market.rsi:.1f} indicates overbought conditions",
                "signal": "bearish",
                "strength": (market.rsi - 70) / 30,
            })
        
        # Volatility analysis
        if market.volatility > 0.03:  # High volatility threshold
            observations.append({
                "factor": "HIGH_VOLATILITY",
                "description": f"Volatility at {market.volatility:.2%} is elevated",
                "signal": "caution",
                "strength": min(market.volatility / 0.05, 1.0),
            })
        
        # Trend analysis
        if abs(market.trend_strength) > 0.5:
            direction = "up" if market.trend_strength > 0 else "down"
            observations.append({
                "factor": "STRONG_TREND",
                "description": f"Strong {direction}trend with strength {abs(market.trend_strength):.2f}",
                "signal": "bullish" if direction == "up" else "bearish",
                "strength": abs(market.trend_strength),
            })
        
        # Performance-based analysis
        if performance.current_drawdown > 0.10:
            observations.append({
                "factor": "ELEVATED_DRAWDOWN",
                "description": f"Current drawdown at {performance.current_drawdown:.1%}",
                "signal": "caution",
                "strength": performance.current_drawdown / 0.20,
            })
        
        if performance.current_streak <= -3:
            observations.append({
                "factor": "LOSING_STREAK",
                "description": f"{abs(performance.current_streak)} consecutive losses",
                "signal": "caution",
                "strength": min(abs(performance.current_streak) / 5, 1.0),
            })
        
        # Time-based observations
        if market.hour_of_day == 9:
            observations.append({
                "factor": "MARKET_OPEN",
                "description": "First hour of trading - higher volatility expected",
                "signal": "info",
                "strength": 0.5,
            })
        elif market.hour_of_day >= 15:
            observations.append({
                "factor": "MARKET_CLOSE",
                "description": "End of day - consider closing positions",
                "signal": "info",
                "strength": 0.3,
            })
        
        return observations
    
    def match_patterns(
        self,
        market: MarketSnapshot,
        performance: PerformanceSnapshot,
    ) -> list[dict]:
        """
        Match current conditions against learned patterns.
        
        Returns:
            List of matched patterns with confidence scores.
        """
        matched = []
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get patterns that match current regime
            cursor.execute("""
                EXEC sp_GetTopPatterns 
                    @PatternType = NULL,
                    @MinConfidence = ?,
                    @Limit = 20
            """, (self.config.thresholds.pattern_match_threshold,))
            
            patterns = cursor.fetchall()
            
            for pattern in patterns:
                pattern_id, pattern_type, conditions_json, action_json, \
                    occurrences, success_rate, confidence = pattern
                
                # Parse conditions and check match
                # In a full implementation, this would deserialize the JSON
                # and compare against current market conditions
                
                # Simple match score based on regime
                match_score = 0.0
                
                if "regime" in (conditions_json or "").lower():
                    if market.regime.value.lower() in conditions_json.lower():
                        match_score += 0.4
                
                if "volatility" in (conditions_json or "").lower():
                    if "high" in conditions_json.lower() and market.volatility > 0.02:
                        match_score += 0.3
                    elif "low" in conditions_json.lower() and market.volatility <= 0.02:
                        match_score += 0.3
                
                if match_score >= self.config.thresholds.pattern_match_threshold:
                    matched.append({
                        "pattern_id": pattern_id,
                        "pattern_type": pattern_type,
                        "action": action_json,
                        "match_score": match_score,
                        "confidence": float(confidence or 0),
                        "success_rate": float(success_rate or 0),
                    })
            
            cursor.close()
            
        except pyodbc.Error as e:
            logger.warning(f"Database error in match_patterns: {e}")
        except Exception as e:
            logger.error(f"Error matching patterns: {e}")
        
        return sorted(matched, key=lambda x: x["match_score"] * x["confidence"], reverse=True)
    
    def get_active_recommendations(self) -> list[dict]:
        """
        Get active recommendations from the Learning Store.
        
        Returns:
            List of recommendation dictionaries.
        """
        recommendations = []
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                EXEC sp_GetActiveRecommendations @Limit = 10
            """)
            
            for row in cursor.fetchall():
                rec_id, pattern_id, rec_type, param, old_val, new_val, \
                    reason, confidence, priority, created = row
                
                recommendations.append({
                    "recommendation_id": rec_id,
                    "pattern_id": pattern_id,
                    "recommendation_type": rec_type,
                    "parameter_name": param,
                    "old_value": old_val,
                    "new_value": new_val,
                    "reason": reason,
                    "confidence": float(confidence or 0),
                    "priority": priority,
                    "created_at": created,
                })
            
            cursor.close()
            
        except pyodbc.Error as e:
            logger.warning(f"Database error in get_active_recommendations: {e}")
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
        
        return recommendations
    
    def assess_risk(
        self,
        market: MarketSnapshot,
        positions: list[PositionSnapshot],
        performance: PerformanceSnapshot,
    ) -> dict:
        """
        Assess current risk level.
        
        Returns:
            Risk assessment dictionary.
        """
        risk_score = 0.0
        risk_factors = []
        
        # Position risk
        total_position_value = sum(abs(p.quantity * p.current_price) for p in positions)
        # Assume $100k account for percentage calculation
        position_pct = total_position_value / 100000
        
        if position_pct > self.config.risk.max_position_size_pct:
            risk_score += 0.3
            risk_factors.append(f"Position size ({position_pct:.1%}) exceeds max ({self.config.risk.max_position_size_pct:.1%})")
        
        # Drawdown risk
        if performance.current_drawdown > self.config.thresholds.emergency_drawdown_pct:
            risk_score += 0.4
            risk_factors.append(f"Drawdown ({performance.current_drawdown:.1%}) exceeds emergency threshold")
        elif performance.current_drawdown > self.config.risk.max_daily_loss_pct:
            risk_score += 0.2
            risk_factors.append(f"Drawdown ({performance.current_drawdown:.1%}) elevated")
        
        # Consecutive losses
        if abs(performance.current_streak) >= self.config.risk.max_consecutive_losses:
            if performance.current_streak < 0:
                risk_score += 0.3
                risk_factors.append(f"{abs(performance.current_streak)} consecutive losses")
        
        # Volatility risk
        if market.volatility > 0.04:
            risk_score += 0.2
            risk_factors.append(f"High volatility ({market.volatility:.2%})")
        
        return {
            "risk_score": min(risk_score, 1.0),
            "risk_level": self._risk_level(risk_score),
            "factors": risk_factors,
            "emergency_stop_recommended": risk_score >= 0.8,
        }
    
    def _risk_level(self, score: float) -> str:
        """Convert risk score to level."""
        if score >= 0.7:
            return "CRITICAL"
        elif score >= 0.5:
            return "HIGH"
        elif score >= 0.3:
            return "MODERATE"
        else:
            return "LOW"
    
    def generate_decision(
        self,
        market: MarketSnapshot,
        positions: list[PositionSnapshot],
        performance: PerformanceSnapshot,
        observations: list[dict],
        matched_patterns: list[dict],
        recommendations: list[dict],
        risk_assessment: dict,
    ) -> Decision:
        """
        Generate a decision based on all analysis inputs.
        
        Returns:
            Decision object with recommended action.
        """
        # Check for emergency conditions first
        if risk_assessment["emergency_stop_recommended"]:
            return Decision(
                decision_type=DecisionType.EMERGENCY_STOP,
                action="HALT_TRADING",
                confidence=1.0,
                reasoning=f"Emergency stop triggered. Risk factors: {', '.join(risk_assessment['factors'])}",
                contributing_factors=risk_assessment["factors"],
                market_snapshot=market,
                performance_snapshot=performance,
            )
        
        # Check for high-priority recommendations
        if recommendations:
            top_rec = recommendations[0]
            if top_rec["confidence"] >= self.config.thresholds.min_confidence_to_act:
                return Decision(
                    decision_type=DecisionType.PARAMETER_ADJUSTMENT,
                    action="APPLY_RECOMMENDATION",
                    confidence=top_rec["confidence"],
                    parameter_name=top_rec["parameter_name"],
                    old_value=top_rec["old_value"],
                    new_value=top_rec["new_value"],
                    reasoning=top_rec["reason"],
                    supporting_patterns=[top_rec["pattern_id"]] if top_rec["pattern_id"] else [],
                    market_snapshot=market,
                    performance_snapshot=performance,
                )
        
        # Check for pattern-based actions
        if matched_patterns:
            top_pattern = matched_patterns[0]
            combined_confidence = top_pattern["match_score"] * top_pattern["confidence"]
            
            if combined_confidence >= self.config.thresholds.min_confidence_to_act:
                return Decision(
                    decision_type=DecisionType.PARAMETER_ADJUSTMENT,
                    action="APPLY_PATTERN",
                    confidence=combined_confidence,
                    reasoning=f"Pattern {top_pattern['pattern_type']} matched with {combined_confidence:.1%} confidence",
                    supporting_patterns=[top_pattern["pattern_id"]],
                    market_snapshot=market,
                    performance_snapshot=performance,
                )
        
        # Check for regime-based adaptations
        caution_signals = [o for o in observations if o["signal"] == "caution"]
        if caution_signals:
            avg_strength = sum(o["strength"] for o in caution_signals) / len(caution_signals)
            if avg_strength >= 0.6:
                return Decision(
                    decision_type=DecisionType.RISK_SCALING,
                    action="REDUCE_EXPOSURE",
                    confidence=avg_strength,
                    reasoning=f"Caution signals detected: {', '.join(o['factor'] for o in caution_signals)}",
                    contributing_factors=[o["factor"] for o in caution_signals],
                    market_snapshot=market,
                    performance_snapshot=performance,
                )
        
        # No action needed
        return Decision(
            decision_type=DecisionType.NO_ACTION,
            action="CONTINUE",
            confidence=1.0,
            reasoning="No significant signals requiring action",
            market_snapshot=market,
            performance_snapshot=performance,
        )
    
    def close(self):
        """Close database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
