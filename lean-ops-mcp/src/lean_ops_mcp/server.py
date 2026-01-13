"""
LEAN-Ops MCP Server
===================
MCP server for QuantConnect LEAN algorithm operations.

This server provides tools for AI agents to:
- Run and manage backtests
- Deploy algorithms to paper/live trading
- Monitor positions and performance
- Update strategy parameters
- Emergency position liquidation

Usage:
    python -m lean_ops_mcp.server
"""

import asyncio
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .config import get_config
from .database import get_db, close_db
from .alpaca_client import close_clients
from . import tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("lean-ops-mcp")


# ============================================
# TOOL DEFINITIONS
# ============================================

TOOLS = [
    Tool(
        name="run_backtest",
        description="""Execute a LEAN backtest with specified parameters.
        
Run a historical backtest of a trading algorithm. Returns comprehensive
performance metrics including Sharpe ratio, win rate, max drawdown, etc.

Use this to:
- Test strategy changes before deployment
- Compare different parameter settings
- Validate algorithm behavior on historical data""",
        inputSchema={
            "type": "object",
            "properties": {
                "algorithm_name": {
                    "type": "string",
                    "description": "Algorithm class name (default: TQQQScalpingAlgorithm)",
                    "default": "TQQQScalpingAlgorithm"
                },
                "start_date": {
                    "type": "string",
                    "description": "Backtest start date (YYYY-MM-DD)",
                    "default": "2024-01-01"
                },
                "end_date": {
                    "type": "string",
                    "description": "Backtest end date (YYYY-MM-DD)",
                    "default": "2024-12-31"
                },
                "initial_cash": {
                    "type": "number",
                    "description": "Starting capital",
                    "default": 100000
                },
                "parameters": {
                    "type": "object",
                    "description": "Strategy parameters to override (e.g., rsi_oversold, stop_loss_pct)",
                    "additionalProperties": True
                }
            }
        }
    ),
    Tool(
        name="get_backtest_results",
        description="""Retrieve detailed results from a completed backtest.
        
Get comprehensive results including all trades, daily performance,
and summary statistics. Use this after run_backtest to analyze
what happened during the simulation.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The backtest session ID"
                }
            },
            "required": ["session_id"]
        }
    ),
    Tool(
        name="list_backtests",
        description="""List available backtest sessions.
        
Get a list of all backtest runs with their summary statistics.
Useful for finding past backtests to compare or analyze.""",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 20
                },
                "status": {
                    "type": "string",
                    "description": "Filter by status (COMPLETED, RUNNING, FAILED)",
                    "enum": ["COMPLETED", "RUNNING", "FAILED"]
                }
            }
        }
    ),
    Tool(
        name="compare_backtests",
        description="""Compare multiple backtest results side by side.
        
Analyze multiple backtests to find the best performing configuration.
Returns comparison table and identifies best performers by different metrics.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of session IDs to compare"
                }
            },
            "required": ["session_ids"]
        }
    ),
    Tool(
        name="deploy_paper",
        description="""Deploy algorithm to Alpaca paper trading.
        
Start paper trading with the specified algorithm. Paper trading
uses simulated money - safe for testing strategies in real-time
market conditions.""",
        inputSchema={
            "type": "object",
            "properties": {
                "algorithm_name": {
                    "type": "string",
                    "description": "Algorithm to deploy",
                    "default": "TQQQScalpingAlgorithm"
                },
                "parameters": {
                    "type": "object",
                    "description": "Strategy parameters",
                    "additionalProperties": True
                }
            }
        }
    ),
    Tool(
        name="deploy_live",
        description="""Deploy algorithm to Alpaca LIVE trading.
        
⚠️ CAUTION: This uses REAL MONEY!
        
Requires:
1. LIVE_DEPLOY_ENABLED=true in environment
2. Correct confirmation code

Only use after thorough paper trading validation.""",
        inputSchema={
            "type": "object",
            "properties": {
                "algorithm_name": {
                    "type": "string",
                    "description": "Algorithm to deploy",
                    "default": "TQQQScalpingAlgorithm"
                },
                "confirm_code": {
                    "type": "string",
                    "description": "Safety confirmation code"
                },
                "parameters": {
                    "type": "object",
                    "description": "Strategy parameters",
                    "additionalProperties": True
                }
            },
            "required": ["confirm_code"]
        }
    ),
    Tool(
        name="stop_algorithm",
        description="""Stop a running algorithm (paper or live).
        
Gracefully stops the algorithm. Does NOT automatically liquidate
positions - use liquidate_positions if needed.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session to stop"
                },
                "mode": {
                    "type": "string",
                    "description": "Trading mode",
                    "enum": ["paper", "live"],
                    "default": "paper"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for stopping",
                    "default": "Manual stop requested"
                }
            }
        }
    ),
    Tool(
        name="get_algorithm_status",
        description="""Get current algorithm status, positions, and P&L.
        
Returns real-time account info, all open positions with P&L,
and current session status. Use this to monitor trading activity.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID (optional)"
                },
                "mode": {
                    "type": "string",
                    "description": "Trading mode",
                    "enum": ["paper", "live"],
                    "default": "paper"
                }
            }
        }
    ),
    Tool(
        name="update_parameters",
        description="""Update strategy parameters (hot reload).
        
Change algorithm parameters without restarting. Parameters are
stored in the database and picked up by the algorithm on next cycle.""",
        inputSchema={
            "type": "object",
            "properties": {
                "algorithm_name": {
                    "type": "string",
                    "description": "Algorithm to update",
                    "default": "TQQQScalpingAlgorithm"
                },
                "parameters": {
                    "type": "object",
                    "description": "New parameter values",
                    "additionalProperties": True
                }
            },
            "required": ["parameters"]
        }
    ),
    Tool(
        name="liquidate_positions",
        description="""Emergency position liquidation.
        
⚠️ CAUTION: Immediately closes positions at MARKET price!
        
Use in emergencies when you need to exit all positions quickly.
For live mode, confirm=true is required.""",
        inputSchema={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "description": "Trading mode",
                    "enum": ["paper", "live"],
                    "default": "paper"
                },
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific symbols to liquidate (empty = all)"
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true for live mode",
                    "default": False
                }
            }
        }
    ),
    Tool(
        name="get_available_algorithms",
        description="""List available algorithms in the LEAN workspace.
        
Returns all Python algorithms that can be run.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="health_check",
        description="""Check health of all connected services.
        
Verify database, LEAN engine, and Alpaca connections are working.
Also shows current configuration settings.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
]


# ============================================
# HANDLERS
# ============================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool called: {name} with args: {arguments}")
    
    try:
        # Route to appropriate tool function
        if name == "run_backtest":
            result = await tools.run_backtest(**arguments)
        elif name == "get_backtest_results":
            result = await tools.get_backtest_results(**arguments)
        elif name == "list_backtests":
            result = await tools.list_backtests(**arguments)
        elif name == "compare_backtests":
            result = await tools.compare_backtests(**arguments)
        elif name == "deploy_paper":
            result = await tools.deploy_paper(**arguments)
        elif name == "deploy_live":
            result = await tools.deploy_live(**arguments)
        elif name == "stop_algorithm":
            result = await tools.stop_algorithm(**arguments)
        elif name == "get_algorithm_status":
            result = await tools.get_algorithm_status(**arguments)
        elif name == "update_parameters":
            result = await tools.update_parameters(**arguments)
        elif name == "liquidate_positions":
            result = await tools.liquidate_positions(**arguments)
        elif name == "get_available_algorithms":
            result = await tools.get_available_algorithms()
        elif name == "health_check":
            result = await tools.health_check()
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        # Format result as text
        import json
        text = json.dumps(result, indent=2, default=str)
        
        return [TextContent(type="text", text=text)]
        
    except Exception as e:
        logger.exception(f"Error in tool {name}")
        error_result = {
            "error": str(e),
            "tool": name,
            "success": False
        }
        import json
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


# ============================================
# MAIN
# ============================================

async def run_server():
    """Run the MCP server."""
    logger.info("Starting LEAN-Ops MCP Server...")
    
    # Initialize database connection
    db = get_db()
    logger.info(f"Database: {'connected' if db.connected else 'not connected'}")
    
    # Run server
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    finally:
        # Cleanup
        close_db()
        close_clients()
        logger.info("LEAN-Ops MCP Server stopped")


def main():
    """Entry point."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server interrupted")
        sys.exit(0)
    except Exception as e:
        logger.exception("Server error")
        sys.exit(1)


if __name__ == "__main__":
    main()
