# TQQQ/SQQQ Backtest Pipeline

## Overview

This directory contains the backtest infrastructure that feeds data into Trade-Mind MCP for adaptive learning.

## Components

| File | Purpose |
|------|---------|
| [backtest_runner.py](backtest_runner.py) | Execute LEAN backtests and store results in SQL |
| [results_processor.py](results_processor.py) | Parse LEAN output and structure for MCP |
| [parameter_optimizer.py](parameter_optimizer.py) | Multi-parameter optimization and sweep |
| [tqqq_backtest_config.json](tqqq_backtest_config.json) | LEAN configuration for backtesting |
| [TRADE_MIND_DATA_CONTRACT.md](TRADE_MIND_DATA_CONTRACT.md) | Data contract for MCP integration |

## Quick Start

### 1. Run a Single Backtest

```powershell
cd c:\Users\anand\Documents\trading_plan\backtest
python backtest_runner.py --start 2024-01-01 --end 2024-12-31
```

### 2. Parameter Sweep

```powershell
# Sweep RSI oversold values
python backtest_runner.py --sweep --sweep-param rsi_oversold --sweep-values "25,28,30,32,35"
```

### 3. Full Optimization

```powershell
# Grid search over multiple parameters
python parameter_optimizer.py --mode grid --start 2024-01-01 --end 2024-12-31

# Regime-specific optimization
python parameter_optimizer.py --mode regime --regime TRENDING_UP
```

## Data Flow to Trade-Mind MCP

```
Backtest Results → SQL Server → Trade-Mind MCP Tools
                                ├── get_last_trades
                                ├── calculate_win_rate
                                ├── get_daily_pnl
                                ├── suggest_corrections
                                └── detect_market_regime
```

## Results Storage

Results are stored in two locations:

1. **SQL Server** (TradingDB) - For Trade-Mind MCP queries
   - `Trades` table
   - `DailyPerformance` table
   - `BacktestOutcomes` table
   - `ParameterPerformance` table

2. **File System** - For debugging and backup
   - `results/<session_id>/config.json`
   - `results/<session_id>/parsed_results.json`
   - `results/<session_id>/trade_mind_data.json`

## Prerequisites

1. **LEAN Engine**: Build the QuantConnect LEAN solution
   ```powershell
   cd quantconnect-lean
   dotnet build QuantConnect.Lean.sln
   ```

2. **SQL Server**: Run the database schema scripts
   ```powershell
   cd database
   sqlcmd -S localhost -E -i 01_create_database.sql
   # ... run all scripts
   ```

3. **Python Dependencies**:
   ```powershell
   pip install pyodbc
   ```

## Configuration

Edit `tqqq_backtest_config.json` to change:
- Date range
- Initial capital
- Data paths
- Logging level

## Output Format

Each backtest produces:
- Session ID: `BT_YYYYMMDD_HHMMSS_<uuid>`
- Statistics: Sharpe, return, drawdown, win rate
- Trades: Entry/exit with reasons
- Daily P&L: Aggregated by day

## Trade-Mind Integration

See [TRADE_MIND_DATA_CONTRACT.md](TRADE_MIND_DATA_CONTRACT.md) for:
- SQL table schemas
- Stored procedure inputs/outputs
- MCP tool data formats
