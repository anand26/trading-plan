"""
Test fixtures - Mock response generators.
"""

from datetime import datetime
from typing import Any


def mock_mcp_response(success: bool = True, data: Any = None) -> dict:
    """Generate a mock MCP response."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "success": success,
            "data": data or {},
            "timestamp": datetime.now().isoformat(),
        }
    }


def mock_backtest_result(
    total_return: float = 0.15,
    sharpe_ratio: float = 1.5,
    max_drawdown: float = 0.08,
    total_trades: int = 100,
) -> dict:
    """Generate a mock backtest result."""
    return {
        "backtest_id": "BT_12345",
        "status": "completed",
        "metrics": {
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "total_trades": total_trades,
            "win_rate": 0.55,
            "profit_factor": 1.8,
            "avg_trade_duration_minutes": 45,
        },
        "trades": [],
        "equity_curve": [],
        "started_at": datetime.now().isoformat(),
        "completed_at": datetime.now().isoformat(),
    }


def mock_pattern_response(
    pattern_type: str = "ENTRY_TIMING",
    confidence: float = 0.75,
    success_rate: float = 0.62,
) -> dict:
    """Generate a mock pattern response."""
    return {
        "pattern_id": 1,
        "pattern_type": pattern_type,
        "conditions": {
            "regime": "BULLISH",
            "rsi_range": [30, 50],
            "volatility": "low",
        },
        "action": {
            "type": "adjust_entry",
            "parameter": "rsi_entry_threshold",
            "value": 35,
        },
        "confidence": confidence,
        "success_rate": success_rate,
        "occurrences": 25,
        "status": "ACTIVE",
    }


def mock_recommendation_response(
    rec_type: str = "PARAMETER_ADJUSTMENT",
    confidence: float = 0.8,
) -> dict:
    """Generate a mock recommendation response."""
    return {
        "recommendation_id": 1,
        "pattern_id": 1,
        "recommendation_type": rec_type,
        "parameter_name": "stop_loss_pct",
        "old_value": "0.02",
        "new_value": "0.025",
        "reason": "Increased volatility suggests wider stops",
        "confidence": confidence,
        "priority": 1,
        "status": "PENDING",
    }


def mock_alpaca_account() -> dict:
    """Generate a mock Alpaca account response."""
    return {
        "id": "acc_12345",
        "account_number": "PA12345678",
        "status": "ACTIVE",
        "currency": "USD",
        "cash": "50000.00",
        "portfolio_value": "52500.00",
        "buying_power": "100000.00",
        "equity": "52500.00",
        "last_equity": "52000.00",
        "long_market_value": "2500.00",
        "short_market_value": "0.00",
        "initial_margin": "1250.00",
        "maintenance_margin": "750.00",
        "daytrade_count": 2,
        "pattern_day_trader": False,
    }


def mock_alpaca_positions() -> list[dict]:
    """Generate mock Alpaca positions."""
    return [
        {
            "asset_id": "asset_tqqq",
            "symbol": "TQQQ",
            "exchange": "NASDAQ",
            "asset_class": "us_equity",
            "qty": "100",
            "avg_entry_price": "44.50",
            "side": "long",
            "market_value": "4550.00",
            "cost_basis": "4450.00",
            "unrealized_pl": "100.00",
            "unrealized_plpc": "0.0225",
            "current_price": "45.50",
        }
    ]


def mock_db_query_result(
    columns: list[str],
    rows: list[tuple],
) -> list[dict]:
    """Convert mock DB results to list of dicts."""
    return [dict(zip(columns, row)) for row in rows]


def mock_strategy_parameters() -> dict:
    """Generate mock strategy parameters."""
    return {
        "RSI_Entry_Threshold": 35,
        "RSI_Exit_Threshold": 65,
        "Stop_Loss_Pct": 0.02,
        "Take_Profit_Pct": 0.03,
        "Max_Position_Size": 0.20,
        "Scalp_Size": 100,
        "Trading_Enabled": True,
        "Use_Trailing_Stop": True,
        "Trailing_Stop_Pct": 0.015,
    }


def mock_error_response(error_code: int = 500, message: str = "Internal error") -> dict:
    """Generate a mock error response."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": error_code,
            "message": message,
        }
    }
