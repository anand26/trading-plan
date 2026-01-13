# TQQQ/SQQQ Trading System - Database Setup

## Overview

This directory contains the SQL Server schema for the TQQQ/SQQQ Scalping Trading System. The database serves as the central persistence hub for:

- **Trade Operations**: Orders, trades, positions, signals
- **Performance Tracking**: Daily P&L, account snapshots, win rates
- **Adaptive Learning**: Backtest outcomes, parameter performance, market regimes
- **Configuration**: Hot-reloadable strategy parameters

## Prerequisites

- **SQL Server 2019+** or **Azure SQL Database**
- **SQL Server Management Studio (SSMS)** or **sqlcmd**
- Windows Authentication or SQL Authentication

## Installation

### Option 1: Using SSMS

1. Open SSMS and connect to your SQL Server instance
2. Execute scripts in order:
   - `01_create_database.sql`
   - `02_core_schema.sql`
   - `03_learning_schema.sql`
   - `04_config_schema.sql`
   - `05_stored_procedures.sql`
   - `06_views_indexes.sql`

### Option 2: Using sqlcmd (Command Line)

```powershell
# Navigate to database directory
cd c:\Users\anand\Documents\trading_plan\database

# Execute scripts in order (Windows Authentication)
sqlcmd -S localhost -E -i 01_create_database.sql
sqlcmd -S localhost -E -d TradingDB -i 02_core_schema.sql
sqlcmd -S localhost -E -d TradingDB -i 03_learning_schema.sql
sqlcmd -S localhost -E -d TradingDB -i 04_config_schema.sql
sqlcmd -S localhost -E -d TradingDB -i 05_stored_procedures.sql
sqlcmd -S localhost -E -d TradingDB -i 06_views_indexes.sql

# Or with SQL Authentication
sqlcmd -S localhost -U your_user -P your_password -i 01_create_database.sql
```

### Option 3: All-in-One Script

```powershell
# Run all scripts in sequence
Get-ChildItem -Filter "*.sql" | Sort-Object Name | ForEach-Object {
    Write-Host "Executing: $($_.Name)"
    sqlcmd -S localhost -E -d TradingDB -i $_.FullName
}
```

## Schema Overview

### Database Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TradingDB                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     CORE TABLES (02_core_schema.sql)                 │   │
│  │                                                                      │   │
│  │   Orders ────► Trades ◄──── PositionEntries                         │   │
│  │      │            │                                                  │   │
│  │      │            ▼                                                  │   │
│  │      └────► DailyPerformance ◄──── AccountSnapshots                 │   │
│  │                   │                                                  │   │
│  │   Signals ◄──────┘                                                  │   │
│  │   Bars                                                              │   │
│  │   AuditLog                                                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                  LEARNING TABLES (03_learning_schema.sql)           │   │
│  │                                                                      │   │
│  │   BacktestOutcomes ────► ParameterPerformance                       │   │
│  │          │                        │                                  │   │
│  │          ▼                        ▼                                  │   │
│  │   MarketRegimes ◄──── CorrectionHistory ────► OptimalParameters     │   │
│  │          │                                                          │   │
│  │          ▼                                                          │   │
│  │   LearningPatterns                                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                  CONFIG TABLES (04_config_schema.sql)               │   │
│  │                                                                      │   │
│  │   StrategyParameters ◄──── ParameterHistory                         │   │
│  │   Sessions                                                          │   │
│  │   SystemConfig                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Table Reference

### Core Tables

| Table | Purpose |
|-------|---------|
| `Orders` | All order submissions (pending, filled, cancelled) |
| `Trades` | Completed round-trip trades with P&L |
| `PositionEntries` | Individual entries for pyramiding positions |
| `DailyPerformance` | Daily aggregated metrics |
| `AccountSnapshots` | Point-in-time account state |
| `Signals` | Generated signals (acted on or not) |
| `Bars` | Optional 5-min OHLCV storage |
| `AuditLog` | System events and changes |

### Learning Tables

| Table | Purpose |
|-------|---------|
| `BacktestOutcomes` | Backtest run results |
| `ParameterPerformance` | How parameters perform in different conditions |
| `MarketRegimes` | Detected market regime periods |
| `CorrectionHistory` | All adaptive corrections made |
| `LearningPatterns` | Identified patterns from data |
| `OptimalParameters` | Best parameters per regime |

### Configuration Tables

| Table | Purpose |
|-------|---------|
| `StrategyParameters` | Hot-reloadable strategy parameters |
| `ParameterHistory` | Track all parameter changes |
| `Sessions` | Backtest/paper/live sessions |
| `SystemConfig` | Global system configuration |

## Stored Procedures (MCP Server Interface)

### Trade-Mind MCP Tools

```sql
-- Get last N trades
EXEC sp_GetLastTrades @Symbol = 'TQQQ', @Count = 10;

-- Calculate win rate with filters
EXEC sp_CalculateWinRate 
    @Symbol = 'TQQQ', 
    @StartDate = '2024-01-01',
    @MinTrades = 10;

-- Get daily P&L
EXEC sp_GetDailyPnL @DaysBack = 30;

-- Detect current market regime
EXEC sp_DetectMarketRegime @Symbol = 'QQQ';

-- Get suggested corrections
EXEC sp_SuggestCorrections @MinConfidence = 0.7;
```

### Algorithm Operations

```sql
-- Get all strategy parameters (for algorithm init)
EXEC sp_GetAllParameters @StrategyId = 'TQQQ_SCALPING';

-- Update a parameter
EXEC sp_UpdateParameter 
    @ParamName = 'rsi_oversold', 
    @NewValue = '28',
    @ChangedBy = 'AGENT',
    @ChangeReason = 'Adaptive correction based on recent performance';

-- Record a trade
EXEC sp_RecordTrade 
    @SessionId = 'PAPER_20240115',
    @Symbol = 'TQQQ',
    @Side = 'BUY',
    @Quantity = 100,
    @EntryPrice = 45.50,
    @ExitPrice = 46.20,
    @EntryTime = '2024-01-15 10:30:00',
    @ExitTime = '2024-01-15 11:45:00';
```

## Views

| View | Purpose |
|------|---------|
| `v_RecentTrades` | Recent trades with calculated metrics |
| `v_DailyStats` | Daily performance statistics |
| `v_SymbolPerformance` | Performance aggregated by symbol |
| `v_SignalAnalysis` | Signal generation statistics |
| `v_SignalOutcomes` | Links signals to trade outcomes |
| `v_ParameterEffectiveness` | Parameter performance analysis |
| `v_MarketRegimeSummary` | Market regime history |
| `v_BacktestComparison` | Compare backtest results |
| `v_CorrectionHistory` | Adaptive correction outcomes |
| `v_ActiveSession` | Current running session |

## Default Parameters

The schema includes default parameters for the TQQQ scalping strategy:

| Category | Parameter | Default |
|----------|-----------|---------|
| RSI | `rsi_period` | 14 |
| RSI | `rsi_oversold` | 30 |
| RSI | `rsi_overbought` | 70 |
| BB | `bb_period` | 20 |
| BB | `bb_std_dev` | 2.0 |
| EMA | `ema_fast_period` | 9 |
| EMA | `ema_slow_period` | 21 |
| RISK | `stop_loss_pct` | 2% |
| RISK | `max_daily_trades` | 10 |
| POSITION | `position_size_level1` | 50% |
| POSITION | `position_size_level2` | 30% |
| POSITION | `position_size_level3` | 20% |

## Connection Strings

### Python (pyodbc)
```python
import pyodbc

# Windows Authentication
conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=TradingDB;Trusted_Connection=yes;"

# SQL Authentication
conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=TradingDB;UID=your_user;PWD=your_password;"

conn = pyodbc.connect(conn_str)
```

### .NET (C#)
```csharp
// Windows Authentication
var connStr = "Server=localhost;Database=TradingDB;Integrated Security=true;";

// SQL Authentication
var connStr = "Server=localhost;Database=TradingDB;User Id=your_user;Password=your_password;";
```

## Maintenance

### Backup
```sql
BACKUP DATABASE TradingDB 
TO DISK = 'C:\Backups\TradingDB.bak'
WITH FORMAT, COMPRESSION;
```

### Archive Old Data
```sql
-- Archive trades older than 1 year
INSERT INTO TradesArchive
SELECT * FROM Trades 
WHERE ExitTime < DATEADD(YEAR, -1, GETUTCDATE());

DELETE FROM Trades 
WHERE ExitTime < DATEADD(YEAR, -1, GETUTCDATE());
```

### Index Maintenance
```sql
-- Rebuild fragmented indexes
ALTER INDEX ALL ON Trades REBUILD;
ALTER INDEX ALL ON Signals REBUILD;
```

## Troubleshooting

### Common Issues

1. **Connection refused**: Ensure SQL Server service is running
2. **Login failed**: Check authentication mode (Windows vs SQL)
3. **Database doesn't exist**: Run `01_create_database.sql` first
4. **Permission denied**: Run SSMS as administrator

### Verify Installation
```sql
-- Check all tables exist
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_TYPE = 'BASE TABLE' 
ORDER BY TABLE_NAME;

-- Check stored procedures
SELECT name FROM sys.procedures ORDER BY name;

-- Check views
SELECT name FROM sys.views ORDER BY name;
```

## Next Steps

After database setup:
1. **#3 Backtest Pipeline**: Configure LEAN for backtesting
2. **#4 SQL Connector**: Add persistence to TQQQScalpingAlgorithm.py
3. **#5 LEAN-Ops MCP**: Build the operations MCP server
4. **#6 Trade-Mind MCP**: Build the analytics MCP server
