# Trade-Mind MCP Server

MCP (Model Context Protocol) server for trading analytics and adaptive learning.

## Overview

Trade-Mind is the **analytics and intelligence layer** of the trading system. It provides tools for AI agents to:

- **Analyze Performance** - Win rates, P&L, drawdowns, trade patterns
- **Detect Market Regimes** - Identify trending, ranging, or volatile conditions
- **Suggest Corrections** - Data-driven parameter adjustments
- **Learn from History** - Store and retrieve trading patterns/insights

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Agent (Claude)                        │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Trade-Mind MCP Server                       │
│  ┌───────────────────┐ ┌──────────────────┐ ┌───────────────┐  │
│  │ ANALYTICS TOOLS   │ │  LEARNING TOOLS  │ │ REGIME TOOLS  │  │
│  │ get_last_trades   │ │ suggest_correct  │ │ detect_regime │  │
│  │ calculate_winrate │ │ record_learning  │ │ get_optimal   │  │
│  │ get_daily_pnl     │ │ analyze_pattern  │ │ compare_perf  │  │
│  └───────────────────┘ └──────────────────┘ └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │    SQL Server    │
                    │    (TradingDB)   │
                    │  ┌────────────┐  │
                    │  │   Trades   │  │
                    │  │   Signals  │  │
                    │  │   Daily    │  │
                    │  │  Regimes   │  │
                    │  │  Learning  │  │
                    │  └────────────┘  │
                    └──────────────────┘
```

## Available Tools

### Analytics Tools
| Tool | Description |
|------|-------------|
| `get_last_trades` | Recent trade history with P&L details |
| `calculate_win_rate` | Win rate, profit factor, avg win/loss |
| `get_daily_pnl` | Daily P&L breakdown and equity curve |
| `analyze_drawdown` | Drawdown analysis with recovery times |
| `get_performance_summary` | Comprehensive performance report |
| `analyze_trade_patterns` | Find patterns in winning/losing trades |

### Learning Tools
| Tool | Description |
|------|-------------|
| `suggest_corrections` | AI-driven parameter adjustment suggestions |
| `get_optimal_params` | Best parameters for current market regime |
| `record_learning` | Store a new pattern or insight |
| `get_learning_history` | Retrieve past learnings and patterns |
| `compare_parameter_performance` | Compare different parameter settings |

### Regime Tools
| Tool | Description |
|------|-------------|
| `detect_market_regime` | Identify current market condition |
| `get_regime_history` | Historical regime changes |
| `get_regime_performance` | Performance breakdown by regime |

## Installation

```bash
cd trade-mind-mcp
pip install -e .
```

## Configuration

Create a `.env` file:

```env
# Database
SQL_SERVER=localhost
SQL_DATABASE=TradingDB
SQL_TRUSTED_CONNECTION=yes

# Analysis Settings
MIN_TRADES_FOR_STATS=5
MIN_CONFIDENCE_THRESHOLD=0.6
LOOKBACK_DAYS_DEFAULT=30

# Learning
LEARNING_ENABLED=true
AUTO_SUGGEST_ENABLED=true
```

## Usage with Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "trade-mind": {
      "command": "python",
      "args": ["-m", "trade_mind_mcp.server"],
      "cwd": "C:/Users/anand/Documents/trading_plan/trade-mind-mcp",
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

## Example Workflows

### Analyze Recent Performance
```
"What's my win rate for TQQQ trades this week? Show me the last 10 trades."
```

### Get Improvement Suggestions
```
"Analyze my recent losing trades and suggest parameter adjustments"
```

### Detect Market Conditions
```
"What's the current market regime? Should I adjust my strategy?"
```

### Learn from Patterns
```
"Record that RSI below 25 with high volume tends to produce better entries"
```

## Data Requirements

For meaningful analytics:
- **Minimum 20 trades** for statistical significance
- **Multiple sessions** to detect patterns
- **Regime data** from at least 5 trading days
- **Parameter variations** from backtest sweeps

## Integration with LEAN-Ops

Trade-Mind complements LEAN-Ops:

| LEAN-Ops | Trade-Mind |
|----------|------------|
| Run backtests | Analyze results |
| Deploy algorithms | Monitor performance |
| Update parameters | Suggest parameters |
| Control execution | Learn from outcomes |

## License

MIT
