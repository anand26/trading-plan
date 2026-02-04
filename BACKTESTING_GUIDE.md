# TQQQ/SQQQ Backtesting Guide

## Overview

This guide explains how to backtest your TQQQ/SQQQ scalping strategy using the QuantConnect LEAN engine, integrated with your MCP servers for analysis.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         YOUR WORKFLOW                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   1. ASK COPILOT      2. LEAN ENGINE         3. ANALYZE RESULTS     │
│   ┌─────────────┐     ┌─────────────┐        ┌─────────────────┐    │
│   │ "Run a      │────▶│   Docker    │───────▶│  Trade-Mind     │    │
│   │  backtest"  │     │   LEAN      │        │  MCP queries    │    │
│   └─────────────┘     └─────────────┘        └─────────────────┘    │
│         │                   │                        │               │
│         ▼                   ▼                        ▼               │
│   lean-ops MCP        Trades → SQL            Win rate, P&L,        │
│   (orchestrates)      (stored)                regime analysis       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites Checklist

| Requirement | Status | How to Verify |
|-------------|--------|---------------|
| **SQL Server** | Required | `sqlcmd -S localhost -E -Q "SELECT 1"` |
| **TradingDB** | Required | `sqlcmd -S localhost -E -d TradingDB -Q "SELECT 1"` |
| **Python venv** | Required | `.\.venv\Scripts\Activate.ps1` |
| **MCP Servers** | Required | Check VS Code MCP panel |
| **Docker Desktop** | Required for LEAN | Start Docker Desktop app |
| **Historical Data** | Required | See "Getting Data" section |

---

## Method 1: Use Copilot Chat (Recommended)

Once MCP servers are running, just ask in this chat:

### Running Backtests
```
"Run a backtest for TQQQ from 2024-01-01 to 2024-06-30"

"Run a backtest with RSI oversold at 25"

"Compare backtests with different stop loss values: 1%, 2%, 3%"
```

### Analyzing Results
```
"What's my win rate for the last backtest?"

"Show daily P&L breakdown"

"Detect the market regime"

"Suggest parameter corrections"

"Get optimal parameters for trending up market"
```

---

## Method 2: Command Line

### Step 1: Activate Environment
```powershell
cd C:\Users\anand\Documents\trading_plan
.\.venv\Scripts\Activate.ps1
```

### Step 2: Run Single Backtest
```powershell
cd backtest
python backtest_runner.py --start 2024-01-01 --end 2024-06-30
```

### Step 3: Parameter Sweep
```powershell
# Sweep RSI oversold values
python backtest_runner.py --sweep --sweep-param rsi_oversold --sweep-values "25,28,30,32,35"

# Sweep stop loss percentages
python backtest_runner.py --sweep --sweep-param stop_loss_pct --sweep-values "0.01,0.015,0.02,0.025,0.03"
```

### Step 4: Full Grid Optimization
```powershell
python parameter_optimizer.py --mode grid --start 2024-01-01 --end 2024-12-31
```

---

## Method 3: Docker (Direct LEAN Engine)

### Step 1: Start Docker Desktop
```powershell
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
# Wait for Docker to be ready
docker info
```

### Step 2: Pull LEAN Image (First Time Only)
```powershell
docker pull quantconnect/lean:latest
```

### Step 3: Run Backtest in Docker
```powershell
cd C:\Users\anand\Documents\trading_plan\quantconnect-lean

# Run with your algorithm
docker run --rm `
  -v "${PWD}:/Lean/Launcher/bin/Debug" `
  -v "C:/Users/anand/Documents/trading_plan/algorithms:/Lean/Algorithm.Python" `
  -v "C:/Users/anand/Documents/trading_plan/backtest/results:/Results" `
  quantconnect/lean:latest `
  --config /Lean/Launcher/bin/Debug/config.json
```

---

## Getting Historical Data

### Option A: Sample Data (Quick Start)
```powershell
cd C:\Users\anand\Documents\trading_plan\quantconnect-lean

# Download sample equity data
Invoke-WebRequest -Uri "https://cdn.quantconnect.com/data/equity/usa/minute/tqqq.zip" -OutFile "Data/equity/usa/minute/tqqq.zip"
Expand-Archive -Path "Data/equity/usa/minute/tqqq.zip" -DestinationPath "Data/equity/usa/minute/tqqq"
```

### Option B: QuantConnect Data Library
1. Create account at https://www.quantconnect.com
2. Subscribe to data or use free tier
3. Download via their CLI tool

### Option C: Alpaca Historical Data
```python
# Use Alpaca API to fetch historical data
import alpaca_trade_api as tradeapi

api = tradeapi.REST('YOUR_KEY', 'YOUR_SECRET', 'https://paper-api.alpaca.markets')
bars = api.get_bars('TQQQ', '1Min', start='2024-01-01', end='2024-06-30').df
```

---

## Strategy Parameters Reference

| Parameter | Default | Description | Good Range |
|-----------|---------|-------------|------------|
| `rsi_period` | 14 | RSI calculation period | 10-20 |
| `rsi_oversold` | 30 | Buy signal threshold | 25-35 |
| `rsi_overbought` | 70 | Sell signal threshold | 65-75 |
| `bb_period` | 20 | Bollinger Bands period | 15-25 |
| `bb_std_dev` | 2.0 | BB standard deviation | 1.5-2.5 |
| `stop_loss_pct` | 0.02 | Stop loss percentage | 0.01-0.03 |

---

## Understanding Results

### Session ID Format
```
BT_20260113_143052_a1b2c3d4
│  │        │       │
│  │        │       └── Unique identifier
│  │        └────────── Time (HHMMSS)
│  └─────────────────── Date (YYYYMMDD)
└────────────────────── BT = Backtest, PT = Paper Trading
```

### Results Location
```
backtest/results/<session_id>/
├── config.json              # Parameters used
├── transactions.csv         # All trades
├── parsed_results.json      # Performance metrics
├── trade_mind_data.json     # MCP-ready data
└── webhook_log.txt          # Simulated webhooks
```

### Key Metrics to Watch
| Metric | Good | Great | Excellent |
|--------|------|-------|-----------|
| Win Rate | >50% | >55% | >60% |
| Profit Factor | >1.2 | >1.5 | >2.0 |
| Max Drawdown | <15% | <10% | <7% |
| Sharpe Ratio | >0.5 | >1.0 | >1.5 |

---

## Typical Workflow

### Week 1-2: Initial Testing
1. Run baseline backtest with default parameters
2. Analyze win rate and drawdown
3. Identify problem areas (time of day, market regime)

### Week 3-4: Optimization
1. Parameter sweeps on individual parameters
2. Regime-specific optimization
3. Compare results via Trade-Mind MCP

### Ongoing: Adaptive Learning
1. Run backtests regularly with new data
2. Use `suggest_corrections` tool for improvements
3. Track patterns in `Learning Store`

---

## Quick Commands Reference

### In Copilot Chat
| Task | Command |
|------|---------|
| Run backtest | "Run a backtest from 2024-01-01 to 2024-06-30" |
| Get performance | "Show my trading performance" |
| Get win rate | "What's my win rate?" |
| Market regime | "Detect current market regime" |
| Get suggestions | "Suggest parameter corrections" |
| Compare backtests | "Compare backtests session1 and session2" |

### In Terminal
| Task | Command |
|------|---------|
| Activate venv | `.\.venv\Scripts\Activate.ps1` |
| Run backtest | `python backtest/backtest_runner.py --start 2024-01-01 --end 2024-06-30` |
| Parameter sweep | `python backtest/backtest_runner.py --sweep --sweep-param rsi_oversold --sweep-values "25,30,35"` |
| Grid optimization | `python backtest/parameter_optimizer.py --mode grid` |

---

## Troubleshooting

### MCP Server Not Responding
```powershell
# Test manually
C:/Users/anand/Documents/trading_plan/.venv/Scripts/python.exe -m lean_ops_mcp
```

### No Data Available
```powershell
# Check Data folder
ls C:\Users\anand\Documents\trading_plan\quantconnect-lean\Data\equity\usa\minute\
```

### Docker Not Running
```powershell
docker info
# If error, start Docker Desktop
```

### SQL Connection Failed
```powershell
sqlcmd -S localhost -E -d TradingDB -Q "SELECT COUNT(*) FROM Trades"
```

---

## Next Steps

1. **Verify Setup**: Run `python -m lean_ops_mcp` manually
2. **Get Data**: Download TQQQ/SQQQ historical data
3. **First Backtest**: Try a simple 3-month backtest
4. **Analyze**: Use Trade-Mind MCP to review results
5. **Optimize**: Run parameter sweeps
6. **Iterate**: Refine based on suggestions

---

## MCP Tools Available

### LEAN-Ops MCP (Algorithm Operations)
- `run_backtest` - Execute backtest with LEAN engine
- `get_backtest_results` - Retrieve statistics
- `compare_backtests` - Compare multiple runs
- `deploy_paper` - Deploy to paper trading
- `get_algorithm_status` - Check running algorithm
- `update_parameters` - Hot-reload parameters

### Trade-Mind MCP (Analytics & Learning)
- `get_last_trades` - Recent trade history
- `calculate_win_rate` - Win rate statistics
- `get_daily_pnl` - Daily P&L breakdown
- `detect_market_regime` - Current market condition
- `suggest_corrections` - AI-driven suggestions
- `get_optimal_params` - Best params for regime

---

*Last Updated: January 13, 2026*
