"""
MCP Tools Module
================
Tool implementations for Trade-Mind MCP server.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

from .config import get_config
from .database import get_db
from .analytics import get_analyzer

logger = logging.getLogger(__name__)


# ============================================
# ANALYTICS TOOLS
# ============================================

async def get_last_trades(
    symbol: Optional[str] = None,
    count: int = 20,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get recent trade history with P&L details.
    
    Args:
        symbol: Filter by symbol (TQQQ, SQQQ, or None for all)
        count: Number of trades to return (default 20)
        session_id: Filter by session ID
    
    Returns:
        List of recent trades with full details
    """
    db = get_db()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    trades = db.get_last_trades(symbol=symbol, count=count, session_id=session_id)
    
    # Calculate summary
    total_pnl = sum(t.get("RealizedPnL", 0) or 0 for t in trades)
    winning = sum(1 for t in trades if (t.get("RealizedPnL") or 0) > 0)
    
    return {
        "success": True,
        "count": len(trades),
        "trades": trades,
        "summary": {
            "total_pnl": total_pnl,
            "winning_trades": winning,
            "losing_trades": len(trades) - winning,
            "win_rate": winning / len(trades) if trades else 0
        },
        "filters": {
            "symbol": symbol,
            "session_id": session_id
        }
    }


async def calculate_win_rate(
    symbol: Optional[str] = None,
    session_id: Optional[str] = None,
    days_back: Optional[int] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive win rate statistics.
    
    Args:
        symbol: Filter by symbol
        session_id: Filter by session
        days_back: Only include trades from last N days
    
    Returns:
        Win rate, profit factor, average win/loss, and more
    """
    db = get_db()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    stats = db.calculate_win_rate(
        symbol=symbol,
        session_id=session_id,
        days_back=days_back
    )
    
    if stats.get("success"):
        # Add grade
        analyzer = get_analyzer()
        stats["performance_grade"] = analyzer.grade_performance(stats)
    
    return stats


async def get_daily_pnl(
    days_back: int = 30,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get daily P&L breakdown and equity curve.
    
    Args:
        days_back: Number of days to retrieve
        session_id: Filter by session
    
    Returns:
        Daily P&L data and summary statistics
    """
    db = get_db()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    daily_data = db.get_daily_pnl(days_back=days_back, session_id=session_id)
    
    if not daily_data:
        return {
            "success": True,
            "count": 0,
            "daily_pnl": [],
            "message": "No daily performance data found"
        }
    
    # Calculate statistics
    pnls = [d.get("RealizedPnL", 0) or 0 for d in daily_data]
    winning_days = sum(1 for p in pnls if p > 0)
    losing_days = sum(1 for p in pnls if p < 0)
    
    return {
        "success": True,
        "count": len(daily_data),
        "daily_pnl": daily_data,
        "statistics": {
            "total_pnl": sum(pnls),
            "avg_daily_pnl": sum(pnls) / len(pnls) if pnls else 0,
            "best_day": max(pnls) if pnls else 0,
            "worst_day": min(pnls) if pnls else 0,
            "winning_days": winning_days,
            "losing_days": losing_days,
            "day_win_rate": winning_days / len(pnls) if pnls else 0
        }
    }


async def analyze_drawdown(
    session_id: Optional[str] = None,
    days_back: int = 30
) -> Dict[str, Any]:
    """
    Analyze drawdown metrics and recovery patterns.
    
    Args:
        session_id: Filter by session
        days_back: Analysis period
    
    Returns:
        Drawdown analysis with max drawdown, recovery times
    """
    db = get_db()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    return db.analyze_drawdown(session_id=session_id, days_back=days_back)


async def get_performance_summary(
    session_id: Optional[str] = None,
    days_back: int = 30
) -> Dict[str, Any]:
    """
    Get comprehensive performance report.
    
    Args:
        session_id: Filter by session
        days_back: Analysis period
    
    Returns:
        Complete performance summary with all metrics
    """
    db = get_db()
    analyzer = get_analyzer()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    # Get all components
    stats = db.calculate_win_rate(session_id=session_id, days_back=days_back)
    drawdown = db.analyze_drawdown(session_id=session_id, days_back=days_back)
    daily = db.get_daily_pnl(days_back=days_back, session_id=session_id)
    regime = db.get_current_regime()
    
    # Calculate grade
    grade = analyzer.grade_performance(stats) if stats.get("success") else "N/A"
    
    # Daily statistics
    daily_pnls = [d.get("RealizedPnL", 0) or 0 for d in daily]
    
    return {
        "success": True,
        "period": f"Last {days_back} days",
        "session_id": session_id,
        "overall_grade": grade,
        "statistics": {
            "total_trades": stats.get("total_trades", 0),
            "win_rate": stats.get("win_rate", 0),
            "profit_factor": stats.get("profit_factor", 0),
            "total_pnl": stats.get("total_pnl", 0),
            "avg_pnl_per_trade": stats.get("avg_pnl", 0),
            "avg_win": stats.get("avg_win", 0),
            "avg_loss": stats.get("avg_loss", 0),
            "max_win": stats.get("max_win", 0),
            "max_loss": stats.get("max_loss", 0)
        },
        "risk_metrics": {
            "max_drawdown": drawdown.get("max_drawdown", 0),
            "current_drawdown": drawdown.get("current_drawdown", 0),
            "drawdown_events": drawdown.get("drawdown_events", 0)
        },
        "daily_metrics": {
            "trading_days": len(daily),
            "winning_days": sum(1 for p in daily_pnls if p > 0),
            "losing_days": sum(1 for p in daily_pnls if p < 0),
            "avg_daily_pnl": sum(daily_pnls) / len(daily_pnls) if daily_pnls else 0
        },
        "current_regime": regime.get("regime", {})
    }


async def analyze_trade_patterns(
    session_id: Optional[str] = None,
    days_back: int = 30,
    outcome_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze patterns in winning/losing trades.
    
    Args:
        session_id: Filter by session
        days_back: Analysis period
        outcome_filter: 'winning', 'losing', or None for all
    
    Returns:
        Pattern analysis with entry/exit/time insights
    """
    db = get_db()
    analyzer = get_analyzer()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    # Get trades
    start_date = date.today() - timedelta(days=days_back)
    trades = db.get_trades_in_range(
        start_date=start_date,
        end_date=date.today()
    )
    
    if session_id:
        trades = [t for t in trades if t.get("SessionId") == session_id]
    
    return analyzer.analyze_trade_patterns(trades, outcome_filter)


# ============================================
# LEARNING TOOLS
# ============================================

async def suggest_corrections(
    session_id: Optional[str] = None,
    strategy_id: str = "TQQQ_SCALPING",
    min_confidence: float = 0.6
) -> Dict[str, Any]:
    """
    Generate AI-driven parameter adjustment suggestions.
    
    Analyzes current performance and suggests data-backed corrections
    based on historical patterns and optimal parameters.
    
    Args:
        session_id: Session to analyze (None for all recent)
        strategy_id: Strategy identifier
        min_confidence: Minimum confidence for suggestions
    
    Returns:
        List of prioritized corrections with data support
    """
    db = get_db()
    analyzer = get_analyzer()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    # Get current statistics
    stats = db.calculate_win_rate(session_id=session_id, days_back=30)
    if not stats.get("success"):
        return {
            "success": False,
            "error": "Insufficient trade data for analysis",
            "minimum_trades_needed": get_config().analysis.min_trades_for_stats
        }
    
    # Get current regime
    regime = db.get_current_regime()
    regime_type = regime.get("regime", {}).get("RegimeType", "UNKNOWN")
    
    # Get optimal parameters for this regime
    optimal_params = db.get_optimal_parameters(strategy_id, regime_type)
    
    # Current parameters (would come from algorithm config, using defaults here)
    current_params = {
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.015,
        "position_size_level1": 0.5
    }
    
    # Generate corrections
    corrections = analyzer.generate_corrections(
        stats=stats,
        current_params=current_params,
        optimal_params=optimal_params,
        current_regime=regime
    )
    
    # Filter by confidence
    corrections = [c for c in corrections if c.get("confidence", 0) >= min_confidence]
    
    # Generate recommendation
    if not corrections:
        recommendation = "Performance is within acceptable parameters. Continue monitoring."
    elif any(c["priority"] == "CRITICAL" for c in corrections):
        recommendation = "CRITICAL: Immediate parameter adjustments recommended to prevent further losses."
    elif any(c["priority"] == "HIGH" for c in corrections):
        recommendation = "HIGH PRIORITY: Consider implementing suggested changes before next trading session."
    else:
        recommendation = "Performance could be improved with suggested optimizations."
    
    return {
        "success": True,
        "session_id": session_id,
        "strategy_id": strategy_id,
        "current_regime": regime_type,
        "performance_grade": analyzer.grade_performance(stats),
        "current_stats": {
            "win_rate": stats.get("win_rate"),
            "profit_factor": stats.get("profit_factor"),
            "total_trades": stats.get("total_trades")
        },
        "corrections": corrections,
        "correction_count": len(corrections),
        "recommendation": recommendation
    }


async def get_optimal_params(
    strategy_id: str = "TQQQ_SCALPING",
    market_regime: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get best parameters for current/specified market regime.
    
    Args:
        strategy_id: Strategy identifier
        market_regime: Specific regime or None for current
    
    Returns:
        Optimal parameters with confidence scores
    """
    db = get_db()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    # Get regime if not specified
    if market_regime is None:
        regime = db.get_current_regime()
        market_regime = regime.get("regime", {}).get("RegimeType", "ALL")
    
    # Get optimal parameters
    params = db.get_optimal_parameters(strategy_id, market_regime)
    
    if not params:
        # Try getting params for ALL regimes
        params = db.get_optimal_parameters(strategy_id, "ALL")
    
    return {
        "success": True,
        "strategy_id": strategy_id,
        "market_regime": market_regime,
        "optimal_parameters": params,
        "count": len(params)
    }


async def record_learning(
    pattern_type: str,
    description: str,
    data: Dict[str, Any],
    confidence: float = 0.5
) -> Dict[str, Any]:
    """
    Store a new pattern or insight in the learning store.
    
    Args:
        pattern_type: Type of pattern (ENTRY_SIGNAL, EXIT_SIGNAL, REGIME_PATTERN, etc.)
        description: Human-readable description
        data: Structured pattern data
        confidence: Confidence score 0-1
    
    Returns:
        Confirmation of stored learning
    """
    db = get_db()
    config = get_config()
    
    if not config.learning.learning_enabled:
        return {
            "success": False,
            "error": "Learning is disabled in configuration"
        }
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    success = db.record_learning(
        pattern_type=pattern_type,
        description=description,
        data=data,
        confidence=confidence
    )
    
    return {
        "success": success,
        "pattern_type": pattern_type,
        "description": description,
        "confidence": confidence,
        "message": "Learning recorded successfully" if success else "Failed to record learning"
    }


async def get_learning_history(
    pattern_type: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Retrieve past learnings and patterns.
    
    Args:
        pattern_type: Filter by type
        min_confidence: Minimum confidence threshold
        limit: Maximum results
    
    Returns:
        List of stored learnings
    """
    db = get_db()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    learnings = db.get_learnings(
        pattern_type=pattern_type,
        min_confidence=min_confidence,
        limit=limit
    )
    
    return {
        "success": True,
        "count": len(learnings),
        "learnings": learnings,
        "filters": {
            "pattern_type": pattern_type,
            "min_confidence": min_confidence
        }
    }


async def compare_parameter_performance(
    param_name: str,
    market_regime: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compare performance of different parameter values.
    
    Args:
        param_name: Parameter to analyze (e.g., 'rsi_oversold')
        market_regime: Filter by regime
    
    Returns:
        Performance comparison across parameter values
    """
    db = get_db()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    performance = db.get_parameter_performance(param_name, market_regime)
    
    if not performance:
        return {
            "success": True,
            "param_name": param_name,
            "message": "No performance data available for this parameter",
            "values": []
        }
    
    # Find best value
    best = max(performance, key=lambda x: (x.get("WinRate", 0), x.get("AvgPnLWhenUsed", 0)))
    
    return {
        "success": True,
        "param_name": param_name,
        "market_regime": market_regime or "ALL",
        "values": performance,
        "best_value": {
            "value": best.get("ParamValue"),
            "win_rate": best.get("WinRate"),
            "avg_pnl": best.get("AvgPnLWhenUsed"),
            "sample_size": best.get("TradeCount")
        }
    }


# ============================================
# REGIME TOOLS
# ============================================

async def detect_market_regime(
    symbol: str = "QQQ",
    lookback_days: int = 20
) -> Dict[str, Any]:
    """
    Identify current market condition.
    
    Args:
        symbol: Symbol to analyze
        lookback_days: Analysis period
    
    Returns:
        Current regime with confidence and characteristics
    """
    db = get_db()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    # Get from database first
    regime = db.get_current_regime(symbol)
    
    if regime.get("success") and regime.get("regime", {}).get("RegimeType") != "UNKNOWN":
        return regime
    
    # If no database regime, return unknown with suggestion
    return {
        "success": True,
        "regime": {
            "RegimeType": "UNKNOWN",
            "TrendDirection": "NEUTRAL",
            "Volatility": "NORMAL",
            "Confidence": 0.3
        },
        "note": "No regime data in database. Run algorithm or analysis to populate.",
        "suggestion": "Consider using external market data to determine regime"
    }


async def get_regime_history(
    symbol: str = "QQQ",
    days_back: int = 30
) -> Dict[str, Any]:
    """
    Get historical regime changes.
    
    Args:
        symbol: Symbol to analyze
        days_back: History period
    
    Returns:
        Regime change history
    """
    db = get_db()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    history = db.get_regime_history(symbol, days_back)
    
    # Calculate regime distribution
    regime_counts = {}
    for r in history:
        regime_type = r.get("RegimeType", "UNKNOWN")
        if regime_type not in regime_counts:
            regime_counts[regime_type] = 0
        regime_counts[regime_type] += 1
    
    return {
        "success": True,
        "symbol": symbol,
        "period_days": days_back,
        "history": history,
        "regime_distribution": regime_counts,
        "dominant_regime": max(regime_counts, key=regime_counts.get) if regime_counts else "UNKNOWN"
    }


async def get_regime_performance(
    session_id: Optional[str] = None,
    days_back: int = 30
) -> Dict[str, Any]:
    """
    Get performance breakdown by market regime.
    
    Args:
        session_id: Filter by session
        days_back: Analysis period
    
    Returns:
        Performance metrics per regime
    """
    db = get_db()
    
    if not db.connected:
        return {"success": False, "error": "Database not connected"}
    
    # Get trades with their regimes
    # This would require joining trades with regime data
    # For now, return structure with placeholder data
    
    return {
        "success": True,
        "note": "Regime performance requires trade-regime correlation in database",
        "suggestion": "Ensure MarketRegimes table is populated during trading",
        "expected_format": {
            "TRENDING_UP": {"trades": 0, "win_rate": 0, "avg_pnl": 0},
            "TRENDING_DOWN": {"trades": 0, "win_rate": 0, "avg_pnl": 0},
            "RANGING": {"trades": 0, "win_rate": 0, "avg_pnl": 0},
            "HIGH_VOLATILITY": {"trades": 0, "win_rate": 0, "avg_pnl": 0}
        }
    }


# ============================================
# UTILITY TOOLS
# ============================================

async def health_check() -> Dict[str, Any]:
    """
    Check health of Trade-Mind services.
    
    Returns:
        Status of database and configuration
    """
    db = get_db()
    config = get_config()
    
    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "connected" if db.connected else "disconnected"
        },
        "configuration": {
            "min_trades_for_stats": config.analysis.min_trades_for_stats,
            "min_confidence_threshold": config.analysis.min_confidence_threshold,
            "lookback_days_default": config.analysis.lookback_days_default,
            "learning_enabled": config.learning.learning_enabled,
            "auto_suggest_enabled": config.learning.auto_suggest_enabled
        }
    }
