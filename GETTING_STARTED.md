# 🚀 Getting Started Guide

## TQQQ/SQQQ Adaptive Trading System

This guide walks you through setting up and running the complete trading system, from integration testing through paper trading.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Database Setup](#3-database-setup)
4. [Configuration](#4-configuration)
5. [Running Integration Tests](#5-running-integration-tests)
6. [Starting Paper Trading](#6-starting-paper-trading)
7. [Monitoring & Dashboard](#7-monitoring--dashboard)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Prerequisites

### Required Software

| Software | Version | Download |
|----------|---------|----------|
| Python | 3.11+ | https://python.org |
| SQL Server | 2019+ (Express OK) | https://www.microsoft.com/sql-server |
| SSMS (optional) | Latest | For database management |
| Git | Latest | https://git-scm.com |
| ODBC Driver | 17+ | https://docs.microsoft.com/sql/connect/odbc |

### Accounts Needed

| Service | Purpose | Sign Up |
|---------|---------|---------|
| Alpaca | Paper/Live Trading | https://app.alpaca.markets/signup |
| QuantConnect (optional) | Cloud backtesting | https://www.quantconnect.com |

---

## 2. Installation

### Step 2.1: Clone/Navigate to Project
```powershell
cd c:\Users\anand\Documents\trading_plan
```

### Step 2.2: Create Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 2.3: Install All Dependencies
```powershell
# Core dependencies
pip install pyodbc pandas numpy python-dotenv pydantic httpx

# Testing
pip install pytest pytest-asyncio pytest-cov pytest-mock

# Dashboard
pip install streamlit plotly

# Scheduling
pip install apscheduler

# LEAN (local backtesting)
pip install lean

# All at once (recommended):
pip install pyodbc pandas numpy python-dotenv pydantic httpx pytest pytest-asyncio pytest-cov pytest-mock streamlit plotly apscheduler lean
```

### Step 2.4: Install Each Component (Editable Mode)
```powershell
# Adaptive Agent
cd adaptive-agent
pip install -e .
cd ..

# Learning Store
cd learning-store
pip install -e .
cd ..

# Test Suite
cd tests
pip install -e .
cd ..
```

---

## 3. Database Setup

### Step 3.1: Create Database
Open SQL Server Management Studio (SSMS) or use sqlcmd:

```sql
CREATE DATABASE TradingDB;
GO
```

### Step 3.2: Run Schema Files (In Order!)
```powershell
# Using sqlcmd (run each in order)
sqlcmd -S localhost -d TradingDB -i database\01_create_database.sql
sqlcmd -S localhost -d TradingDB -i database\02_core_schema.sql
sqlcmd -S localhost -d TradingDB -i database\03_learning_schema.sql
sqlcmd -S localhost -d TradingDB -i database\04_config_schema.sql
sqlcmd -S localhost -d TradingDB -i database\05_stored_procedures.sql
sqlcmd -S localhost -d TradingDB -i database\06_views_indexes.sql
sqlcmd -S localhost -d TradingDB -i database\07_lean_ops_mcp_schema.sql
sqlcmd -S localhost -d TradingDB -i database\08_trade_mind_mcp_schema.sql
sqlcmd -S localhost -d TradingDB -i database\09_learning_store_schema.sql
sqlcmd -S localhost -d TradingDB -i database\10_adaptive_agent_schema.sql
```

Or use the combined script approach in SSMS.

### Step 3.3: Verify Database
```sql
-- Run in SSMS to verify tables exist
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;
```

Expected tables: `AgentActions`, `AgentDecisions`, `BacktestResults`, `MarketData`, `Patterns`, `Recommendations`, `Trades`, etc.

---

## 4. Configuration

### Step 4.1: Create .env File
```powershell
# Copy template
copy .env.example .env

# Edit with your values
notepad .env
```

### Step 4.2: Required Settings to Update

```env
# Database (if using Windows Auth, leave USERNAME/PASSWORD blank)
DB_SERVER=localhost
DB_NAME=TradingDB

# Alpaca Paper Account (GET THESE FROM alpaca.markets)
ALPACA_API_KEY=PK...your_key_here
ALPACA_SECRET_KEY=...your_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Mode
TRADING_MODE=paper
AGENT_MODE=paper
DRY_RUN=true
```

### Step 4.3: Copy .env to Components
```powershell
copy .env adaptive-agent\.env
copy .env learning-store\.env
copy .env dashboard\.env
copy .env tests\.env.test
```

---

## 5. Running Integration Tests

### Step 5.1: Verify Python Environment
```powershell
python --version  # Should be 3.11+
pip list | Select-String pytest  # Should show pytest
```

### Step 5.2: Run Unit Tests First (No DB Required)
```powershell
cd tests
python -m pytest unit/ -v
```

Expected output: All tests should pass (green).

### Step 5.3: Run Integration Tests (Requires DB)
```powershell
python -m pytest integration/ -v -m database
```

### Step 5.4: Run Full Test Suite
```powershell
python run_tests.py --coverage
```

### Step 5.5: Check Test Report
```powershell
# Open coverage report in browser
start htmlcov\index.html
```

### ✅ Tests Passing? Move to Paper Trading!

---

## 6. Starting Paper Trading

### Phase 1: Validate Components

#### 6.1.1: Test Database Connection
```powershell
python -c "
import pyodbc
conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=TradingDB;Trusted_Connection=yes')
print('✓ Database connected!')
conn.close()
"
```

#### 6.1.2: Test Alpaca Connection
```powershell
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
import httpx

headers = {
    'APCA-API-KEY-ID': os.getenv('ALPACA_API_KEY'),
    'APCA-API-SECRET-KEY': os.getenv('ALPACA_SECRET_KEY')
}
r = httpx.get(os.getenv('ALPACA_BASE_URL') + '/v2/account', headers=headers)
print('✓ Alpaca connected!')
print(f'  Account Status: {r.json()[\"status\"]}')
print(f'  Buying Power: \${float(r.json()[\"buying_power\"]):,.2f}')
"
```

### Phase 2: Run Agent in Dry-Run Mode

#### 6.2.1: Single Cycle Test
```powershell
cd adaptive-agent
python -m adaptive_agent cycle --dry-run --debug
```

This runs ONE cycle without executing trades. Review output.

#### 6.2.2: Run Agent (Dry-Run, Continuous)
```powershell
python -m adaptive_agent run --mode paper --dry-run --interval 60
```

- Press `Ctrl+C` to stop
- Review decisions in console output
- Check database for logged decisions:
  ```sql
  SELECT TOP 10 * FROM AgentDecisions ORDER BY CreatedAt DESC;
  ```

### Phase 3: Enable Paper Trading (Live Execution)

#### 6.3.1: Update Configuration
```env
# In .env
DRY_RUN=false
AGENT_MODE=paper
```

#### 6.3.2: Start Agent
```powershell
python -m adaptive_agent run --mode paper --interval 60
```

#### 6.3.3: Monitor
- Watch console for decisions
- Open dashboard (next section)
- Check Alpaca dashboard for trades

---

## 7. Monitoring & Dashboard

### Start Streamlit Dashboard
```powershell
cd dashboard
streamlit run app.py
```

Opens in browser at http://localhost:8501

### Dashboard Pages
- **Overview**: System status, key metrics
- **Trades**: Recent trades, P&L
- **Regimes**: Market regime detection
- **Learning**: Pattern analysis, recommendations
- **Status**: Component health

### Database Monitoring Queries
```sql
-- Recent trades
SELECT * FROM vw_RecentTrades;

-- Today's performance
SELECT * FROM vw_DailyPerformance WHERE TradeDate = CAST(GETDATE() AS DATE);

-- Agent decisions
SELECT TOP 20 * FROM AgentDecisions ORDER BY CreatedAt DESC;

-- Active patterns
SELECT * FROM vw_PatternAnalysis WHERE Status = 'ACTIVE';
```

---

## 8. Troubleshooting

### Database Connection Errors

**Error**: `pyodbc.InterfaceError: ('IM002', '[IM002] [Microsoft][ODBC Driver Manager] Data source name not found')`

**Solution**:
```powershell
# Check ODBC drivers installed
Get-OdbcDriver | Where-Object {$_.Name -like '*SQL Server*'}

# Install ODBC Driver 17 if missing
# Download from Microsoft
```

### Alpaca Connection Errors

**Error**: `403 Forbidden`

**Solution**:
- Verify API keys are correct
- Check if using paper URL with paper keys
- Ensure account is active (not suspended)

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'adaptive_agent'`

**Solution**:
```powershell
cd adaptive-agent
pip install -e .
```

### Tests Failing

**Issue**: Database tests skipped

**Solution**:
- Ensure SQL Server is running
- Verify connection string in `.env.test`
- Run schema files first

---

## Quick Reference Commands

```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Run tests
cd tests && python run_tests.py

# Start agent (dry-run)
cd adaptive-agent && python -m adaptive_agent run --dry-run

# Start dashboard
cd dashboard && streamlit run app.py

# Check database
sqlcmd -S localhost -d TradingDB -Q "SELECT COUNT(*) FROM Trades"
```

---

## Next Steps After Paper Trading

1. **Monitor for 1-2 weeks** - Observe decisions and patterns
2. **Review learning** - Check if patterns are improving
3. **Tune parameters** - Adjust thresholds based on results
4. **Consider live trading** - Only after consistent paper profits

### Going Live Checklist
- [ ] 2+ weeks profitable paper trading
- [ ] Risk parameters thoroughly tested
- [ ] Emergency stop tested and working
- [ ] Notification system configured
- [ ] Change `TRADING_MODE=live` and `AGENT_MODE=live`
- [ ] Use live Alpaca API keys
- [ ] Start with SMALL position sizes

---

## Support

- Review logs in console output
- Check `AgentDecisions` table for decision history
- Use dashboard for visual monitoring
- Database queries for deep analysis
