"""
Analytics Module
================
Advanced analytics and performance calculations for Trade-Mind MCP.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """Market regime types."""
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNKNOWN = "UNKNOWN"


class CorrectionPriority(str, Enum):
    """Priority levels for corrections."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Correction:
    """A suggested correction to strategy parameters."""
    type: str
    priority: CorrectionPriority
    param_name: str
    current_value: Any
    suggested_value: Any
    observation: str
    suggestion: str
    confidence: float
    data_support: Dict[str, Any]


class PerformanceAnalyzer:
    """
    Analyzes trading performance and generates insights.
    """
    
    def __init__(self, min_trades: int = 5, min_confidence: float = 0.6):
        self.min_trades = min_trades
        self.min_confidence = min_confidence
    
    def grade_performance(self, stats: Dict[str, Any]) -> str:
        """
        Grade overall performance A-F.
        
        Criteria:
        - A: Win rate >60%, Profit factor >2.0, Low drawdown
        - B: Win rate >55%, Profit factor >1.5
        - C: Win rate >50%, Profit factor >1.2
        - D: Win rate >45%, Profit factor >1.0
        - F: Below D thresholds
        """
        score = 0
        
        win_rate = stats.get("win_rate", 0)
        profit_factor = stats.get("profit_factor", 0)
        max_drawdown = abs(stats.get("max_drawdown", 0))
        
        # Win rate scoring
        if win_rate > 0.60:
            score += 3
        elif win_rate > 0.55:
            score += 2
        elif win_rate > 0.50:
            score += 1
        elif win_rate > 0.45:
            score += 0.5
        
        # Profit factor scoring
        if profit_factor > 2.0:
            score += 3
        elif profit_factor > 1.5:
            score += 2
        elif profit_factor > 1.2:
            score += 1
        elif profit_factor > 1.0:
            score += 0.5
        
        # Drawdown penalty
        if max_drawdown > 0.20:
            score -= 2
        elif max_drawdown > 0.15:
            score -= 1
        elif max_drawdown > 0.10:
            score -= 0.5
        
        # Grade mapping
        if score >= 5:
            return "A"
        elif score >= 4:
            return "B"
        elif score >= 2.5:
            return "C"
        elif score >= 1.5:
            return "D"
        else:
            return "F"
    
    def analyze_trade_patterns(
        self,
        trades: List[Dict[str, Any]],
        outcome_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze patterns in trades.
        
        Args:
            trades: List of trade records
            outcome_filter: 'winning', 'losing', or None for all
        
        Returns:
            Pattern analysis results
        """
        if not trades:
            return {"success": False, "error": "No trades to analyze"}
        
        # Filter trades
        if outcome_filter == "winning":
            filtered = [t for t in trades if (t.get("RealizedPnL") or 0) > 0]
        elif outcome_filter == "losing":
            filtered = [t for t in trades if (t.get("RealizedPnL") or 0) < 0]
        else:
            filtered = trades
        
        if not filtered:
            return {"success": False, "error": f"No {outcome_filter or 'matching'} trades found"}
        
        # Analyze by entry reason
        entry_reasons = {}
        for trade in filtered:
            reason = trade.get("EntryReason", "UNKNOWN")
            if reason not in entry_reasons:
                entry_reasons[reason] = {"count": 0, "total_pnl": 0, "wins": 0}
            entry_reasons[reason]["count"] += 1
            entry_reasons[reason]["total_pnl"] += trade.get("RealizedPnL", 0)
            if (trade.get("RealizedPnL") or 0) > 0:
                entry_reasons[reason]["wins"] += 1
        
        # Calculate win rate per reason
        for reason in entry_reasons:
            count = entry_reasons[reason]["count"]
            entry_reasons[reason]["win_rate"] = entry_reasons[reason]["wins"] / count if count > 0 else 0
            entry_reasons[reason]["avg_pnl"] = entry_reasons[reason]["total_pnl"] / count if count > 0 else 0
        
        # Analyze by exit reason
        exit_reasons = {}
        for trade in filtered:
            reason = trade.get("ExitReason", "UNKNOWN")
            if reason not in exit_reasons:
                exit_reasons[reason] = {"count": 0, "total_pnl": 0}
            exit_reasons[reason]["count"] += 1
            exit_reasons[reason]["total_pnl"] += trade.get("RealizedPnL", 0)
        
        for reason in exit_reasons:
            count = exit_reasons[reason]["count"]
            exit_reasons[reason]["avg_pnl"] = exit_reasons[reason]["total_pnl"] / count if count > 0 else 0
        
        # Analyze by time of day
        hour_performance = {}
        for trade in filtered:
            entry_time = trade.get("EntryTime")
            if entry_time:
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time)
                hour = entry_time.hour
                if hour not in hour_performance:
                    hour_performance[hour] = {"count": 0, "total_pnl": 0, "wins": 0}
                hour_performance[hour]["count"] += 1
                hour_performance[hour]["total_pnl"] += trade.get("RealizedPnL", 0)
                if (trade.get("RealizedPnL") or 0) > 0:
                    hour_performance[hour]["wins"] += 1
        
        for hour in hour_performance:
            count = hour_performance[hour]["count"]
            hour_performance[hour]["win_rate"] = hour_performance[hour]["wins"] / count if count > 0 else 0
        
        # Find best/worst patterns
        best_entry = max(entry_reasons.items(), key=lambda x: x[1]["win_rate"]) if entry_reasons else None
        worst_entry = min(entry_reasons.items(), key=lambda x: x[1]["win_rate"]) if entry_reasons else None
        best_hour = max(hour_performance.items(), key=lambda x: x[1]["win_rate"]) if hour_performance else None
        
        # Analyze holding time
        holding_times = [t.get("HoldingPeriodSeconds", 0) for t in filtered if t.get("HoldingPeriodSeconds")]
        avg_holding = sum(holding_times) / len(holding_times) if holding_times else 0
        
        # Winning vs losing holding times
        winning_holds = [t.get("HoldingPeriodSeconds", 0) for t in filtered 
                        if (t.get("RealizedPnL") or 0) > 0 and t.get("HoldingPeriodSeconds")]
        losing_holds = [t.get("HoldingPeriodSeconds", 0) for t in filtered 
                       if (t.get("RealizedPnL") or 0) < 0 and t.get("HoldingPeriodSeconds")]
        
        avg_winning_hold = sum(winning_holds) / len(winning_holds) if winning_holds else 0
        avg_losing_hold = sum(losing_holds) / len(losing_holds) if losing_holds else 0
        
        return {
            "success": True,
            "total_trades_analyzed": len(filtered),
            "filter_applied": outcome_filter or "all",
            "entry_patterns": entry_reasons,
            "exit_patterns": exit_reasons,
            "hourly_performance": hour_performance,
            "insights": {
                "best_entry_reason": best_entry[0] if best_entry else None,
                "best_entry_win_rate": best_entry[1]["win_rate"] if best_entry else None,
                "worst_entry_reason": worst_entry[0] if worst_entry else None,
                "worst_entry_win_rate": worst_entry[1]["win_rate"] if worst_entry else None,
                "best_trading_hour": best_hour[0] if best_hour else None,
                "best_hour_win_rate": best_hour[1]["win_rate"] if best_hour else None
            },
            "holding_time_analysis": {
                "avg_holding_seconds": avg_holding,
                "avg_holding_minutes": avg_holding / 60,
                "avg_winning_hold_seconds": avg_winning_hold,
                "avg_losing_hold_seconds": avg_losing_hold,
                "observation": "Winners held longer" if avg_winning_hold > avg_losing_hold else "Losers held longer"
            }
        }
    
    def generate_corrections(
        self,
        stats: Dict[str, Any],
        current_params: Dict[str, Any],
        optimal_params: List[Dict[str, Any]],
        current_regime: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate data-driven correction suggestions.
        
        Args:
            stats: Current performance statistics
            current_params: Current parameter values
            optimal_params: Optimal parameters from database
            current_regime: Current market regime
        
        Returns:
            List of correction suggestions
        """
        corrections = []
        regime_type = current_regime.get("regime", {}).get("RegimeType", "UNKNOWN")
        
        # Win rate analysis
        win_rate = stats.get("win_rate", 0)
        if win_rate < 0.40:
            # Find optimal RSI oversold
            rsi_optimal = next(
                (p for p in optimal_params if p.get("ParamName") == "rsi_oversold"),
                None
            )
            corrections.append({
                "type": "ENTRY_CRITERIA",
                "priority": "HIGH",
                "param_name": "rsi_oversold",
                "current_value": current_params.get("rsi_oversold", 30),
                "suggested_value": rsi_optimal.get("OptimalValue", 25) if rsi_optimal else 25,
                "observation": f"Win rate {win_rate:.1%} below 40% threshold",
                "suggestion": "Tighten RSI oversold threshold for better entries",
                "confidence": rsi_optimal.get("ConfidenceScore", 0.6) if rsi_optimal else 0.6,
                "data_support": {
                    "optimal_value_regime": regime_type,
                    "sample_size": rsi_optimal.get("SampleSize", 0) if rsi_optimal else 0
                }
            })
        
        # Profit factor analysis
        profit_factor = stats.get("profit_factor", 0)
        if profit_factor < 1.2:
            corrections.append({
                "type": "EXIT_CRITERIA",
                "priority": "MEDIUM",
                "param_name": "take_profit_pct",
                "current_value": current_params.get("take_profit_pct", 0.015),
                "suggested_value": 0.02,
                "observation": f"Profit factor {profit_factor:.2f} indicates poor risk/reward",
                "suggestion": "Increase take profit target to improve risk/reward",
                "confidence": 0.65,
                "data_support": {
                    "avg_win": stats.get("avg_win", 0),
                    "avg_loss": stats.get("avg_loss", 0)
                }
            })
        
        # Drawdown analysis
        max_drawdown = abs(stats.get("max_drawdown", 0))
        if max_drawdown > 0.15:
            corrections.append({
                "type": "RISK_MANAGEMENT",
                "priority": "CRITICAL",
                "param_name": "position_size_level1",
                "current_value": current_params.get("position_size_level1", 0.5),
                "suggested_value": 0.35,
                "observation": f"Max drawdown {max_drawdown:.1%} exceeds 15% limit",
                "suggestion": "Reduce position size until drawdown recovers",
                "confidence": 0.85,
                "data_support": {
                    "current_drawdown": max_drawdown,
                    "threshold": 0.15
                }
            })
        
        # Regime-specific suggestions
        if regime_type == "HIGH_VOLATILITY":
            corrections.append({
                "type": "REGIME_ADAPTATION",
                "priority": "MEDIUM",
                "param_name": "stop_loss_pct",
                "current_value": current_params.get("stop_loss_pct", 0.02),
                "suggested_value": 0.025,
                "observation": f"High volatility regime detected",
                "suggestion": "Widen stop loss to avoid whipsaws in volatile market",
                "confidence": 0.7,
                "data_support": {
                    "regime": regime_type,
                    "volatility": current_regime.get("regime", {}).get("Volatility", "HIGH")
                }
            })
        elif regime_type == "RANGING":
            corrections.append({
                "type": "REGIME_ADAPTATION",
                "priority": "LOW",
                "param_name": "trading_enabled",
                "current_value": True,
                "suggested_value": "REDUCE_SIZE",
                "observation": f"Ranging market detected - trend strategies underperform",
                "suggestion": "Consider reducing position sizes or pausing in ranging markets",
                "confidence": 0.6,
                "data_support": {
                    "regime": regime_type,
                    "trend_direction": current_regime.get("regime", {}).get("TrendDirection", "NEUTRAL")
                }
            })
        
        # Sort by priority
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        corrections.sort(key=lambda x: priority_order.get(x["priority"], 99))
        
        return corrections
    
    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.05,
        periods_per_year: int = 252
    ) -> float:
        """Calculate annualized Sharpe ratio."""
        if not returns or len(returns) < 2:
            return 0.0
        
        import statistics
        
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize
        excess_return = avg_return - (risk_free_rate / periods_per_year)
        sharpe = (excess_return / std_return) * (periods_per_year ** 0.5)
        
        return sharpe
    
    def detect_regime_from_data(
        self,
        prices: List[float],
        lookback: int = 20
    ) -> Dict[str, Any]:
        """
        Detect market regime from price data.
        
        Simple regime detection based on:
        - Trend: Price position relative to moving average
        - Volatility: Recent range vs historical
        """
        if len(prices) < lookback:
            return {
                "regime_type": MarketRegime.UNKNOWN.value,
                "confidence": 0.3,
                "trend_direction": "NEUTRAL"
            }
        
        recent = prices[-lookback:]
        
        # Calculate simple moving average
        sma = sum(recent) / len(recent)
        current = prices[-1]
        
        # Trend detection
        pct_from_sma = (current - sma) / sma if sma > 0 else 0
        
        if pct_from_sma > 0.02:
            trend = "UP"
        elif pct_from_sma < -0.02:
            trend = "DOWN"
        else:
            trend = "NEUTRAL"
        
        # Volatility detection (using range)
        high = max(recent)
        low = min(recent)
        range_pct = (high - low) / sma if sma > 0 else 0
        
        if range_pct > 0.08:
            volatility = "HIGH"
        elif range_pct < 0.03:
            volatility = "LOW"
        else:
            volatility = "NORMAL"
        
        # Determine regime
        if volatility == "HIGH":
            regime = MarketRegime.HIGH_VOLATILITY
        elif trend == "UP" and volatility != "HIGH":
            regime = MarketRegime.TRENDING_UP
        elif trend == "DOWN" and volatility != "HIGH":
            regime = MarketRegime.TRENDING_DOWN
        elif trend == "NEUTRAL":
            regime = MarketRegime.RANGING
        else:
            regime = MarketRegime.UNKNOWN
        
        # Confidence based on clarity of signal
        confidence = 0.5
        if abs(pct_from_sma) > 0.05:
            confidence += 0.2
        if range_pct > 0.05 or range_pct < 0.02:
            confidence += 0.1
        
        return {
            "regime_type": regime.value,
            "confidence": min(confidence, 0.9),
            "trend_direction": trend,
            "volatility": volatility,
            "pct_from_sma": pct_from_sma,
            "range_pct": range_pct
        }


# Global analyzer instance
_analyzer: Optional[PerformanceAnalyzer] = None


def get_analyzer() -> PerformanceAnalyzer:
    """Get the global analyzer instance."""
    global _analyzer
    if _analyzer is None:
        from .config import get_config
        config = get_config()
        _analyzer = PerformanceAnalyzer(
            min_trades=config.analysis.min_trades_for_stats,
            min_confidence=config.analysis.min_confidence_threshold
        )
    return _analyzer
