"""Fixtures package."""

from .market_data import (
    generate_price_series,
    generate_market_data,
    calculate_indicators,
    sample_market_conditions,
)
from .trade_data import (
    generate_trade,
    generate_trade_history,
    calculate_trade_stats,
    generate_losing_streak,
    generate_winning_streak,
    sample_performance_scenarios,
)
from .mock_responses import (
    mock_mcp_response,
    mock_backtest_result,
    mock_pattern_response,
    mock_recommendation_response,
    mock_alpaca_account,
    mock_alpaca_positions,
    mock_strategy_parameters,
    mock_error_response,
)

__all__ = [
    "generate_price_series",
    "generate_market_data",
    "calculate_indicators",
    "sample_market_conditions",
    "generate_trade",
    "generate_trade_history",
    "calculate_trade_stats",
    "generate_losing_streak",
    "generate_winning_streak",
    "sample_performance_scenarios",
    "mock_mcp_response",
    "mock_backtest_result",
    "mock_pattern_response",
    "mock_recommendation_response",
    "mock_alpaca_account",
    "mock_alpaca_positions",
    "mock_strategy_parameters",
    "mock_error_response",
]
