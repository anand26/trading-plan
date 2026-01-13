# Trade-Mind MCP Data Contract
## Backtest Pipeline → MCP Integration

This document defines how backtest data flows into Trade-Mind MCP, enabling the adaptive learning agent to make data-driven decisions.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKTEST PIPELINE                                   │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │    LEAN      │    │   Results    │    │  SQL Server  │                  │
│  │   Engine     │───►│  Processor   │───►│  (TradingDB) │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│         │                                        │                          │
│         │ JSON Results                          │ Data Available            │
│         │ Transaction Logs                       │                          │
│         │ Algorithm Logs                         ▼                          │
│         │                            ┌──────────────────────┐               │
│         │                            │   Trade-Mind MCP     │               │
│         │                            │                      │               │
│         │                            │  • get_last_trades   │               │
│         │                            │  • calculate_win_rate│               │
│         │                            │  • get_daily_pnl     │               │
│         │                            │  • suggest_corrections│              │
│         │                            │  • detect_regime     │               │
│         │                            └──────────────────────┘               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Contracts

### 1. `get_last_trades` Tool

**Source**: `Trades` table  
**Populated by**: `backtest_runner.py` → `results_processor.py`

```sql
-- Trade-Mind MCP calls sp_GetLastTrades
EXEC sp_GetLastTrades @Symbol = 'TQQQ', @Count = 10, @SessionId = NULL;
```

**Data Contract**:
```python
{
    "TradeId": int,
    "SessionId": str,           # BT_YYYYMMDD_HHMMSS_uuid
    "Symbol": str,              # TQQQ, SQQQ
    "Side": str,                # BUY, SELL
    "Quantity": float,
    "EntryPrice": float,
    "ExitPrice": float,
    "RealizedPnL": float,       # Absolute P&L in USD
    "RealizedPnLPct": float,    # P&L as percentage (0.02 = 2%)
    "EntryTime": datetime,
    "ExitTime": datetime,
    "Duration": int,            # Seconds
    "EntryReason": str,         # RSI_OVERSOLD, VWAP_BOUNCE, etc.
    "ExitReason": str           # TAKE_PROFIT, STOP_LOSS, EOD_CLOSE
}
```

**Use Cases**:
- Review recent trade history
- Analyze entry/exit patterns
- Calculate trade duration statistics

---

### 2. `calculate_win_rate` Tool

**Source**: `Trades` table (aggregated)  
**Populated by**: `backtest_runner.py` → `results_processor.py`

```sql
-- Trade-Mind MCP calls sp_CalculateWinRate
EXEC sp_CalculateWinRate 
    @Symbol = 'TQQQ', 
    @StartDate = '2024-01-01',
    @MinTrades = 10;
```

**Data Contract**:
```python
{
    "Symbol": str,
    "TotalTrades": int,
    "WinningTrades": int,
    "LosingTrades": int,
    "BreakEvenTrades": int,
    "WinRate": float,           # 0.65 = 65%
    "TotalPnL": float,
    "AvgPnL": float,
    "AvgWin": float,
    "AvgLoss": float,           # Negative value
    "ProfitFactor": float,      # |AvgWin| / |AvgLoss|
    "MaxWin": float,
    "MaxLoss": float,
    "AvgDuration": int,         # Seconds
    "DataQuality": str          # STATISTICALLY_VALID or INSUFFICIENT_DATA
}
```

**Use Cases**:
- Evaluate strategy performance
- Compare symbol profitability
- Set realistic expectations for risk management

---

### 3. `get_daily_pnl` Tool

**Source**: `DailyPerformance` table  
**Populated by**: `results_processor.py` → `_calculate_daily_stats()`

```sql
-- Trade-Mind MCP calls sp_GetDailyPnL
EXEC sp_GetDailyPnL @DaysBack = 30, @SessionId = NULL;
```

**Data Contract**:
```python
{
    "TradingDate": date,
    "SessionId": str,
    "OpeningBalance": float,
    "ClosingBalance": float,
    "RealizedPnL": float,
    "UnrealizedPnL": float,
    "TotalPnL": float,
    "TotalPnLPct": float,       # Daily return percentage
    "TradeCount": int,
    "WinCount": int,
    "LossCount": int,
    "DayWinRate": float,
    "VolumeTraded": float,
    "Commission": float,
    "MaxDrawdownDay": float     # Intraday max drawdown
}
```

**Use Cases**:
- Track daily performance trends
- Identify profitable/unprofitable days of week
- Detect performance degradation

---

### 4. `suggest_corrections` Tool

**Source**: `ParameterPerformance`, `OptimalParameters`, `MarketRegimes` tables  
**Populated by**: `parameter_optimizer.py`

```sql
-- Trade-Mind MCP calls sp_SuggestCorrections
EXEC sp_SuggestCorrections @MinConfidence = 0.6, @MinSampleSize = 20;
```

**Data Contract**:
```python
{
    "ParamName": str,           # rsi_oversold, stop_loss_pct, etc.
    "CurrentValue": str,
    "SuggestedValue": str,
    "ConfidenceScore": float,   # 0.0 to 1.0
    "SampleSize": int,          # Number of backtests supporting this
    "CurrentMarketRegime": str, # TRENDING_UP, RANGING, etc.
    "OptimalForRegime": str,
    "AvgPnLWhenUsed": float,
    "WinRateWhenUsed": float,
    "RecommendationStrength": str  # HIGH_CONFIDENCE, MEDIUM_CONFIDENCE, LOW_CONFIDENCE
}
```

**Use Cases**:
- Adaptive parameter adjustments
- Regime-specific tuning
- Continuous improvement loop

---

### 5. `detect_market_regime` Tool

**Source**: `MarketRegimes` table  
**Populated by**: Algorithm runtime + analysis scripts

```sql
-- Trade-Mind MCP calls sp_DetectMarketRegime
EXEC sp_DetectMarketRegime @Symbol = 'QQQ';
```

**Data Contract**:
```python
{
    "RegimeType": str,          # TRENDING_UP, TRENDING_DOWN, RANGING, HIGH_VOLATILITY
    "Confidence": float,        # 0.0 to 1.0
    "VixLevel": float,          # Current VIX value
    "TrendDirection": str,      # UP, DOWN, NEUTRAL
    "Volatility": float,        # ATR-based volatility measure
    "StartTime": datetime,
    "EndTime": datetime,        # NULL if current
    "DurationHours": int
}
```

**Use Cases**:
- Adjust strategy for current market conditions
- Select regime-specific parameters
- Risk management decisions

---

## Backtest Session Tracking

Every backtest run creates a session record for traceability:

**Table**: `Sessions`

```python
{
    "SessionId": str,           # BT_20240115_143022_abc12345
    "SessionType": str,         # BACKTEST, PAPER, LIVE
    "StrategyId": str,          # TQQQ_SCALPING
    "StartTime": datetime,
    "EndTime": datetime,
    "ParametersJson": str,      # Full parameter snapshot
    "Status": str,              # RUNNING, COMPLETED, FAILED
    "TotalReturn": float,
    "SharpeRatio": float,
    "MaxDrawdown": float,
    "TotalTrades": int,
    "WinRate": float
}
```

---

## Parameter Performance Tracking

Each parameter value tested is recorded:

**Table**: `ParameterPerformance`

```python
{
    "ParamName": str,           # rsi_oversold
    "ParamValue": str,          # 28
    "MarketRegime": str,        # ALL, TRENDING_UP, etc.
    "TradeCount": int,          # Total trades with this value
    "WinRate": float,
    "AvgPnLWhenUsed": float,
    "SharpeRatio": float,
    "MaxDrawdown": float,
    "AvgHoldingTime": int,      # Seconds
    "LastUpdated": datetime
}
```

**Populated by**: `parameter_optimizer.py` → `_store_param_performance()`

---

## Optimal Parameters Per Regime

Best parameters discovered for each market regime:

**Table**: `OptimalParameters`

```python
{
    "StrategyId": str,          # TQQQ_SCALPING
    "ParamName": str,           # rsi_oversold
    "MarketRegime": str,        # TRENDING_UP
    "OptimalValue": str,        # 28
    "ConfidenceScore": float,   # 0.85
    "SampleSize": int,          # 50 backtests
    "ExpectedSharpe": float,
    "ExpectedReturn": float,
    "ExpectedDrawdown": float,
    "LastCalculated": datetime
}
```

**Populated by**: `parameter_optimizer.py` → `_store_optimal_params()`

---

## Usage Examples

### Example 1: Run Backtest and Store for MCP

```python
from backtest_runner import BacktestRunner

runner = BacktestRunner()
result = runner.run_backtest(
    start_date="2024-01-01",
    end_date="2024-06-30",
    rsi_oversold=28
)

# Data now available via Trade-Mind MCP:
# - sp_GetLastTrades returns trades from this backtest
# - sp_CalculateWinRate includes this session's trades
# - sp_GetDailyPnL shows daily performance
```

### Example 2: Optimize Parameters and Enable Suggestions

```python
from parameter_optimizer import ParameterOptimizer, ParameterRange

optimizer = ParameterOptimizer()

# Sweep RSI oversold values
optimizer.single_param_sweep(
    ParameterRange(name="rsi_oversold", values=[25, 28, 30, 32, 35]),
    start_date="2024-01-01",
    end_date="2024-12-31",
    market_regime="TRENDING_UP"
)

# Data now available via Trade-Mind MCP:
# - sp_SuggestCorrections returns optimal RSI values
# - ParameterPerformance shows which values work best
```

### Example 3: Query via Trade-Mind MCP

```python
# This is what Trade-Mind MCP does internally:

# Tool: get_last_trades
cursor.execute("EXEC sp_GetLastTrades @Symbol = 'TQQQ', @Count = 10")
trades = cursor.fetchall()

# Tool: calculate_win_rate  
cursor.execute("EXEC sp_CalculateWinRate @Symbol = 'TQQQ'")
stats = cursor.fetchone()

# Tool: suggest_corrections
cursor.execute("EXEC sp_SuggestCorrections @MinConfidence = 0.7")
suggestions = cursor.fetchall()
```

---

## Integration Points Summary

| MCP Tool | SQL Stored Procedure | Source Module |
|----------|---------------------|---------------|
| `get_last_trades` | `sp_GetLastTrades` | `results_processor.py` |
| `calculate_win_rate` | `sp_CalculateWinRate` | `results_processor.py` |
| `get_daily_pnl` | `sp_GetDailyPnL` | `results_processor.py` |
| `suggest_corrections` | `sp_SuggestCorrections` | `parameter_optimizer.py` |
| `detect_market_regime` | `sp_DetectMarketRegime` | Algorithm + analysis |

---

## Data Quality Requirements

For Trade-Mind MCP suggestions to be meaningful:

1. **Minimum Sample Size**: 20+ trades per parameter combination
2. **Regime Coverage**: Test across multiple market conditions
3. **Statistical Validity**: Win rate calculations require 5+ trades minimum
4. **Recency**: Optimal parameters should be recalculated monthly

---

## Next Steps

With this data contract established:

1. **#4 SQL Connector**: Add SQL persistence to TQQQScalpingAlgorithm.py
2. **#5 LEAN-Ops MCP**: Build backtest execution MCP server
3. **#6 Trade-Mind MCP**: Build analytics MCP server using these contracts
