"""
Decision Engine - Core Decision Logic

Multi-factor scoring and confidence aggregation for adaptive decisions.
"""

import logging
from datetime import datetime, timedelta
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


class Factor:
    """A weighted decision factor."""
    
    def __init__(
        self,
        name: str,
        weight: float,
        score: float,
        direction: str = "neutral",
        description: str = "",
    ):
        self.name = name
        self.weight = weight
        self.score = score  # -1 to 1
        self.direction = direction  # bullish, bearish, neutral, caution
        self.description = description
    
    @property
    def weighted_score(self) -> float:
        return self.weight * self.score


class DecisionEngine:
    """
    Core decision-making logic using multi-factor analysis.
    
    Combines signals from:
    - Market conditions (RSI, momentum, volatility)
    - Performance metrics (win rate, drawdown, streaks)
    - Learned patterns (from Learning Store)
    - Risk assessment (position size, exposure)
    """
    
    # Factor weights (should sum to 1.0)
    WEIGHTS = {
        "market_momentum": 0.15,
        "rsi_signal": 0.10,
        "volatility": 0.10,
        "regime": 0.15,
        "performance": 0.15,
        "risk": 0.15,
        "patterns": 0.10,
        "time_context": 0.10,
    }
    
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
    
    def evaluate_factors(
        self,
        market: MarketSnapshot,
        positions: list[PositionSnapshot],
        performance: PerformanceSnapshot,
    ) -> list[Factor]:
        """
        Evaluate all decision factors.
        
        Returns:
            List of Factor objects with scores and weights.
        """
        factors = []
        
        # Market Momentum
        momentum_score = self._normalize(market.momentum, -1, 1)
        factors.append(Factor(
            name="market_momentum",
            weight=self.WEIGHTS["market_momentum"],
            score=momentum_score,
            direction="bullish" if momentum_score > 0.2 else ("bearish" if momentum_score < -0.2 else "neutral"),
            description=f"Momentum: {market.momentum:.2f}",
        ))
        
        # RSI Signal
        rsi_score = self._rsi_to_score(market.rsi)
        factors.append(Factor(
            name="rsi_signal",
            weight=self.WEIGHTS["rsi_signal"],
            score=rsi_score,
            direction="bullish" if market.rsi < 30 else ("bearish" if market.rsi > 70 else "neutral"),
            description=f"RSI: {market.rsi:.1f}",
        ))
        
        # Volatility
        vol_score = self._volatility_score(market.volatility)
        factors.append(Factor(
            name="volatility",
            weight=self.WEIGHTS["volatility"],
            score=vol_score,
            direction="caution" if market.volatility > 0.03 else "neutral",
            description=f"Volatility: {market.volatility:.2%}",
        ))
        
        # Regime
        regime_score = self._regime_score(market.regime, market.regime_confidence)
        factors.append(Factor(
            name="regime",
            weight=self.WEIGHTS["regime"],
            score=regime_score,
            direction="bullish" if regime_score > 0.3 else ("bearish" if regime_score < -0.3 else "neutral"),
            description=f"Regime: {market.regime.value} ({market.regime_confidence:.0%})",
        ))
        
        # Performance
        perf_score = self._performance_score(performance)
        factors.append(Factor(
            name="performance",
            weight=self.WEIGHTS["performance"],
            score=perf_score,
            direction="caution" if perf_score < -0.3 else ("bullish" if perf_score > 0.3 else "neutral"),
            description=f"Win rate: {performance.weekly_win_rate:.0%}, Streak: {performance.current_streak}",
        ))
        
        # Risk
        risk_score = self._risk_score(positions, performance)
        factors.append(Factor(
            name="risk",
            weight=self.WEIGHTS["risk"],
            score=risk_score,
            direction="caution" if risk_score < -0.3 else "neutral",
            description=f"Drawdown: {performance.current_drawdown:.1%}",
        ))
        
        # Patterns (from database)
        pattern_score = self._pattern_score(market)
        factors.append(Factor(
            name="patterns",
            weight=self.WEIGHTS["patterns"],
            score=pattern_score,
            direction="bullish" if pattern_score > 0.2 else ("bearish" if pattern_score < -0.2 else "neutral"),
            description="Learned pattern signals",
        ))
        
        # Time Context
        time_score = self._time_score(market)
        factors.append(Factor(
            name="time_context",
            weight=self.WEIGHTS["time_context"],
            score=time_score,
            direction="caution" if time_score < -0.2 else "neutral",
            description=f"Hour: {market.hour_of_day}, Day: {market.day_of_week}",
        ))
        
        return factors
    
    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize a value to -1 to 1 range."""
        if max_val == min_val:
            return 0
        return max(-1, min(1, 2 * (value - min_val) / (max_val - min_val) - 1))
    
    def _rsi_to_score(self, rsi: float) -> float:
        """Convert RSI to a score (-1 to 1)."""
        if rsi < 30:
            return (30 - rsi) / 30  # Oversold = bullish signal
        elif rsi > 70:
            return -(rsi - 70) / 30  # Overbought = bearish signal
        else:
            return 0
    
    def _volatility_score(self, volatility: float) -> float:
        """
        Convert volatility to a score.
        High volatility = negative (caution), Low = positive.
        """
        # Optimal volatility around 1-2%
        if volatility < 0.01:
            return 0.2  # Low vol - slightly positive
        elif volatility < 0.02:
            return 0.5  # Good vol range
        elif volatility < 0.03:
            return 0.0  # Neutral
        elif volatility < 0.04:
            return -0.3  # Elevated
        else:
            return -0.7  # High vol - caution
    
    def _regime_score(self, regime: MarketRegime, confidence: float) -> float:
        """Convert regime to directional score."""
        base_scores = {
            MarketRegime.BULLISH: 0.7,
            MarketRegime.TRENDING_UP: 0.5,
            MarketRegime.NEUTRAL: 0.0,
            MarketRegime.VOLATILE: -0.2,
            MarketRegime.TRENDING_DOWN: -0.5,
            MarketRegime.BEARISH: -0.7,
        }
        base = base_scores.get(regime, 0)
        return base * confidence
    
    def _performance_score(self, performance: PerformanceSnapshot) -> float:
        """Score based on recent performance."""
        score = 0.0
        
        # Win rate contribution
        wr_deviation = performance.weekly_win_rate - 0.5
        score += wr_deviation * 0.5
        
        # Streak contribution
        if performance.current_streak > 0:
            score += min(performance.current_streak / 5, 0.3)
        else:
            score += max(performance.current_streak / 5, -0.5)
        
        # Drawdown penalty
        if performance.current_drawdown > 0.10:
            score -= 0.4
        elif performance.current_drawdown > 0.05:
            score -= 0.2
        
        return max(-1, min(1, score))
    
    def _risk_score(
        self,
        positions: list[PositionSnapshot],
        performance: PerformanceSnapshot,
    ) -> float:
        """Score based on risk levels."""
        score = 0.5  # Start positive
        
        # Position concentration
        if positions:
            max_pnl_pct = max(abs(p.unrealized_pnl_pct) for p in positions)
            if max_pnl_pct > 5:
                score -= 0.3
        
        # Drawdown impact
        if performance.current_drawdown > self.config.thresholds.emergency_drawdown_pct:
            score = -1.0  # Maximum caution
        elif performance.current_drawdown > 0.10:
            score -= 0.4
        elif performance.current_drawdown > 0.05:
            score -= 0.2
        
        return max(-1, min(1, score))
    
    def _pattern_score(self, market: MarketSnapshot) -> float:
        """Get aggregate score from matched patterns."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get recent successful patterns for current regime
            cursor.execute("""
                SELECT AVG(
                    CASE 
                        WHEN SuccessRate > 0.6 THEN (SuccessRate - 0.5) * 2
                        WHEN SuccessRate < 0.4 THEN (SuccessRate - 0.5) * 2
                        ELSE 0 
                    END
                ) * Confidence
                FROM Patterns
                WHERE Status = 'ACTIVE'
                AND Conditions LIKE ?
                AND Confidence >= 0.5
            """, (f"%{market.regime.value}%",))
            
            row = cursor.fetchone()
            cursor.close()
            
            if row and row[0]:
                return float(row[0])
            
        except Exception as e:
            logger.debug(f"Pattern score lookup failed: {e}")
        
        return 0.0
    
    def _time_score(self, market: MarketSnapshot) -> float:
        """Score based on time of day and week."""
        score = 0.0
        
        # First hour (9:30-10:30) - more volatile
        if market.hour_of_day == 9:
            score -= 0.2
        # Last hour (3:00-4:00) - closing adjustments
        elif market.hour_of_day == 15:
            score -= 0.1
        # Mid-day (11-14) - usually calmer
        elif 11 <= market.hour_of_day <= 14:
            score += 0.1
        
        # Monday/Friday typically more volatile
        if market.day_of_week in (0, 4):
            score -= 0.1
        
        return score
    
    def aggregate_score(self, factors: list[Factor]) -> tuple[float, float]:
        """
        Aggregate all factor scores into overall score and confidence.
        
        Returns:
            Tuple of (aggregate_score, confidence)
        """
        if not factors:
            return 0.0, 0.0
        
        # Weighted sum
        total_score = sum(f.weighted_score for f in factors)
        
        # Confidence based on factor agreement
        directions = [f.direction for f in factors if f.direction != "neutral"]
        if directions:
            most_common = max(set(directions), key=directions.count)
            agreement = directions.count(most_common) / len(directions)
        else:
            agreement = 0.5
        
        # Base confidence from score magnitude + agreement
        base_confidence = abs(total_score) * 0.5 + agreement * 0.5
        
        # Reduce confidence if there are caution signals
        caution_count = sum(1 for f in factors if f.direction == "caution")
        if caution_count > 0:
            base_confidence *= (1 - 0.1 * caution_count)
        
        return total_score, min(base_confidence, 1.0)
    
    def determine_action(
        self,
        score: float,
        confidence: float,
        factors: list[Factor],
        market: MarketSnapshot,
        performance: PerformanceSnapshot,
    ) -> Decision:
        """
        Determine what action to take based on score and confidence.
        
        Returns:
            Decision object with recommended action.
        """
        contributing = [
            f"{f.name}: {f.description} ({f.direction})"
            for f in factors
            if abs(f.weighted_score) > 0.05
        ]
        
        # Check for emergency conditions
        risk_factor = next((f for f in factors if f.name == "risk"), None)
        if risk_factor and risk_factor.score <= -0.8:
            return Decision(
                decision_type=DecisionType.EMERGENCY_STOP,
                action="HALT_TRADING",
                confidence=1.0,
                reasoning="Critical risk level detected",
                contributing_factors=contributing,
                market_snapshot=market,
                performance_snapshot=performance,
            )
        
        # High confidence bullish/bearish signals
        if confidence >= self.config.thresholds.min_confidence_to_act:
            if score > 0.3:
                return Decision(
                    decision_type=DecisionType.REGIME_ADAPTATION,
                    action="INCREASE_EXPOSURE",
                    confidence=confidence,
                    reasoning=f"Bullish signals with {confidence:.0%} confidence (score: {score:.2f})",
                    contributing_factors=contributing,
                    market_snapshot=market,
                    performance_snapshot=performance,
                )
            elif score < -0.3:
                return Decision(
                    decision_type=DecisionType.RISK_SCALING,
                    action="REDUCE_EXPOSURE",
                    confidence=confidence,
                    reasoning=f"Bearish/caution signals with {confidence:.0%} confidence (score: {score:.2f})",
                    contributing_factors=contributing,
                    market_snapshot=market,
                    performance_snapshot=performance,
                )
        
        # Moderate signals - suggest parameter adjustments
        if abs(score) > 0.2 and confidence >= 0.5:
            if score > 0:
                return Decision(
                    decision_type=DecisionType.TIMING_OPTIMIZATION,
                    action="OPTIMIZE_ENTRY",
                    confidence=confidence,
                    reasoning=f"Moderate bullish signals suggest entry optimization",
                    contributing_factors=contributing,
                    market_snapshot=market,
                    performance_snapshot=performance,
                )
            else:
                return Decision(
                    decision_type=DecisionType.TIMING_OPTIMIZATION,
                    action="OPTIMIZE_EXIT",
                    confidence=confidence,
                    reasoning=f"Moderate caution signals suggest exit optimization",
                    contributing_factors=contributing,
                    market_snapshot=market,
                    performance_snapshot=performance,
                )
        
        # No significant action
        return Decision(
            decision_type=DecisionType.NO_ACTION,
            action="CONTINUE",
            confidence=1.0 - abs(score),
            reasoning=f"No significant signals (score: {score:.2f}, confidence: {confidence:.0%})",
            contributing_factors=contributing,
            market_snapshot=market,
            performance_snapshot=performance,
        )
    
    def evaluate(
        self,
        market: MarketSnapshot,
        positions: list[PositionSnapshot],
        performance: PerformanceSnapshot,
    ) -> Decision:
        """
        Full evaluation pipeline.
        
        Returns:
            Decision based on all factors.
        """
        factors = self.evaluate_factors(market, positions, performance)
        score, confidence = self.aggregate_score(factors)
        decision = self.determine_action(score, confidence, factors, market, performance)
        
        logger.debug(
            f"Decision Engine: score={score:.2f}, confidence={confidence:.2f}, "
            f"decision={decision.decision_type.value}"
        )
        
        return decision
    
    def close(self):
        """Close database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
