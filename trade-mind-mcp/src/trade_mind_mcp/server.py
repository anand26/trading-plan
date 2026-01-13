"""
Trade-Mind MCP Server
=====================
MCP server for trading analytics and adaptive learning.

This server provides tools for AI agents to:
- Analyze trading performance (win rate, P&L, patterns)
- Detect market regimes
- Generate data-driven correction suggestions
- Store and retrieve trading learnings

Usage:
    python -m trade_mind_mcp.server
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
from . import tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("trade-mind-mcp")


# ============================================
# TOOL DEFINITIONS
# ============================================

TOOLS = [
    # Analytics Tools
    Tool(
        name="get_last_trades",
        description="""Get recent trade history with P&L details.
        
Returns the most recent trades with entry/exit prices, P&L,
entry/exit reasons, and holding times. Use this to review
recent trading activity.""",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Filter by symbol (TQQQ, SQQQ)",
                    "enum": ["TQQQ", "SQQQ"]
                },
                "count": {
                    "type": "integer",
                    "description": "Number of trades to return",
                    "default": 20
                },
                "session_id": {
                    "type": "string",
                    "description": "Filter by session ID"
                }
            }
        }
    ),
    Tool(
        name="calculate_win_rate",
        description="""Calculate comprehensive win rate statistics.
        
Returns win rate, profit factor, average win/loss, max win/loss,
and performance grade. Essential for evaluating strategy health.""",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Filter by symbol"
                },
                "session_id": {
                    "type": "string",
                    "description": "Filter by session"
                },
                "days_back": {
                    "type": "integer",
                    "description": "Only include trades from last N days"
                }
            }
        }
    ),
    Tool(
        name="get_daily_pnl",
        description="""Get daily P&L breakdown and statistics.
        
Shows P&L for each trading day, plus summary stats like
best/worst days and day win rate.""",
        inputSchema={
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Number of days to retrieve",
                    "default": 30
                },
                "session_id": {
                    "type": "string",
                    "description": "Filter by session"
                }
            }
        }
    ),
    Tool(
        name="analyze_drawdown",
        description="""Analyze drawdown metrics and recovery patterns.
        
Returns max drawdown, current drawdown, recovery times,
and drawdown events. Critical for risk assessment.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Filter by session"
                },
                "days_back": {
                    "type": "integer",
                    "description": "Analysis period",
                    "default": 30
                }
            }
        }
    ),
    Tool(
        name="get_performance_summary",
        description="""Get comprehensive performance report.
        
All-in-one view: win rate, profit factor, drawdown,
daily metrics, and current regime. Use for status checks.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Filter by session"
                },
                "days_back": {
                    "type": "integer",
                    "description": "Analysis period",
                    "default": 30
                }
            }
        }
    ),
    Tool(
        name="analyze_trade_patterns",
        description="""Find patterns in winning/losing trades.
        
Analyzes trades by entry reason, exit reason, time of day,
and holding time. Reveals what's working and what isn't.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Filter by session"
                },
                "days_back": {
                    "type": "integer",
                    "description": "Analysis period",
                    "default": 30
                },
                "outcome_filter": {
                    "type": "string",
                    "description": "Filter trades",
                    "enum": ["winning", "losing"]
                }
            }
        }
    ),
    
    # Learning Tools
    Tool(
        name="suggest_corrections",
        description="""Generate AI-driven parameter adjustment suggestions.
        
The core learning tool. Analyzes current performance against
optimal parameters and market regime to suggest improvements.
Returns prioritized corrections with data support.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session to analyze"
                },
                "strategy_id": {
                    "type": "string",
                    "description": "Strategy identifier",
                    "default": "TQQQ_SCALPING"
                },
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum confidence for suggestions",
                    "default": 0.6
                }
            }
        }
    ),
    Tool(
        name="get_optimal_params",
        description="""Get best parameters for current/specified market regime.
        
Returns optimal parameter values with confidence scores
and sample sizes. Use for regime-based tuning.""",
        inputSchema={
            "type": "object",
            "properties": {
                "strategy_id": {
                    "type": "string",
                    "description": "Strategy identifier",
                    "default": "TQQQ_SCALPING"
                },
                "market_regime": {
                    "type": "string",
                    "description": "Specific regime",
                    "enum": ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "HIGH_VOLATILITY"]
                }
            }
        }
    ),
    Tool(
        name="record_learning",
        description="""Store a new pattern or insight in the learning store.
        
Record observations about what works in different conditions.
These learnings improve future suggestions.""",
        inputSchema={
            "type": "object",
            "properties": {
                "pattern_type": {
                    "type": "string",
                    "description": "Type of pattern",
                    "enum": ["ENTRY_SIGNAL", "EXIT_SIGNAL", "REGIME_PATTERN", "RISK_PATTERN", "TIME_PATTERN"]
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description"
                },
                "data": {
                    "type": "object",
                    "description": "Structured pattern data"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score 0-1",
                    "default": 0.5
                }
            },
            "required": ["pattern_type", "description", "data"]
        }
    ),
    Tool(
        name="get_learning_history",
        description="""Retrieve past learnings and patterns.
        
Access stored learnings to inform decisions or
review what patterns have been identified.""",
        inputSchema={
            "type": "object",
            "properties": {
                "pattern_type": {
                    "type": "string",
                    "description": "Filter by pattern type"
                },
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum confidence threshold",
                    "default": 0.0
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results",
                    "default": 50
                }
            }
        }
    ),
    Tool(
        name="compare_parameter_performance",
        description="""Compare performance of different parameter values.
        
See how different values of a parameter (e.g., RSI oversold)
have performed historically. Data-driven parameter selection.""",
        inputSchema={
            "type": "object",
            "properties": {
                "param_name": {
                    "type": "string",
                    "description": "Parameter to analyze (e.g., 'rsi_oversold')"
                },
                "market_regime": {
                    "type": "string",
                    "description": "Filter by regime"
                }
            },
            "required": ["param_name"]
        }
    ),
    
    # Regime Tools
    Tool(
        name="detect_market_regime",
        description="""Identify current market condition.
        
Returns regime type (trending, ranging, volatile),
trend direction, and confidence. Critical for
adaptive strategy behavior.""",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol to analyze",
                    "default": "QQQ"
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Analysis period",
                    "default": 20
                }
            }
        }
    ),
    Tool(
        name="get_regime_history",
        description="""Get historical regime changes.
        
Shows how market regime has evolved over time.
Useful for understanding regime duration and transitions.""",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol to analyze",
                    "default": "QQQ"
                },
                "days_back": {
                    "type": "integer",
                    "description": "History period",
                    "default": 30
                }
            }
        }
    ),
    Tool(
        name="get_regime_performance",
        description="""Get performance breakdown by market regime.
        
Shows how strategy performed in each regime type.
Identifies which regimes are profitable vs problematic.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Filter by session"
                },
                "days_back": {
                    "type": "integer",
                    "description": "Analysis period",
                    "default": 30
                }
            }
        }
    ),
    
    # Utility Tools
    Tool(
        name="health_check",
        description="""Check health of Trade-Mind services.
        
Verify database connection and view current configuration.""",
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
        if name == "get_last_trades":
            result = await tools.get_last_trades(**arguments)
        elif name == "calculate_win_rate":
            result = await tools.calculate_win_rate(**arguments)
        elif name == "get_daily_pnl":
            result = await tools.get_daily_pnl(**arguments)
        elif name == "analyze_drawdown":
            result = await tools.analyze_drawdown(**arguments)
        elif name == "get_performance_summary":
            result = await tools.get_performance_summary(**arguments)
        elif name == "analyze_trade_patterns":
            result = await tools.analyze_trade_patterns(**arguments)
        elif name == "suggest_corrections":
            result = await tools.suggest_corrections(**arguments)
        elif name == "get_optimal_params":
            result = await tools.get_optimal_params(**arguments)
        elif name == "record_learning":
            result = await tools.record_learning(**arguments)
        elif name == "get_learning_history":
            result = await tools.get_learning_history(**arguments)
        elif name == "compare_parameter_performance":
            result = await tools.compare_parameter_performance(**arguments)
        elif name == "detect_market_regime":
            result = await tools.detect_market_regime(**arguments)
        elif name == "get_regime_history":
            result = await tools.get_regime_history(**arguments)
        elif name == "get_regime_performance":
            result = await tools.get_regime_performance(**arguments)
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
    logger.info("Starting Trade-Mind MCP Server...")
    
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
        logger.info("Trade-Mind MCP Server stopped")


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
