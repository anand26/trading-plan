# Copilot Project Context
> **Last Updated:** 2026-01-15 (v3 - Webhook filtering, improved progress bar)
> **Purpose:** Quick reference for AI assistant to understand project structure and state

---

## 🎯 Project Overview

**TQQQ/SQQQ Trading System** - An algorithmic trading system with:
- QuantConnect LEAN backtesting engine
- Streamlit dashboard for monitoring
- SQL Server database for persistence
- MCP (Model Context Protocol) servers for AI integration

---

## 📁 Key Directory Structure

```
trading_plan/
├── algorithms/                    # SOURCE algorithm files (edit here!)
│   ├── TQQQScalpingAlgorithm.py  # Main algorithm (RSI + BB + VWAP)
│   └── sql_connector.py          # Database connector for algorithm
├── backtest/                      # Backtest infrastructure
│   ├── backtest_runner.py        # CLI to run LEAN backtests (AUTO-SYNCS files!)
│   ├── webhook_simulator.py      # Simulates TradingView webhooks
│   └── results/                  # Backtest output (BT_* folders)
├── dashboard/src/dashboard/       # Streamlit UI
│   ├── app.py                    # Main Streamlit app
│   ├── database.py               # DB queries for dashboard
│   └── views/
│       ├── backtest_runner.py    # Backtest Runner page (4 tabs)
│       ├── overview.py           # Overview page
│       ├── trades.py             # Trades page
│       └── regimes.py            # Market regimes page
├── database/                      # SQL schema files (01-12)
├── quantconnect-lean/            # LEAN engine (submodule)
│   └── Algorithm.Python/         # WHERE LEAN RUNS FROM (auto-synced)
├── sync_algorithm.ps1            # Manual sync script (optional)
├── lean-ops-mcp/                 # MCP server for LEAN operations
├── trade-mind-mcp/               # MCP server for trade analytics
└── Data/                         # Market data files
```

---

## 🔧 Key Files & Their Purposes

### Algorithm Layer (IMPORTANT: Edit in algorithms/, auto-syncs to LEAN)
| File | Purpose |
|------|---------|
| `algorithms/TQQQScalpingAlgorithm.py` | **EDIT HERE** - Main trading algorithm source |
| `algorithms/sql_connector.py` | **EDIT HERE** - SQL connector source |
| `backtest/webhook_simulator.py` | **EDIT HERE** - Webhook simulator source |
| `quantconnect-lean/Algorithm.Python/*.py` | Auto-synced copies (LEAN runs these) |

### Backtest Layer
| File | Purpose |
|------|---------|
| `backtest/backtest_runner.py` | CLI to run LEAN backtests. **Auto-syncs algorithm files on init!** |
| `backtest/webhook_simulator.py` | WebhookSimulator class - logs simulated webhooks |
| `backtest/tqqq_backtest_config.json` | Default backtest parameters |

### Dashboard Layer
| File | Purpose |
|------|---------|
| `dashboard/src/dashboard/app.py` | Main Streamlit entry point |
| `dashboard/src/dashboard/views/backtest_runner.py` | Backtest Runner UI (4 tabs: Parameters, Run, Webhooks, History) |
| `dashboard/src/dashboard/database.py` | All database queries |

---

## 🔄 Data Flow

```
1. User clicks "Run Backtest" in dashboard
   └── dashboard/views/backtest_runner.py
       └── Calls: python backtest/backtest_runner.py --session-id BT_xxx
           └── AUTO-SYNCS algorithm files to quantconnect-lean/Algorithm.Python/
           └── Creates LEAN config with webhook-log-path parameter
           └── Runs LEAN engine (QuantConnect.Lean.Launcher.exe)
               └── Algorithm initializes WebhookSimulator
               └── Algorithm logs trades to SQL + webhook_log.txt
           └── Parses results, stores in SQL

2. Dashboard monitors progress (uses threading for non-blocking output)
   └── Reads subprocess output via queue
   └── Reads webhook_log.txt for live webhook events
   └── Updates progress bar based on log patterns
```

---

## ✅ Recently Fixed Issues (2026-01-23)

| Issue | Fix Applied |
|-------|-------------|
| Risk Management inputs were free-form | Replaced with discrete percentage selectboxes (1%, 1.25%, 1.5%, 2%, 2.5%, 3%) |
| Webhook display showed SCHEDULED events | Filter to show only SIGNAL events (BUY/SELL/TAKE_PROFIT/STOP_LOSS) |
| Progress bar stuck at "Initializing..." | Added LEAN-specific output patterns for progress detection |
| LEAN ran old algorithm | Added auto-sync in `backtest_runner.py` |
| `datetime.time` error | Import `time as dt_time` from datetime module |
| Webhook log not created | Fixed param name: `webhook-log-path` (hyphens) |
| Progress bar stuck | Changed to threaded queue-based output reading |
| Presets not working | Fixed to update `backtest_params` in session_state |
| Import path issues | Removed relative imports, files copied to same folder |

---

## 🔑 Key Parameters

### Strategy Parameters (TQQQScalpingAlgorithm)
```python
rsi_period = 14
rsi_oversold = 45.0      # Relaxed for testing (normally 30)
rsi_overbought = 55.0    # Relaxed for testing (normally 70)
bb_period = 20
bb_std_dev = 2.0
stop_loss_pct = 0.02     # 2%
position_size_level1 = 0.50
position_size_level2 = 0.30
position_size_level3 = 0.20
```

### Backtest Defaults
```python
start_date = "2026-01-02"
end_date = "2026-01-13"
initial_cash = 100000.0
```

---

## 🗄️ Database Connection

```python
connection_string = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost;"
    "Database=TradingDB;"
    "Trusted_Connection=yes;"
)
```

### Key Tables
- `Sessions` - Backtest/paper/live sessions
- `Trades` - Individual trades with P&L
- `WebhookEvents` - Simulated webhook logs
- `MarketRegimes` - Detected market regimes

---

## 🚀 How to Run

### Start Dashboard
```powershell
cd dashboard/src
python -m streamlit run dashboard/app.py
```

### Run Backtest (CLI)
```powershell
python backtest/backtest_runner.py --start 2026-01-02 --end 2026-01-13 --cash 100000
```

### Build LEAN
```powershell
cd quantconnect-lean
dotnet build QuantConnect.Lean.sln -c Release
```

### Manual Sync (if needed)
```powershell
.\sync_algorithm.ps1
```

---

## 📝 Session State Keys (Streamlit)

| Key | Purpose |
|-----|---------|
| `backtest_params` | Current parameter values (dict with start_date, rsi_period, etc.) |
| `running_backtest` | Boolean - is backtest running |
| `selected_backtest_session` | Currently selected session ID for webhook view |
| `current_session_id` | Active running session |

---

## 🐛 Debugging Tips

1. **Check LEAN output:** `backtest/results/BT_xxx/TQQQScalpingAlgorithm-log.txt`
2. **Check webhook file:** `backtest/results/BT_xxx/webhook_log.txt`
3. **Check for [WEBHOOK] log:** Should see `[WEBHOOK] Simulation enabled` in LEAN log
4. **Check sync worked:** Look for `[SYNC] Copied...` messages in backtest output
5. **SQL data:** `SELECT * FROM Sessions WHERE SessionType='BACKTEST' ORDER BY StartTime DESC`
6. **Dashboard errors:** Check Streamlit terminal for stack traces

---

## ⚠️ Common Gotchas

| Problem | Cause | Solution |
|---------|-------|----------|
| `datetime.time` error | LEAN overrides `datetime` | Use `from datetime import time as dt_time` |
| Webhook log not created | Wrong param name | Must be `webhook-log-path` (hyphens) |
| Old algorithm running | Files not synced | Auto-sync now built-in, or run `sync_algorithm.ps1` |
| Progress bar stuck | Blocking I/O | Using threaded queue now |
| Import errors in LEAN | Files not in Algorithm.Python | Auto-sync copies them there |

---

## 📌 Quick Reference: File Locations for Common Fixes

| To Fix | Edit This File | Notes |
|--------|---------------|-------|
| Algorithm logic | `algorithms/TQQQScalpingAlgorithm.py` | Auto-syncs to LEAN |
| Webhook simulation | `backtest/webhook_simulator.py` | Auto-syncs to LEAN |
| Backtest UI | `dashboard/src/dashboard/views/backtest_runner.py` | Progress, presets |
| DB queries | `dashboard/src/dashboard/database.py` | Webhook events, sessions |
| LEAN config | `backtest/backtest_runner.py` | Parameters, paths |
| Auto-sync logic | `backtest/backtest_runner.py` | `_sync_algorithm_files()` |

---

## 🔄 Update This Document

When making significant changes:
1. Update the "Last Updated" line at top
2. Add new fixes to the "Recently Fixed" table
3. Update "Common Gotchas" if you discover new issues
4. Keep file locations current

