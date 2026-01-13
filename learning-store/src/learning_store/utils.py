"""
Utility functions for the Learning Store.
"""

from datetime import datetime, timedelta
from typing import Any, Optional
import json
import numpy as np


def calculate_confidence_decay(
    base_confidence: float,
    days_since_update: int,
    decay_rate: float = 0.95
) -> float:
    """
    Calculate decayed confidence based on time since last update.
    
    Args:
        base_confidence: Original confidence score
        days_since_update: Days since the pattern was last validated
        decay_rate: Daily decay multiplier (default 0.95 = 5% daily decay)
    
    Returns:
        Decayed confidence score
    """
    return base_confidence * (decay_rate ** days_since_update)


def calculate_combined_confidence(
    confidences: list[float],
    weights: Optional[list[float]] = None
) -> float:
    """
    Combine multiple confidence scores into one.
    
    Uses weighted average if weights provided, otherwise simple average.
    """
    if not confidences:
        return 0.0
    
    if weights:
        if len(weights) != len(confidences):
            raise ValueError("Weights must match confidences length")
        return sum(c * w for c, w in zip(confidences, weights)) / sum(weights)
    
    return sum(confidences) / len(confidences)


def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    Calculate the Sharpe ratio for a series of returns.
    
    Args:
        returns: List of period returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of trading periods per year
    
    Returns:
        Annualized Sharpe ratio
    """
    if not returns or len(returns) < 2:
        return 0.0
    
    returns_arr = np.array(returns)
    excess_returns = returns_arr - (risk_free_rate / periods_per_year)
    
    mean_return = np.mean(excess_returns)
    std_return = np.std(excess_returns, ddof=1)
    
    if std_return == 0:
        return 0.0
    
    return (mean_return / std_return) * np.sqrt(periods_per_year)


def calculate_max_drawdown(equity_curve: list[float]) -> float:
    """
    Calculate the maximum drawdown from an equity curve.
    
    Returns drawdown as a positive percentage (e.g., 0.15 = 15% drawdown).
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    equity = np.array(equity_curve)
    peak = np.maximum.accumulate(equity)
    drawdown = (peak - equity) / peak
    
    return float(np.max(drawdown))


def calculate_profit_factor(
    wins: list[float],
    losses: list[float]
) -> float:
    """
    Calculate profit factor (gross profit / gross loss).
    
    Returns infinity if no losses, 0 if no wins.
    """
    total_wins = sum(abs(w) for w in wins if w > 0)
    total_losses = sum(abs(l) for l in losses if l < 0)
    
    if total_losses == 0:
        return float('inf') if total_wins > 0 else 0.0
    
    return total_wins / total_losses


def format_recommendation_text(
    parameter_name: str,
    current_value: Any,
    recommended_value: Any,
    confidence: float,
    reasoning: str
) -> str:
    """Format a recommendation as human-readable text."""
    confidence_level = (
        "High" if confidence >= 0.8 else
        "Medium" if confidence >= 0.5 else
        "Low"
    )
    
    return f"""
**Parameter Recommendation: {parameter_name}**
- Current Value: {current_value}
- Recommended Value: {recommended_value}
- Confidence: {confidence:.1%} ({confidence_level})
- Reasoning: {reasoning}
""".strip()


def safe_json_serialize(obj: Any) -> str:
    """Safely serialize an object to JSON, handling special types."""
    
    def default_handler(o):
        if isinstance(o, datetime):
            return o.isoformat()
        elif isinstance(o, np.integer):
            return int(o)
        elif isinstance(o, np.floating):
            return float(o)
        elif isinstance(o, np.ndarray):
            return o.tolist()
        elif hasattr(o, 'value'):  # Enum
            return o.value
        elif hasattr(o, '__dict__'):
            return o.__dict__
        return str(o)
    
    return json.dumps(obj, default=default_handler)


def parse_parameter_value(value_str: str, data_type: str = "auto") -> Any:
    """
    Parse a parameter value string to the appropriate type.
    
    Args:
        value_str: String representation of the value
        data_type: Expected type ('int', 'float', 'bool', 'str', 'auto')
    
    Returns:
        Parsed value in appropriate type
    """
    if data_type == "int":
        return int(float(value_str))
    elif data_type == "float":
        return float(value_str)
    elif data_type == "bool":
        return value_str.lower() in ("true", "1", "yes", "on")
    elif data_type == "str":
        return str(value_str)
    elif data_type == "auto":
        # Try to infer type
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            if value_str.lower() in ("true", "false"):
                return value_str.lower() == "true"
            return value_str
    
    return value_str


def time_bucket(hour: int) -> str:
    """
    Convert hour to trading time bucket.
    
    Returns bucket name like 'pre_market', 'morning', 'midday', 'afternoon', 'close'.
    """
    if hour < 9:
        return "pre_market"
    elif hour < 11:
        return "morning"
    elif hour < 13:
        return "midday"
    elif hour < 15:
        return "afternoon"
    else:
        return "close"


def regime_to_symbol_bias(regime: str) -> dict:
    """
    Get symbol trading bias based on market regime.
    
    Returns dict with 'TQQQ' and 'SQQQ' bias scores.
    """
    regime_biases = {
        "BULLISH": {"TQQQ": 0.8, "SQQQ": 0.2},
        "BEARISH": {"TQQQ": 0.2, "SQQQ": 0.8},
        "NEUTRAL": {"TQQQ": 0.5, "SQQQ": 0.5},
        "VOLATILE": {"TQQQ": 0.4, "SQQQ": 0.4},
        "TRENDING_UP": {"TQQQ": 0.7, "SQQQ": 0.3},
        "TRENDING_DOWN": {"TQQQ": 0.3, "SQQQ": 0.7}
    }
    
    return regime_biases.get(regime, {"TQQQ": 0.5, "SQQQ": 0.5})


def calculate_position_size(
    confidence: float,
    base_size: float,
    max_size: float,
    min_size: float
) -> float:
    """
    Calculate position size based on confidence level.
    
    Args:
        confidence: Pattern/recommendation confidence (0-1)
        base_size: Base position size as fraction of portfolio
        max_size: Maximum position size
        min_size: Minimum position size
    
    Returns:
        Recommended position size as portfolio fraction
    """
    # Scale size with confidence
    size = base_size * (0.5 + 0.5 * confidence)
    
    # Clamp to bounds
    return max(min_size, min(max_size, size))
