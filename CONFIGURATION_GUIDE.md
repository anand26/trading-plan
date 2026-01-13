# TQQQ/SQQQ Adaptive Trading System - Configuration Guide

## 1. Configuration Files That Need Your Settings

### 📁 Database Connection (SQL Server)

| File | Settings to Update |
|------|-------------------|
| `.env` (root) | `DB_SERVER`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD` |
| `adaptive-agent/.env` | Same DB settings |
| `learning-store/.env` | Same DB settings |
| `dashboard/.env` | Same DB settings |
| `mcp-servers/lean-ops/.env` | Same DB settings |
| `mcp-servers/trade-mind/.env` | Same DB settings |
| `backtest-pipeline/.env` | Same DB settings |

### 📁 Alpaca API Credentials

| File | Settings to Update |
|------|-------------------|
| `.env` (root) | `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL` |
| `adaptive-agent/.env` | Same Alpaca settings |
| `mcp-servers/lean-ops/.env` | Same Alpaca settings |

### 📁 Mode Settings (Paper vs Live)

| File | Settings to Update |
|------|-------------------|
| `.env` (root) | `TRADING_MODE=paper` or `live` |
| `adaptive-agent/.env` | `AGENT_MODE=paper` or `live` |

---

## 2. Master .env Template

Create this file at `c:\Users\anand\Documents\trading_plan\.env`:

```env
# ============================================
# DATABASE CONFIGURATION
# ============================================
DB_SERVER=localhost
DB_NAME=TradingDB
DB_DRIVER=ODBC Driver 17 for SQL Server
# For SQL Server Authentication (leave blank for Windows Auth):
DB_USERNAME=
DB_PASSWORD=

# ============================================
# ALPACA API CONFIGURATION
# ============================================
# Paper Trading (default)
ALPACA_API_KEY=your_paper_api_key_here
ALPACA_SECRET_KEY=your_paper_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Live Trading (uncomment when ready)
# ALPACA_API_KEY=your_live_api_key_here
# ALPACA_SECRET_KEY=your_live_secret_key_here
# ALPACA_BASE_URL=https://api.alpaca.markets

# ============================================
# TRADING MODE
# ============================================
TRADING_MODE=paper
# Options: paper, live, backtest

# ============================================
# AGENT CONFIGURATION
# ============================================
AGENT_MODE=paper
DRY_RUN=true
CYCLE_INTERVAL_SECONDS=60
LEARNING_ENABLED=true
AUTO_APPLY_RECOMMENDATIONS=false

# ============================================
# RISK THRESHOLDS
# ============================================
MIN_CONFIDENCE_TO_ACT=0.7
MAX_DAILY_PARAMETER_CHANGES=5
EMERGENCY_DRAWDOWN_PCT=0.15
MAX_POSITION_SIZE_PCT=0.20
MAX_DAILY_LOSS_PCT=0.05

# ============================================
# NOTIFICATIONS (Optional)
# ============================================
NOTIFICATIONS_ENABLED=false
SLACK_WEBHOOK_URL=
EMAIL_SMTP_SERVER=

# ============================================
# LOGGING
# ============================================
LOG_LEVEL=INFO
DEBUG=false
```

---

## 3. Where to Get Your Credentials

### Alpaca Paper Account
1. Go to https://app.alpaca.markets/signup
2. Create account and verify email
3. Go to **Paper Trading** section
4. Click **View API Keys**
5. Copy:
   - API Key ID → `ALPACA_API_KEY`
   - Secret Key → `ALPACA_SECRET_KEY`

### SQL Server Database
1. Install SQL Server (Express is free)
2. Create database named `TradingDB`
3. Run schema files in order:
   ```
   database/01_core_schema.sql
   database/02_market_data_schema.sql
   ...
   database/10_adaptive_agent_schema.sql
   ```

---

## 4. Quick Checklist

- [ ] SQL Server installed and running
- [ ] TradingDB database created
- [ ] All 10 schema files executed
- [ ] Alpaca paper account created
- [ ] API keys copied to .env
- [ ] Python 3.11+ installed
- [ ] All dependencies installed (see GETTING_STARTED.md)

---

## 5. Files Reference by Component

### Adaptive Agent
```
adaptive-agent/.env
adaptive-agent/src/adaptive_agent/config.py  # Reads from env
```

### Learning Store
```
learning-store/.env
learning-store/src/learning_store/config.py  # Reads from env
```

### Dashboard
```
dashboard/.env
dashboard/config.py  # Reads from env
```

### MCP Servers
```
mcp-servers/lean-ops/.env
mcp-servers/trade-mind/.env
```

### Backtest Pipeline
```
backtest-pipeline/.env
backtest-pipeline/config.py  # Reads from env
```
