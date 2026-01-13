# LEAN-Ops MCP Server

MCP (Model Context Protocol) server for QuantConnect LEAN algorithm operations.

## Overview

This server provides tools for AI agents (Claude, etc.) to manage trading algorithm lifecycle:

- **Backtest Execution** - Run and retrieve backtest results
- **Paper Trading** - Deploy algorithms to Alpaca paper trading
- **Live Trading** - Deploy to live (with safety confirmations)
- **Algorithm Control** - Start, stop, update parameters
- **Position Management** - Monitor and liquidate positions

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Agent (Claude)                        │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LEAN-Ops MCP Server                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ run_backtest │ │ deploy_paper │ │ get_algorithm_status │    │
│  │ get_results  │ │ deploy_live  │ │ update_parameters    │    │
│  │ compare      │ │ stop_algo    │ │ liquidate_positions  │    │
│  └──────────────┘ └──────────────┘ └──────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  LEAN Engine │  │  SQL Server  │  │    Alpaca    │
    │  (Backtest)  │  │  (TradingDB) │  │  (Brokerage) │
    └──────────────┘  └──────────────┘  └──────────────┘
```

## Available Tools

| Tool | Description |
|------|-------------|
| `run_backtest` | Execute backtest with LEAN engine |
| `get_backtest_results` | Retrieve statistics from completed backtest |
| `list_backtests` | List all available backtest sessions |
| `compare_backtests` | Compare multiple backtest outcomes |
| `deploy_paper` | Deploy algorithm to Alpaca paper trading |
| `deploy_live` | Deploy to Alpaca live (requires confirmation) |
| `stop_algorithm` | Stop running algorithm (paper or live) |
| `get_algorithm_status` | Get current state, positions, P&L |
| `update_parameters` | Update strategy parameters (hot reload) |
| `liquidate_positions` | Emergency position liquidation |

## Installation

```bash
cd lean-ops-mcp
pip install -e .
```

## Configuration

Create a `.env` file:

```env
# Database
SQL_SERVER=localhost
SQL_DATABASE=TradingDB
SQL_TRUSTED_CONNECTION=yes

# LEAN Engine
LEAN_PATH=../quantconnect-lean
LEAN_DATA_PATH=../quantconnect-lean/Data
LEAN_RESULTS_PATH=./results

# Alpaca (Paper)
ALPACA_PAPER_KEY=your_paper_key
ALPACA_PAPER_SECRET=your_paper_secret
ALPACA_PAPER_URL=https://paper-api.alpaca.markets

# Alpaca (Live) - Keep secure!
ALPACA_LIVE_KEY=your_live_key
ALPACA_LIVE_SECRET=your_live_secret
ALPACA_LIVE_URL=https://api.alpaca.markets

# Safety
LIVE_DEPLOY_ENABLED=false
LIVE_CONFIRM_CODE=DEPLOY_LIVE_2026
```

## Usage with Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lean-ops": {
      "command": "python",
      "args": ["-m", "lean_ops_mcp.server"],
      "cwd": "C:/Users/anand/Documents/trading_plan/lean-ops-mcp",
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

## Example Workflows

### Run a Backtest
```
"Run a backtest for TQQQ from 2024-01-01 to 2024-12-31 with RSI oversold at 25"
```

### Compare Strategies
```
"Compare the last 3 backtests and show me which parameters performed best"
```

### Deploy to Paper Trading
```
"Deploy the best performing configuration to paper trading"
```

### Emergency Stop
```
"Stop the algorithm immediately and liquidate all positions"
```

## Safety Features

1. **Live Trading Disabled by Default** - Must set `LIVE_DEPLOY_ENABLED=true`
2. **Confirmation Code Required** - Live deployments require a confirmation code
3. **Position Limits Enforced** - Maximum position sizes checked
4. **Audit Logging** - All operations logged to SQL
5. **Graceful Shutdown** - Proper position closing on stop

## License

MIT
