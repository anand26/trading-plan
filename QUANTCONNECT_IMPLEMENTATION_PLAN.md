# QuantConnect LEAN - TQQQ/SQQQ Scalping Implementation Plan

**Date:** January 2026  
**Project:** Automated TQQQ/SQQQ Intraday Scalping System  
**Framework:** QuantConnect LEAN Engine  
**Version:** 2.0 - Adaptive Learning Agent Architecture

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Vision: Adaptive Learning Agent](#system-vision-adaptive-learning-agent)
3. [MCP Server Architecture](#mcp-server-architecture)
4. [Build Order & Implementation Sequence](#build-order--implementation-sequence)
5. [QuantConnect LEAN Architecture Overview](#quantconnect-lean-architecture-overview)
6. [What's Provided Out-of-the-Box](#whats-provided-out-of-the-box)
7. [Gap Analysis: Requirements vs Capabilities](#gap-analysis-requirements-vs-capabilities)
8. [Implementation Strategy](#implementation-strategy)
9. [Component Design](#component-design)
10. [Technology Stack](#technology-stack)
11. [Development Roadmap](#development-roadmap)
12. [Risk Assessment](#risk-assessment)
13. [Next Steps](#next-steps)

---

## Executive Summary

### Project Goal
Build a **robust, profitable automated scalping system** for TQQQ/SQQQ 3x leveraged ETFs using:
- **RSI(14) + VWAP + Bollinger Bands** technical strategy
- **Pyramiding** position scaling (50%/30%/20%)
- **Intraday-only** trading (close by 3:50 PM EST)
- **QQQ trend filter** for direction selection
- **Alpaca API** for paper/live trading
- **SQL Server** for persistence
- **Dual MCP Servers** for algorithm operations and adaptive learning
- **Streamlit Dashboard** for control/monitoring

### Why QuantConnect LEAN?

✅ **Native Alpaca Support** - Built-in brokerage model, no custom integration needed  
✅ **Professional-Grade Engine** - Institutional quality backtesting and live trading  
✅ **Python Support** - Write strategies in Python (or C#)  
✅ **Stock/ETF Focus** - Designed for equities, not just crypto  
✅ **Proven Framework** - Used by thousands of quant traders globally  
✅ **Open Source** - Full control and customization  

### Effort Estimate

| Phase | Duration | Status |
|-------|----------|--------|
| Strategy Development | 4-5 days | New Work |
| SQL Server Integration | 3-4 days | Custom Component |
| **LEAN-Ops MCP Server** | 2-3 days | Custom Component |
| **Trade-Mind MCP Server** | 3-4 days | Custom Component |
| Streamlit Dashboard | 2-3 days | Custom Component |
| Testing & Refinement | 3-4 days | Standard Process |
| **Total** | **18-23 days** | **~4 weeks** |

**Key Advantage:** QuantConnect provides 70%+ of needed functionality. Focus effort on business logic, adaptive learning, and custom extensions.

---

## System Vision: Adaptive Learning Agent

### Core Philosophy: "Time the Market, or Market the Time"

The system is designed around an **objective, data-driven adaptive agent** that:

1. **Acts on Quantifiable Data Only** - Every decision is backed by metrics (win rate, Sharpe, drawdown)
2. **Learns from Repetitive Backtests** - Stores historical patterns and correlates parameters with outcomes
3. **Self-Corrects Through Iterations** - Identifies underperformance and suggests/applies corrections
4. **Adapts to Market Regimes** - Detects trending vs mean-reverting vs volatile conditions
5. **Maintains Objectivity** - No emotional bias, pure statistical decision-making

### Agent Decision Loop

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ADAPTIVE LEARNING AGENT LOOP                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐       │
│   │   OBSERVE    │────▶│   ANALYZE    │────▶│     DECIDE       │       │
│   │              │     │              │     │                  │       │
│   │ • Market Data│     │ • Win Rate   │     │ • Continue       │       │
│   │ • Trade Stats│     │ • Drawdown   │     │ • Adjust Params  │       │
│   │ • Sentiment  │     │ • Regime     │     │ • Pause Trading  │       │
│   └──────────────┘     └──────────────┘     └────────┬─────────┘       │
│          ▲                                            │                 │
│          │                                            ▼                 │
│   ┌──────┴───────┐                          ┌──────────────────┐       │
│   │    RECORD    │◀─────────────────────────│     EXECUTE      │       │
│   │              │                          │                  │       │
│   │ • Outcomes   │                          │ • Apply Changes  │       │
│   │ • Patterns   │                          │ • Run Backtest   │       │
│   │ • Learnings  │                          │ • Deploy Live    │       │
│   └──────────────┘                          └──────────────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Learning Dimensions

| Dimension | Data Source | Learning Objective |
|-----------|-------------|-------------------|
| **Technical** | RSI, VWAP, BB values | Optimal entry/exit thresholds per regime |
| **Temporal** | Time-of-day patterns | Best trading hours, avoid specific windows |
| **Market Regime** | QQQ trend, VIX levels | Parameter sets per market condition |
| **Performance** | Win rate, Sharpe, drawdown | Self-correction triggers |
| **Sentiment** | External feeds (optional) | Confirm/deny technical signals |

---

## MCP Server Architecture

### Dual MCP Server Design

The system uses **two specialized MCP servers** with distinct responsibilities:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI AGENT INTEGRATION LAYER                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         ┌───────────────────┐                           │
│                         │    Claude/LLM     │                           │
│                         │   (AI Agent)      │                           │
│                         └─────────┬─────────┘                           │
│                                   │                                     │
│              ┌────────────────────┼────────────────────┐                │
│              │                    │                    │                │
│              ▼                    ▼                    ▼                │
│  ┌───────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
│  │   LEAN-OPS MCP    │  │  TRADE-MIND MCP │  │    Streamlit        │   │
│  │   (Operations)    │  │  (Analytics &   │  │    Dashboard        │   │
│  │                   │  │   Learning)     │  │                     │   │
│  └─────────┬─────────┘  └────────┬────────┘  └──────────┬──────────┘   │
│            │                     │                      │               │
│            ▼                     ▼                      ▼               │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                      SQL SERVER                               │     │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │     │
│  │  │ Trades  │ │ Orders  │ │ Params  │ │Learning │ │Backtest │ │     │
│  │  └─────────┘ └─────────┘ └─────────┘ │ Store   │ │ Results │ │     │
│  │                                       └─────────┘ └─────────┘ │     │
│  └───────────────────────────────────────────────────────────────┘     │
│            │                                                            │
│            ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    QUANTCONNECT LEAN ENGINE                      │   │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐     │   │
│  │   │  Backtest   │  │  Live Trade │  │  Alpaca Brokerage   │     │   │
│  │   │  Engine     │  │  Engine     │  │  Integration        │     │   │
│  │   └─────────────┘  └─────────────┘  └─────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### MCP Server 1: LEAN-Ops (Algorithm Operations)

**Purpose:** Interface with QuantConnect LEAN for algorithm lifecycle management

**Server Name:** `lean-ops-mcp`  
**Technology:** Python (to leverage LEAN's Python APIs directly)

#### Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `create_algorithm` | Create new algorithm from template | `name`, `strategy_type`, `symbols` |
| `run_backtest` | Execute backtest with parameters | `algorithm_id`, `start_date`, `end_date`, `params` |
| `get_backtest_results` | Retrieve backtest statistics | `backtest_id` |
| `deploy_paper` | Deploy to Alpaca paper trading | `algorithm_id` |
| `deploy_live` | Deploy to Alpaca live (with safeguards) | `algorithm_id`, `confirm_code` |
| `stop_algorithm` | Emergency stop / graceful shutdown | `algorithm_id`, `reason` |
| `update_parameters` | Hot-reload strategy parameters | `algorithm_id`, `params` |
| `get_algorithm_status` | Current state, positions, P&L | `algorithm_id` |
| `liquidate_positions` | Emergency liquidation | `algorithm_id`, `symbols` (optional) |

#### Example Tool Implementation

```python
# lean-ops-mcp/tools/backtest.py
async def run_backtest_impl(
    algorithm_id: str,
    start_date: str,
    end_date: str,
    params: dict
) -> dict:
    """
    Execute a backtest using LEAN engine.
    Returns comprehensive results for learning agent.
    """
    # Update parameters in SQL
    update_strategy_params(algorithm_id, params)
    
    # Trigger LEAN backtest
    result = lean_engine.run_backtest(
        algorithm=algorithm_id,
        start=start_date,
        end=end_date
    )
    
    # Store results for learning
    store_backtest_outcome(
        algorithm_id=algorithm_id,
        params=params,
        results=result,
        market_regime=detect_regime(start_date, end_date)
    )
    
    return {
        "backtest_id": result.id,
        "sharpe_ratio": result.sharpe,
        "total_return": result.total_return,
        "max_drawdown": result.max_drawdown,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
        "profit_factor": result.profit_factor
    }
```

---

### MCP Server 2: Trade-Mind (Analytics & Learning)

**Purpose:** Provide trading analytics, performance insights, and adaptive learning capabilities

**Server Name:** `trade-mind-mcp`  
**Technology:** Python (for data analysis and ML capabilities)

#### Core Tools (Statistics & Analytics)

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_last_trades` | Recent trade history with details | `count`, `symbol`, `session_id` |
| `calculate_win_rate` | Win rate and related statistics | `session_id`, `date_range` |
| `get_daily_pnl` | Daily P&L breakdown and equity curve | `session_id`, `days` |
| `analyze_drawdown` | Drawdown analysis with recovery times | `session_id` |
| `get_performance_summary` | Comprehensive performance metrics | `session_id` |

#### Learning Tools (Adaptive Intelligence)

| Tool | Description | Parameters |
|------|-------------|------------|
| `detect_market_regime` | Identify current market condition | `lookback_days` |
| `get_optimal_params` | Best parameters for current regime | `strategy_id`, `regime` |
| `suggest_corrections` | AI-driven improvement suggestions | `session_id`, `strategy_id` |
| `compare_backtests` | Compare multiple backtest outcomes | `backtest_ids[]` |
| `analyze_pattern` | Find patterns in losing/winning trades | `session_id`, `outcome_filter` |
| `record_learning` | Store a new pattern/insight | `pattern_type`, `data` |

#### Sentiment Tools (Optional - Future)

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_market_sentiment` | Current market sentiment score | `symbols[]` |
| `get_news_impact` | Recent news impact analysis | `symbol`, `hours` |
| `get_vix_context` | VIX-based risk context | None |

#### Example: Self-Correction Flow

```python
# trade-mind-mcp/tools/learning.py
async def suggest_corrections_impl(
    session_id: str,
    strategy_id: str
) -> dict:
    """
    Analyze current performance and suggest data-backed corrections.
    This is the core of the adaptive learning system.
    """
    # Get current statistics
    current_stats = await calculate_win_rate_impl(session_id)
    
    # Query learning store for historical patterns
    learning_store = LearningStore()
    historical_patterns = learning_store.get_patterns(strategy_id)
    
    # Detect current market regime
    regime = await detect_market_regime_impl(lookback_days=20)
    
    # Get best historical params for this regime
    optimal_params = learning_store.get_best_params(strategy_id, regime)
    
    # Generate corrections
    corrections = []
    
    # Win rate analysis
    if current_stats["win_rate"]["value"] < 0.40:
        corrections.append({
            "type": "ENTRY_CRITERIA",
            "priority": "HIGH",
            "observation": f"Win rate {current_stats['win_rate']['percentage']} below 40% threshold",
            "suggestion": "Tighten RSI oversold from 30 to 25",
            "data_support": {
                "historical_win_rate_at_25": historical_patterns.get("rsi_25_win_rate", "N/A"),
                "sample_size": historical_patterns.get("rsi_25_sample_size", 0)
            }
        })
    
    # Profit factor analysis
    if current_stats["profit_factor"] < 1.2:
        corrections.append({
            "type": "EXIT_CRITERIA",
            "priority": "MEDIUM",
            "observation": f"Profit factor {current_stats['profit_factor']:.2f} indicates poor risk/reward",
            "suggestion": "Increase take profit target from 1.5% to 2.0%",
            "data_support": optimal_params.get("take_profit_analysis", {})
        })
    
    # Drawdown analysis
    if current_stats.get("max_drawdown", 0) > 15:
        corrections.append({
            "type": "RISK_MANAGEMENT",
            "priority": "CRITICAL",
            "observation": f"Max drawdown {current_stats['max_drawdown']:.1f}% exceeds 15% limit",
            "suggestion": "Reduce position size by 30% until drawdown recovers",
            "action": {
                "param": "position_size_level1",
                "current": 0.5,
                "suggested": 0.35
            }
        })
    
    return {
        "session_id": session_id,
        "strategy_id": strategy_id,
        "current_regime": regime,
        "performance_grade": _grade_performance(current_stats),
        "corrections": corrections,
        "optimal_params_for_regime": optimal_params,
        "recommendation": _generate_recommendation(corrections)
    }

def _grade_performance(stats: dict) -> str:
    """Grade overall performance A-F"""
    score = 0
    if stats["win_rate"]["value"] > 0.55: score += 2
    elif stats["win_rate"]["value"] > 0.45: score += 1
    
    if stats["profit_factor"] > 2.0: score += 2
    elif stats["profit_factor"] > 1.5: score += 1
    
    if stats["sharpe_ratio"] > 2.0: score += 2
    elif stats["sharpe_ratio"] > 1.0: score += 1
    
    grades = {6: "A", 5: "B+", 4: "B", 3: "C+", 2: "C", 1: "D", 0: "F"}
    return grades.get(score, "F")
```

---

## Build Order & Implementation Sequence

### Phase Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     IMPLEMENTATION SEQUENCE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PHASE 1                PHASE 2              PHASE 3                    │
│  Foundation             Core MCP             Intelligence               │
│  (Week 1-2)             (Week 2-3)           (Week 3-4)                 │
│                                                                         │
│  ┌─────────────┐       ┌─────────────┐      ┌─────────────┐            │
│  │ 1. Strategy │       │ 5. LEAN-Ops │      │ 8. Learning │            │
│  │    Core     │       │    MCP      │      │    Store    │            │
│  └──────┬──────┘       └──────┬──────┘      └──────┬──────┘            │
│         │                     │                    │                    │
│         ▼                     ▼                    ▼                    │
│  ┌─────────────┐       ┌─────────────┐      ┌─────────────┐            │
│  │ 2. SQL      │       │ 6. Trade-   │      │ 9. Adaptive │            │
│  │    Schema   │       │    Mind MCP │      │    Agent    │            │
│  └──────┬──────┘       └──────┬──────┘      └──────┬──────┘            │
│         │                     │                    │                    │
│         ▼                     ▼                    ▼                    │
│  ┌─────────────┐       ┌─────────────┐      ┌─────────────┐            │
│  │ 3. Backtest │       │ 7. Dashboard│      │ 10. Testing │            │
│  │    Pipeline │       │             │      │  & Tuning   │            │
│  └──────┬──────┘       └─────────────┘      └─────────────┘            │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────┐                                                        │
│  │ 4. SQL      │                                                        │
│  │   Connector │                                                        │
│  └─────────────┘                                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Detailed Build Order

#### **Phase 1: Foundation (Days 1-8)**

| # | Item | Description | Duration | Dependencies |
|---|------|-------------|----------|--------------|
| 1 | **TQQQ Strategy Core** | RSI+VWAP+BB algorithm in Python | 3 days | None |
| 2 | **SQL Server Schema** | Tables for trades, orders, params, learning | 1 day | None |
| 3 | **Backtest Pipeline** | Run strategy through LEAN backtest engine | 2 days | #1 |
| 4 | **SQL Connector** | Algorithm writes to SQL on events | 2 days | #1, #2 |

**Deliverable:** Working algorithm with SQL persistence, validated via backtest

---

#### **Phase 2: Core MCP Servers (Days 9-16)**

| # | Item | Description | Duration | Dependencies |
|---|------|-------------|----------|--------------|
| 5 | **LEAN-Ops MCP Server** | Algorithm operations tools | 3 days | #1, #3 |
|   | └─ `run_backtest` | Execute backtest via MCP | | |
|   | └─ `get_backtest_results` | Retrieve statistics | | |
|   | └─ `update_parameters` | Hot-reload params | | |
|   | └─ `deploy_paper` | Paper trading deployment | | |
|   | └─ `stop_algorithm` | Emergency stop | | |
| 6 | **Trade-Mind MCP Server** | Analytics & learning tools | 3 days | #2, #4 |
|   | └─ `get_last_trades` | Recent trade history | | |
|   | └─ `calculate_win_rate` | Win rate statistics | | |
|   | └─ `get_daily_pnl` | P&L breakdown | | |
|   | └─ `detect_market_regime` | Regime classification | | |
|   | └─ `suggest_corrections` | AI-driven suggestions | | |
| 7 | **Streamlit Dashboard** | UI for monitoring & control | 2 days | #2, #5 |

**Deliverable:** Both MCP servers operational, Dashboard showing real-time data

---

#### **Phase 3: Intelligence Layer (Days 17-23)**

| # | Item | Description | Duration | Dependencies |
|---|------|-------------|----------|--------------|
| 8 | **Learning Store** | SQL tables + logic for pattern storage | 2 days | #2, #6 |
|   | └─ Backtest outcome history | | | |
|   | └─ Parameter → Performance correlations | | | |
|   | └─ Market regime mappings | | | |
| 9 | **Adaptive Agent Logic** | Self-correction implementation | 2 days | #6, #8 |
|   | └─ Performance grading (A-F) | | | |
|   | └─ Automatic correction triggers | | | |
|   | └─ Parameter optimization loop | | | |
| 10 | **Integration Testing** | End-to-end system validation | 2-3 days | All |
|    | └─ Paper trading validation | | | |
|    | └─ Agent decision verification | | | |
|    | └─ Learning loop confirmation | | | |

**Deliverable:** Fully operational adaptive trading system

---

### Component Dependency Graph

```
                    ┌──────────────────┐
                    │  AI Agent (LLM)  │
                    └────────┬─────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌────────────┐    ┌────────────┐    ┌────────────┐
    │ LEAN-Ops   │    │ Trade-Mind │    │ Dashboard  │
    │    MCP     │    │    MCP     │    │ (Streamlit)│
    │    (#5)    │    │    (#6)    │    │    (#7)    │
    └──────┬─────┘    └──────┬─────┘    └──────┬─────┘
           │                 │                 │
           │         ┌───────┴───────┐         │
           │         │               │         │
           │         ▼               ▼         │
           │  ┌────────────┐  ┌────────────┐   │
           │  │  Learning  │  │   SQL      │   │
           │  │   Store    │  │ Connector  │   │
           │  │    (#8)    │  │    (#4)    │   │
           │  └──────┬─────┘  └──────┬─────┘   │
           │         │               │         │
           │         └───────┬───────┘         │
           │                 │                 │
           │                 ▼                 │
           │         ┌────────────┐            │
           │         │ SQL Server │◀───────────┘
           │         │ Schema (#2)│
           │         └──────┬─────┘
           │                │
           │                │
           ▼                ▼
    ┌────────────┐   ┌────────────┐
    │  Backtest  │   │  Strategy  │
    │ Pipeline   │   │   Core     │
    │    (#3)    │◀──│    (#1)    │
    └────────────┘   └────────────┘
           │
           ▼
    ┌────────────┐
    │   LEAN     │
    │  Engine    │
    └────────────┘
```

---

### File Structure After Implementation

```
trading_plan/
├── QUANTCONNECT_IMPLEMENTATION_PLAN.md
├── QUANTCONNECT_ARCHITECTURE.puml
│
├── quantconnect-lean/              # LEAN Engine (existing)
│   └── Algorithm.Python/
│       └── TQQQScalpingAlgorithm.py    # (#1) Strategy Core
│
├── database/                       # (#2) SQL Schema
│   ├── create_schema.sql
│   ├── create_learning_tables.sql
│   └── seed_parameters.sql
│
├── lean-ops-mcp/                   # (#5) Operations MCP Server
│   ├── pyproject.toml
│   ├── src/
│   │   ├── server.py
│   │   ├── tools/
│   │   │   ├── backtest.py
│   │   │   ├── deployment.py
│   │   │   ├── parameters.py
│   │   │   └── status.py
│   │   └── lean_adapter.py
│   └── README.md
│
├── trade-mind-mcp/                 # (#6) Analytics MCP Server
│   ├── pyproject.toml
│   ├── src/
│   │   ├── server.py
│   │   ├── tools/
│   │   │   ├── trades.py           # get_last_trades
│   │   │   ├── statistics.py       # calculate_win_rate
│   │   │   ├── pnl.py              # get_daily_pnl
│   │   │   ├── regime.py           # detect_market_regime
│   │   │   └── learning.py         # suggest_corrections
│   │   ├── data/
│   │   │   ├── sql_adapter.py
│   │   │   └── learning_store.py   # (#8)
│   │   └── models/
│   │       └── trade.py
│   └── README.md
│
├── dashboard/                      # (#7) Streamlit Dashboard
│   ├── app.py
│   ├── components/
│   │   ├── equity_chart.py
│   │   ├── trade_table.py
│   │   └── controls.py
│   └── requirements.txt
│
└── docker-compose.yml              # Deployment orchestration
```

---

## QuantConnect LEAN Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      QUANTCONNECT LEAN ENGINE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐  │
│  │   Algorithm  │───▶│  Data Feed   │───▶│  Brokerage API  │  │
│  │   (Python)   │    │   Handler    │    │    (Alpaca)     │  │
│  └──────────────┘    └──────────────┘    └─────────────────┘  │
│         │                    │                      │            │
│         │                    ▼                      │            │
│         │           ┌──────────────┐                │            │
│         │           │  Historical  │                │            │
│         │           │     Data     │                │            │
│         │           └──────────────┘                │            │
│         │                                           │            │
│         ▼                                           ▼            │
│  ┌──────────────┐                        ┌─────────────────┐   │
│  │  Portfolio   │                        │   Transaction   │   │
│  │  Management  │◀──────────────────────│     Manager     │   │
│  └──────────────┘                        └─────────────────┘   │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │   Results    │                                               │
│  │   Handler    │                                               │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Key Architecture Elements

#### 1. **Algorithm Base Class (QCAlgorithm)**
- **Location:** `Algorithm/QCAlgorithm.cs` (3,822 lines)
- **Purpose:** Base class for all strategies
- **Key Methods:**
  ```python
  def Initialize(self):
      # Setup parameters, add securities, indicators
  
  def OnData(self, data):
      # Called on each new data point (5-min bars for us)
      # Execute trading logic here
  ```

#### 2. **Engine (Engine.cs)**
- **Location:** `Engine/Engine.cs` (561 lines)
- **Purpose:** Main execution loop, orchestrates all components
- **Responsibilities:**
  - Load algorithms
  - Manage data feeds
  - Execute backtests or live trading
  - Handle time synchronization

#### 3. **Alpaca Brokerage Model**
- **Location:** `Common/Brokerages/AlpacaBrokerageModel.cs` (149 lines)
- **Purpose:** Alpaca-specific order handling, fees, market hours
- **Supported Order Types:**
  ```csharp
  SecurityType.Equity: Market, Limit, StopMarket, StopLimit, 
                       TrailingStop, MarketOnOpen, MarketOnClose
  ```
- **Fee Model:** Built-in `AlpacaFeeModel()`

#### 4. **Data Feed Handler**
- **Location:** `Engine/DataFeeds/` directory
- **Purpose:** Subscribe to real-time and historical data
- **Data Sources:**
  - Live: WebSocket connections
  - Backtest: Local data or QuantConnect cloud

#### 5. **Securities & Portfolio**
- **Location:** `Common/Securities/` directory
- **Purpose:** Track positions, calculate P&L, manage buying power
- **Key Classes:**
  - `SecurityHolding` - Current position state
  - `SecurityPortfolioManager` - Aggregate portfolio view
  - `BuyingPowerModel` - Margin calculations

#### 6. **Transaction Manager**
- **Location:** Part of `QCAlgorithm` class
- **Purpose:** Order submission, fills, cancellations
- **Key Methods:**
  - `Buy()`, `Sell()`, `Order()`
  - `SetHoldings()` - Percentage-based positioning
  - `Liquidate()` - Close all positions

### Data Flow Sequence

```
1. Engine starts → Load algorithm
2. Algorithm.Initialize() → Add TQQQ, SQQQ, QQQ
3. Subscribe to 5-min bar data
4. Backtest Mode: Load historical data
   Live Mode: Connect to Alpaca WebSocket
5. For each new 5-min bar:
   a. Update indicators (RSI, VWAP, BB)
   b. Call Algorithm.OnData(slice)
   c. Strategy logic evaluates entry/exit
   d. Submit orders via Transactions
   e. Fill simulation (backtest) or Alpaca API (live)
   f. Update Portfolio holdings
6. Results aggregation
7. Persist results (built-in: JSON, CSV)
```

### Algorithm Lifecycle

```python
class TQQQScalpingAlgorithm(QCAlgorithm):
    def Initialize(self):
        # Called once at startup
        self.SetStartDate(2020, 1, 1)
        self.SetCash(100000)
        
        # Add securities
        self.tqqq = self.AddEquity("TQQQ", Resolution.Minute).Symbol
        self.sqqq = self.AddEquity("SQQQ", Resolution.Minute).Symbol
        self.qqq = self.AddEquity("QQQ", Resolution.Minute).Symbol
        
        # Add indicators
        self.rsi = self.RSI("TQQQ", 14, Resolution.Minute)
        self.bb = self.BB("TQQQ", 20, 2, Resolution.Minute)
        self.vwap = self.VWAP("TQQQ", 5)
        
        # Schedule daily close
        self.Schedule.On(
            self.DateRules.EveryDay("TQQQ"),
            self.TimeRules.At(15, 50),
            self.CloseAllPositions
        )
    
    def OnData(self, data):
        # Called for each new 5-min bar
        if not data.ContainsKey(self.tqqq):
            return
        
        # Strategy logic here
        if self.rsi.Current.Value < 30:
            self.SetHoldings(self.tqqq, 0.5)  # 50% entry
```

---

## What's Provided Out-of-the-Box

### ✅ Available Components (No Custom Development)

#### 1. **Alpaca Integration** ⭐
- **Status:** ✅ Fully Built
- **What Works:**
  - Live trading connection
  - Paper trading support
  - Order submission (Market, Limit, Stop)
  - Position synchronization
  - Account data retrieval
- **Configuration:**
  ```json
  {
    "live-mode-brokerage": "AlpacaBrokerage",
    "alpaca-key-id": "YOUR_KEY",
    "alpaca-secret-key": "YOUR_SECRET",
    "alpaca-paper-trading": true
  }
  ```

#### 2. **Historical Data Access** ⭐
- **Status:** ✅ Fully Built
- **Data Available:**
  - Minute/5-minute bars
  - Daily bars
  - Tick data (premium)
  - 7+ years of US equity data
- **Usage:**
  ```python
  history = self.History(["TQQQ", "SQQQ"], 
                        timedelta(days=365), 
                        Resolution.Minute)
  ```

#### 3. **Technical Indicators** ⭐
- **Status:** ✅ Fully Built (70+ indicators)
- **Available Indicators:**
  - `RSI()` - Relative Strength Index
  - `BB()` - Bollinger Bands
  - `VWAP()` - Volume Weighted Average Price
  - `EMA()`, `SMA()` - Moving Averages
  - Custom indicator framework
- **Auto-Updating:** Indicators update automatically on new data

#### 4. **Backtesting Engine** ⭐
- **Status:** ✅ Production Ready
- **Features:**
  - Event-driven simulation
  - Realistic fill modeling
  - Slippage models
  - Commission modeling
  - Margin calculations
  - Performance metrics (Sharpe, drawdown, etc.)

#### 5. **Order Management** ⭐
- **Status:** ✅ Fully Built
- **Order Types:**
  - Market, Limit, Stop, StopLimit
  - TrailingStop
  - Time-in-force options
- **Portfolio Methods:**
  - `SetHoldings(symbol, percentage)` - Automated position sizing
  - `Buy()`, `Sell()`, `Liquidate()`
  - `Portfolio[symbol].Quantity` - Current position

#### 6. **Scheduling System** ⭐
- **Status:** ✅ Fully Built
- **Capabilities:**
  ```python
  # Daily close at 3:50 PM
  self.Schedule.On(
      self.DateRules.EveryDay(),
      self.TimeRules.At(15, 50),
      self.CloseAllPositions
  )
  
  # Market open action
  self.Schedule.On(
      self.DateRules.EveryDay(),
      self.TimeRules.AfterMarketOpen("TQQQ", 5),
      self.ResetDailyVariables
  )
  ```

#### 7. **Market Hours Enforcement** ⭐
- **Status:** ✅ Built-In
- **Features:**
  - Automatic market hours detection
  - Pre-market / after-hours handling
  - Exchange calendar integration
  - Holiday handling

#### 8. **Results & Reporting** ⭐
- **Status:** ✅ Built-In
- **Output Formats:**
  - JSON results file
  - CSV trade logs
  - Equity curve charts
  - Statistics (Sharpe, Sortino, Win Rate, etc.)
  - Drawdown analysis

---

## Gap Analysis: Requirements vs Capabilities

### Requirements Breakdown

| Requirement | QuantConnect Status | Gap | Effort |
|------------|---------------------|-----|--------|
| **1. TQQQ/SQQQ trading** | ✅ Native equity support | None | 0 days |
| **2. 5-min bars** | ✅ Resolution.Minute (5x) | None | 0 days |
| **3. Alpaca live trading** | ✅ AlpacaBrokerageModel | None | 0 days |
| **4. RSI indicator** | ✅ Built-in RSI(14) | None | 0 days |
| **5. VWAP indicator** | ✅ Built-in VWAP() | None | 0 days |
| **6. Bollinger Bands** | ✅ Built-in BB(20,2) | None | 0 days |
| **7. QQQ trend filter** | ✅ AddEquity("QQQ") | None | 0 days |
| **8. Backtesting** | ✅ Built-in engine | None | 0 days |
| **9. Intraday close (3:50 PM)** | ✅ Schedule.At() | None | 0 days |
| **10. Pyramiding (3 levels)** | ⚠️ Partial | **Need custom logic** | 2 days |
| **11. SQL Server persistence** | ❌ Not built-in | **Custom component** | 3-4 days |
| **12. MCP Server** | ❌ Not in LEAN | **External service** | 2-3 days |
| **13. Streamlit Dashboard** | ❌ Not in LEAN | **External service** | 2-3 days |
| **14. Parameter injection API** | ⚠️ Partial | **Custom extension** | 1-2 days |
| **15. Emergency stop** | ✅ Liquidate() method | None | 0 days |

### Critical Gaps Requiring Custom Development

#### **Gap 1: Pyramiding Position Scaling** 🔧
- **What's Missing:** QuantConnect has `SetHoldings()` but no built-in multi-level entry tracking
- **What's Needed:**
  ```python
  # Track multiple entry levels per position
  class PositionTracker:
      entries = []  # [(price, quantity, timestamp), ...]
      total_quantity = 0
      average_price = 0
  
  # Strategy logic
  if first_entry_signal:
      self.SetHoldings(self.tqqq, 0.5)  # 50%
      position_tracker.add_entry(price, qty)
  
  elif second_entry_signal and position_tracker.profit > 0.003:
      current_qty = self.Portfolio[self.tqqq].Quantity
      additional = calculate_30_percent(self.Portfolio.TotalPortfolioValue)
      self.SetHoldings(self.tqqq, additional)  # Add 30%
      position_tracker.add_entry(price, qty)
  ```
- **Effort:** 2 days (Python class + integration)

#### **Gap 2: SQL Server Persistence** 🔧
- **What's Missing:** QuantConnect saves to JSON/CSV, not SQL Server
- **What's Needed:**
  - Custom `OnOrderEvent()` callback
  - SQL Server connection (pyodbc)
  - Schema: Trades, Orders, Positions, DailyPerformance, Bars
  - Example:
    ```python
    def OnOrderEvent(self, orderEvent):
        if orderEvent.Status == OrderStatus.Filled:
            self.save_to_sql(orderEvent)
    
    def save_to_sql(self, order):
        conn = pyodbc.connect(self.sql_connection_string)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Trades (Symbol, Quantity, Price, Timestamp)
            VALUES (?, ?, ?, ?)
        """, (order.Symbol, order.FillQuantity, order.FillPrice, order.Time))
        conn.commit()
    ```
- **Effort:** 3-4 days (schema design + integration + testing)

#### **Gap 3: MCP Server for Natural Language Queries** 🔧
- **What's Missing:** No MCP server component in LEAN
- **What's Needed:**
  - **Separate TypeScript service** (not part of LEAN engine)
  - Connect to SQL Server (reads data written by LEAN)
  - MCP protocol tools for queries:
    ```typescript
    tools: [
      { name: "get_last_trades", handler: queryLastTrades },
      { name: "calculate_win_rate", handler: calculateWinRate },
      { name: "get_daily_pnl", handler: getDailyPnL }
    ]
    ```
- **Architecture:** MCP Server ← SQL Server ← LEAN Algorithm
- **Effort:** 2-3 days (reuse design from Freqtrade planning)

#### **Gap 4: Streamlit Dashboard** 🔧
- **What's Missing:** No built-in UI dashboard
- **What's Needed:**
  - **Separate Python Streamlit app** (not part of LEAN)
  - Read from SQL Server (same data as MCP)
  - Controls:
    ```python
    if st.button("Start Bot"):
        # Send API call to LEAN or modify config
    
    if st.button("EMERGENCY STOP"):
        # Call self.Liquidate() via API
    ```
- **Integration:** Dashboard → SQL Server ← LEAN Algorithm
- **Effort:** 2-3 days

#### **Gap 5: Parameter Injection API** 🔧
- **What's Missing:** QuantConnect supports parameters but not hot-reload
- **What's Needed:**
  ```python
  class TQQQScalpingAlgorithm(QCAlgorithm):
      def Initialize(self):
          # Read from config or API
          self.rsi_period = self.GetParameter("rsi_period", 14)
          self.rsi_oversold = self.GetParameter("rsi_oversold", 30)
          
          # Check for updates every minute
          self.Schedule.On(
              self.DateRules.EveryDay(),
              self.TimeRules.Every(timedelta(minutes=1)),
              self.ReloadParameters
          )
      
      def ReloadParameters(self):
          # Read from SQL or file
          new_params = read_parameters_from_sql()
          if new_params != current_params:
              self.rsi_oversold = new_params['rsi_oversold']
  ```
- **Effort:** 1-2 days

---

## Implementation Strategy

### Approach: Hybrid Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      HYBRID SYSTEM ARCHITECTURE                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │             QUANTCONNECT LEAN ENGINE (Core)                  │    │
│  │  ┌────────────────────────────────────────────────────┐     │    │
│  │  │  TQQQScalpingAlgorithm (Python)                     │     │    │
│  │  │  - RSI + VWAP + BB strategy logic                   │     │    │
│  │  │  - Pyramiding position tracker                      │     │    │
│  │  │  - QQQ trend filter                                 │     │    │
│  │  │  - Intraday schedule (3:50 PM close)                │     │    │
│  │  └────────────────────────────────────────────────────┘     │    │
│  │          │                                                    │    │
│  │          ▼                                                    │    │
│  │  ┌────────────────────────────────────────────────────┐     │    │
│  │  │  Custom SQL Server Connector                        │     │    │
│  │  │  - OnOrderEvent() → Save to SQL                     │     │    │
│  │  │  - OnData() → Save bars to SQL (optional)          │     │    │
│  │  └────────────────────────────────────────────────────┘     │    │
│  └────────────────┬───────────────────────┬───────────────────┘    │
│                   │                       │                          │
│                   │                       │                          │
│                   ▼                       ▼                          │
│         ┌─────────────────┐    ┌──────────────────┐                │
│         │   Alpaca API    │    │   SQL Server     │                │
│         │   (Brokerage)   │    │   (Persistence)  │                │
│         └─────────────────┘    └──────────────────┘                │
│                                         │                            │
│                   ┌─────────────────────┼──────────────────┐        │
│                   │                     │                  │        │
│                   ▼                     ▼                  ▼        │
│         ┌──────────────────┐  ┌─────────────────┐  ┌──────────────┐│
│         │  MCP Server      │  │   Streamlit     │  │  Parameter   ││
│         │  (TypeScript)    │  │   Dashboard     │  │  Config API  ││
│         │  - Natural Lang  │  │   - Control     │  │  - Hot-reload││
│         │  - Analytics     │  │   - Monitor     │  │              ││
│         └──────────────────┘  └─────────────────┘  └──────────────┘│
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

1. **Leverage LEAN's Strengths:** Use proven engine for algo execution, backtesting, Alpaca integration
2. **Add Missing Pieces:** Build only what's not there (SQL, MCP, Dashboard)
3. **Loose Coupling:** Services communicate via SQL Server (shared database pattern)
4. **Independent Scaling:** Each component can be developed/tested independently

---

## Component Design

### Component 1: TQQQ Scalping Algorithm (Python)

**File:** `tqqq_scalping_algorithm.py`

```python
from AlgorithmImports import *
import pyodbc

class TQQQScalpingAlgorithm(QCAlgorithm):
    
    def Initialize(self):
        """Initialize algorithm"""
        # Dates and cash
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(100000)
        
        # Set Alpaca brokerage
        self.SetBrokerageModel(BrokerageName.Alpaca, AccountType.Margin)
        
        # Add securities (5-min resolution)
        self.tqqq = self.AddEquity("TQQQ", Resolution.Minute).Symbol
        self.sqqq = self.AddEquity("SQQQ", Resolution.Minute).Symbol
        self.qqq = self.AddEquity("QQQ", Resolution.Minute).Symbol
        
        # Consolidate to 5-min bars
        self.Consolidate(self.tqqq, timedelta(minutes=5), self.OnTQQQBar)
        self.Consolidate(self.sqqq, timedelta(minutes=5), self.OnSQQQBar)
        
        # Add indicators (auto-updating)
        self.tqqq_rsi = self.RSI(self.tqqq, 14, Resolution.Minute)
        self.tqqq_bb = self.BB(self.tqqq, 20, 2, Resolution.Minute)
        self.tqqq_vwap = self.VWAP(self.tqqq)
        
        self.sqqq_rsi = self.RSI(self.sqqq, 14, Resolution.Minute)
        
        # QQQ trend filter (EMA 9 and 21)
        self.qqq_ema9 = self.EMA(self.qqq, 9, Resolution.Minute)
        self.qqq_ema21 = self.EMA(self.qqq, 21, Resolution.Minute)
        
        # Position tracking for pyramiding
        self.position_tracker = {
            'TQQQ': PositionTracker(),
            'SQQQ': PositionTracker()
        }
        
        # SQL Server connection
        self.sql_conn = pyodbc.connect(
            "DRIVER={SQL Server};"
            "SERVER=localhost;"
            "DATABASE=TradingDB;"
            "Trusted_Connection=yes;"
        )
        
        # Schedule daily close at 3:50 PM EST
        self.Schedule.On(
            self.DateRules.EveryDay(self.tqqq),
            self.TimeRules.At(15, 50),
            self.CloseAllPositions
        )
        
        # Warmup period (2 weeks for indicators)
        self.SetWarmUp(timedelta(days=14))
    
    def OnTQQQBar(self, bar):
        """Process 5-min TQQQ bar"""
        if self.IsWarmingUp:
            return
        
        # Check indicators are ready
        if not (self.tqqq_rsi.IsReady and self.tqqq_bb.IsReady):
            return
        
        # Get indicator values
        rsi = self.tqqq_rsi.Current.Value
        bb_upper = self.tqqq_bb.UpperBand.Current.Value
        bb_lower = self.tqqq_bb.LowerBand.Current.Value
        vwap = self.tqqq_vwap.Current.Value
        price = bar.Close
        
        # QQQ trend
        qqq_uptrend = self.qqq_ema9.Current.Value > self.qqq_ema21.Current.Value
        
        # Volume confirmation
        avg_volume = self.History(self.tqqq, 20, Resolution.Daily)["volume"].mean()
        volume_spike = bar.Volume > avg_volume * 1.5
        
        # Get current position
        current_position = self.Portfolio[self.tqqq].Quantity
        tracker = self.position_tracker['TQQQ']
        
        # ENTRY LOGIC
        if current_position == 0 and qqq_uptrend:
            # First entry: RSI oversold + near BB lower
            if rsi < 30 and price < bb_lower and volume_spike:
                self.SetHoldings(self.tqqq, 0.5)  # 50% of capital
                tracker.add_entry(price, self.Portfolio[self.tqqq].Quantity, self.Time)
                self.Log(f"TQQQ Entry 1: Price={price}, RSI={rsi}")
        
        elif current_position > 0 and tracker.num_entries < 3:
            # Second entry: Position profitable + RSI still oversold
            profit_pct = tracker.calculate_profit(price)
            if profit_pct > 0.003 and rsi < 25 and tracker.num_entries == 1:
                additional_capital = self.Portfolio.TotalPortfolioValue * 0.3
                self.SetHoldings(self.tqqq, 0.3, add_to_holdings=True)
                tracker.add_entry(price, self.Portfolio[self.tqqq].Quantity, self.Time)
                self.Log(f"TQQQ Entry 2: Price={price}, Profit={profit_pct:.2%}")
            
            # Third entry: RSI extreme oversold
            elif rsi < 20 and tracker.num_entries == 2:
                self.SetHoldings(self.tqqq, 0.2, add_to_holdings=True)
                tracker.add_entry(price, self.Portfolio[self.tqqq].Quantity, self.Time)
                self.Log(f"TQQQ Entry 3: Price={price}, RSI={rsi}")
        
        # EXIT LOGIC
        if current_position > 0:
            profit_pct = tracker.calculate_profit(price)
            
            # Take profit: RSI overbought OR price above VWAP
            if rsi > 70 or price > vwap * 1.01:
                self.Liquidate(self.tqqq)
                self.Log(f"TQQQ Exit: Price={price}, Profit={profit_pct:.2%}")
                tracker.reset()
            
            # Stop loss: -2% loss
            elif profit_pct < -0.02:
                self.Liquidate(self.tqqq)
                self.Log(f"TQQQ Stop Loss: Loss={profit_pct:.2%}")
                tracker.reset()
    
    def OnSQQQBar(self, bar):
        """Process 5-min SQQQ bar (similar logic, inverse direction)"""
        # Mirror logic for SQQQ when QQQ is in downtrend
        pass
    
    def CloseAllPositions(self):
        """Close all positions at 3:50 PM EST"""
        self.Liquidate()
        self.Log("Daily close: All positions liquidated at 3:50 PM")
        
        # Reset trackers
        for tracker in self.position_tracker.values():
            tracker.reset()
    
    def OnOrderEvent(self, orderEvent):
        """Save order fills to SQL Server"""
        if orderEvent.Status == OrderStatus.Filled:
            self.save_order_to_sql(orderEvent)
    
    def save_order_to_sql(self, order):
        """Insert order into SQL Server"""
        cursor = self.sql_conn.cursor()
        cursor.execute("""
            INSERT INTO Orders (
                Symbol, Quantity, Price, Direction, Timestamp, OrderId
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            str(order.Symbol),
            order.FillQuantity,
            order.FillPrice,
            "BUY" if order.Quantity > 0 else "SELL",
            order.Time,
            str(order.OrderId)
        ))
        self.sql_conn.commit()


class PositionTracker:
    """Track multi-level pyramid entries"""
    def __init__(self):
        self.entries = []  # [(price, quantity, timestamp), ...]
        self.num_entries = 0
    
    def add_entry(self, price, quantity, timestamp):
        self.entries.append((price, quantity, timestamp))
        self.num_entries += 1
    
    def calculate_profit(self, current_price):
        if not self.entries:
            return 0.0
        avg_price = sum(p * q for p, q, _ in self.entries) / sum(q for _, q, _ in self.entries)
        return (current_price - avg_price) / avg_price
    
    def reset(self):
        self.entries = []
        self.num_entries = 0
```

---

### Component 2: SQL Server Schema

**File:** `create_schema.sql`

```sql
-- Trading Database Schema for TQQQ/SQQQ System

-- Orders Table
CREATE TABLE Orders (
    OrderId VARCHAR(100) PRIMARY KEY,
    Symbol VARCHAR(10) NOT NULL,
    Quantity DECIMAL(18, 8) NOT NULL,
    Price DECIMAL(18, 4) NOT NULL,
    Direction VARCHAR(10) NOT NULL,  -- BUY, SELL
    Timestamp DATETIME2 NOT NULL,
    FillStatus VARCHAR(20),
    INDEX IX_Orders_Timestamp (Timestamp DESC),
    INDEX IX_Orders_Symbol (Symbol)
);

-- Trades Table (closed positions)
CREATE TABLE Trades (
    TradeId INT IDENTITY(1,1) PRIMARY KEY,
    Symbol VARCHAR(10) NOT NULL,
    EntryTime DATETIME2 NOT NULL,
    ExitTime DATETIME2,
    EntryPrice DECIMAL(18, 4) NOT NULL,
    ExitPrice DECIMAL(18, 4),
    Quantity DECIMAL(18, 8) NOT NULL,
    PnL DECIMAL(18, 4),
    PnLPercent DECIMAL(10, 4),
    Direction VARCHAR(10),  -- LONG, SHORT
    NumEntries INT,  -- Pyramid levels used
    INDEX IX_Trades_ExitTime (ExitTime DESC)
);

-- Position Entries (for pyramiding tracking)
CREATE TABLE PositionEntries (
    EntryId INT IDENTITY(1,1) PRIMARY KEY,
    TradeId INT FOREIGN KEY REFERENCES Trades(TradeId),
    EntryLevel INT NOT NULL,  -- 1, 2, 3
    Quantity DECIMAL(18, 8) NOT NULL,
    Price DECIMAL(18, 4) NOT NULL,
    Timestamp DATETIME2 NOT NULL
);

-- Daily Performance
CREATE TABLE DailyPerformance (
    Date DATE PRIMARY KEY,
    StartingEquity DECIMAL(18, 4),
    EndingEquity DECIMAL(18, 4),
    DailyPnL DECIMAL(18, 4),
    DailyPnLPercent DECIMAL(10, 4),
    NumTrades INT,
    WinningTrades INT,
    LosingTrades INT,
    MaxDrawdown DECIMAL(10, 4)
);

-- Strategy Parameters (for hot-reload)
CREATE TABLE StrategyParameters (
    ParamId INT IDENTITY(1,1) PRIMARY KEY,
    ParamName VARCHAR(50) NOT NULL UNIQUE,
    ParamValue VARCHAR(100) NOT NULL,
    LastUpdated DATETIME2 DEFAULT GETDATE(),
    INDEX IX_Parameters_Name (ParamName)
);

-- Insert default parameters
INSERT INTO StrategyParameters (ParamName, ParamValue) VALUES
('rsi_period', '14'),
('rsi_oversold', '30'),
('rsi_overbought', '70'),
('bb_period', '20'),
('bb_std_dev', '2'),
('vwap_period', '5'),
('stop_loss_pct', '0.02'),
('take_profit_pct', '0.015'),
('pyramid_level2_profit', '0.003'),
('position_size_level1', '0.5'),
('position_size_level2', '0.3'),
('position_size_level3', '0.2');

-- Bars Table (optional: store historical bars)
CREATE TABLE Bars (
    BarId BIGINT IDENTITY(1,1) PRIMARY KEY,
    Symbol VARCHAR(10) NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    Open DECIMAL(18, 4),
    High DECIMAL(18, 4),
    Low DECIMAL(18, 4),
    Close DECIMAL(18, 4),
    Volume BIGINT,
    INDEX IX_Bars_Symbol_Time (Symbol, Timestamp DESC)
);

-- Signals Table (store entry/exit signals for analysis)
CREATE TABLE Signals (
    SignalId BIGINT IDENTITY(1,1) PRIMARY KEY,
    Symbol VARCHAR(10) NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    SignalType VARCHAR(20) NOT NULL,  -- ENTRY, EXIT, PYRAMID
    RSI DECIMAL(10, 4),
    Price DECIMAL(18, 4),
    VWAP DECIMAL(18, 4),
    BBUpper DECIMAL(18, 4),
    BBLower DECIMAL(18, 4),
    Volume BIGINT,
    Action VARCHAR(20),  -- BUY, SELL, HOLD
    INDEX IX_Signals_Timestamp (Timestamp DESC)
);

-- Account Snapshots (track equity over time)
CREATE TABLE AccountSnapshots (
    SnapshotId BIGINT IDENTITY(1,1) PRIMARY KEY,
    Timestamp DATETIME2 NOT NULL,
    TotalEquity DECIMAL(18, 4),
    Cash DECIMAL(18, 4),
    PositionValue DECIMAL(18, 4),
    BuyingPower DECIMAL(18, 4),
    UnrealizedPnL DECIMAL(18, 4),
    INDEX IX_Snapshots_Time (Timestamp DESC)
);

-- Audit Log (track all system actions)
CREATE TABLE AuditLog (
    LogId BIGINT IDENTITY(1,1) PRIMARY KEY,
    Timestamp DATETIME2 DEFAULT GETDATE(),
    EventType VARCHAR(50),
    Message NVARCHAR(MAX),
    Severity VARCHAR(20)  -- INFO, WARNING, ERROR
);
```

---

### Component 3: MCP Servers

#### 3A: LEAN-Ops MCP Server (Python)

**Directory:** `lean-ops-mcp/`

```python
# lean-ops-mcp/src/server.py
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import json
import subprocess
import pyodbc

from tools.backtest import run_backtest_impl, get_backtest_results_impl
from tools.deployment import deploy_paper_impl, stop_algorithm_impl
from tools.parameters import update_parameters_impl
from tools.status import get_algorithm_status_impl

server = Server("lean-ops")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="run_backtest",
            description="Execute a backtest using QuantConnect LEAN engine with specified parameters",
            inputSchema={
                "type": "object",
                "properties": {
                    "algorithm_id": {"type": "string", "description": "Algorithm identifier"},
                    "start_date": {"type": "string", "format": "date"},
                    "end_date": {"type": "string", "format": "date"},
                    "params": {
                        "type": "object",
                        "description": "Strategy parameters to override"
                    }
                },
                "required": ["algorithm_id", "start_date", "end_date"]
            }
        ),
        Tool(
            name="get_backtest_results",
            description="Retrieve detailed results from a completed backtest",
            inputSchema={
                "type": "object",
                "properties": {
                    "backtest_id": {"type": "string"}
                },
                "required": ["backtest_id"]
            }
        ),
        Tool(
            name="update_parameters",
            description="Update strategy parameters in SQL (hot-reload)",
            inputSchema={
                "type": "object",
                "properties": {
                    "params": {
                        "type": "object",
                        "description": "Key-value pairs of parameters"
                    }
                },
                "required": ["params"]
            }
        ),
        Tool(
            name="deploy_paper",
            description="Deploy algorithm to Alpaca paper trading",
            inputSchema={
                "type": "object",
                "properties": {
                    "algorithm_id": {"type": "string"}
                },
                "required": ["algorithm_id"]
            }
        ),
        Tool(
            name="stop_algorithm",
            description="Stop running algorithm (emergency or graceful)",
            inputSchema={
                "type": "object",
                "properties": {
                    "algorithm_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "liquidate": {"type": "boolean", "default": False}
                },
                "required": ["algorithm_id"]
            }
        ),
        Tool(
            name="get_algorithm_status",
            description="Get current algorithm status, positions, and P&L",
            inputSchema={
                "type": "object",
                "properties": {
                    "algorithm_id": {"type": "string"}
                },
                "required": ["algorithm_id"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "run_backtest": run_backtest_impl,
        "get_backtest_results": get_backtest_results_impl,
        "update_parameters": update_parameters_impl,
        "deploy_paper": deploy_paper_impl,
        "stop_algorithm": stop_algorithm_impl,
        "get_algorithm_status": get_algorithm_status_impl
    }
    
    if name not in handlers:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    result = await handlers[name](**arguments)
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

---

#### 3B: Trade-Mind MCP Server (Python)

**Directory:** `trade-mind-mcp/`

```python
# trade-mind-mcp/src/server.py
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import json

from tools.trades import get_last_trades_impl
from tools.statistics import calculate_win_rate_impl
from tools.pnl import get_daily_pnl_impl
from tools.regime import detect_market_regime_impl
from tools.learning import suggest_corrections_impl, get_optimal_params_impl

server = Server("trade-mind")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # === Analytics Tools ===
        Tool(
            name="get_last_trades",
            description="Retrieve the last N trades with full details including entry/exit prices, P&L, MAE/MFE",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "default": 20},
                    "symbol": {"type": "string"},
                    "session_id": {"type": "string"}
                },
                "required": ["session_id"]
            }
        ),
        Tool(
            name="calculate_win_rate",
            description="Calculate comprehensive win rate statistics including Sharpe ratio, profit factor, and expectancy",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "start_date": {"type": "string", "format": "date"},
                    "end_date": {"type": "string", "format": "date"}
                },
                "required": ["session_id"]
            }
        ),
        Tool(
            name="get_daily_pnl",
            description="Get daily P&L breakdown with equity curve, drawdown analysis, and volatility metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "days": {"type": "integer", "default": 30}
                },
                "required": ["session_id"]
            }
        ),
        
        # === Learning Tools ===
        Tool(
            name="detect_market_regime",
            description="Classify current market regime: TRENDING, MEAN_REVERTING, or VOLATILE",
            inputSchema={
                "type": "object",
                "properties": {
                    "lookback_days": {"type": "integer", "default": 20}
                }
            }
        ),
        Tool(
            name="suggest_corrections",
            description="Analyze performance and suggest data-backed corrections to improve strategy",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "strategy_id": {"type": "string"}
                },
                "required": ["session_id", "strategy_id"]
            }
        ),
        Tool(
            name="get_optimal_params",
            description="Retrieve historically optimal parameters for the current market regime",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy_id": {"type": "string"},
                    "regime": {"type": "string", "enum": ["TRENDING", "MEAN_REVERTING", "VOLATILE"]}
                },
                "required": ["strategy_id"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "get_last_trades": get_last_trades_impl,
        "calculate_win_rate": calculate_win_rate_impl,
        "get_daily_pnl": get_daily_pnl_impl,
        "detect_market_regime": detect_market_regime_impl,
        "suggest_corrections": suggest_corrections_impl,
        "get_optimal_params": get_optimal_params_impl
    }
    
    if name not in handlers:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    result = await handlers[name](**arguments)
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

---

#### Trade-Mind Core Tool Implementations

```python
# trade-mind-mcp/src/tools/trades.py
from typing import Optional, Dict, Any
import pyodbc

SQL_CONFIG = (
    "DRIVER={SQL Server};"
    "SERVER=localhost;"
    "DATABASE=TradingDB;"
    "Trusted_Connection=yes;"
)

async def get_last_trades_impl(
    session_id: str,
    count: int = 20,
    symbol: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve the last N trades with comprehensive details."""
    conn = pyodbc.connect(SQL_CONFIG)
    cursor = conn.cursor()
    
    query = """
        SELECT TOP (?) 
            t.TradeId, t.Symbol, t.Direction,
            t.EntryTime, t.EntryPrice, 
            t.ExitTime, t.ExitPrice,
            t.Quantity, t.PnL, t.PnLPercent, t.NumEntries,
            -- Calculate MAE/MFE from price extremes
            (SELECT MIN(Low) FROM Bars b WHERE b.Symbol = t.Symbol 
             AND b.Timestamp BETWEEN t.EntryTime AND t.ExitTime) as MAE_Price,
            (SELECT MAX(High) FROM Bars b WHERE b.Symbol = t.Symbol 
             AND b.Timestamp BETWEEN t.EntryTime AND t.ExitTime) as MFE_Price
        FROM Trades t
        WHERE t.ExitTime IS NOT NULL
        AND (? IS NULL OR t.Symbol = ?)
        ORDER BY t.ExitTime DESC
    """
    
    cursor.execute(query, (count, symbol, symbol))
    rows = cursor.fetchall()
    
    trades = []
    wins = 0
    total_pnl = 0
    
    for row in rows:
        pnl = float(row.PnL or 0)
        is_win = pnl > 0
        if is_win:
            wins += 1
        total_pnl += pnl
        
        trades.append({
            "trade_id": row.TradeId,
            "symbol": row.Symbol,
            "direction": row.Direction,
            "entry_time": row.EntryTime.isoformat() if row.EntryTime else None,
            "entry_price": float(row.EntryPrice),
            "exit_time": row.ExitTime.isoformat() if row.ExitTime else None,
            "exit_price": float(row.ExitPrice) if row.ExitPrice else None,
            "quantity": float(row.Quantity),
            "pnl": pnl,
            "pnl_percent": float(row.PnLPercent or 0),
            "pyramid_levels": row.NumEntries,
            "is_win": is_win
        })
    
    conn.close()
    
    return {
        "trades": trades,
        "summary": {
            "count": len(trades),
            "wins": wins,
            "losses": len(trades) - wins,
            "total_pnl": total_pnl,
            "recent_win_rate": wins / len(trades) if trades else 0
        }
    }
```

```python
# trade-mind-mcp/src/tools/statistics.py
from typing import Optional, Dict, Any
from decimal import Decimal
import pyodbc
import math

SQL_CONFIG = (
    "DRIVER={SQL Server};"
    "SERVER=localhost;"
    "DATABASE=TradingDB;"
    "Trusted_Connection=yes;"
)

async def calculate_win_rate_impl(
    session_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive trading statistics.
    Returns win rate, profit factor, Sharpe ratio, and interpretation.
    """
    conn = pyodbc.connect(SQL_CONFIG)
    cursor = conn.cursor()
    
    # Build date filter
    date_filter = ""
    params = []
    if start_date:
        date_filter += " AND ExitTime >= ?"
        params.append(start_date)
    if end_date:
        date_filter += " AND ExitTime <= ?"
        params.append(end_date)
    
    # Get all trades
    cursor.execute(f"""
        SELECT PnL, PnLPercent, ExitTime
        FROM Trades
        WHERE ExitTime IS NOT NULL {date_filter}
        ORDER BY ExitTime
    """, params)
    
    trades = cursor.fetchall()
    conn.close()
    
    if not trades:
        return {"error": "No trades found for the specified criteria"}
    
    # Calculate statistics
    pnl_values = [float(t.PnL) for t in trades]
    total_trades = len(trades)
    
    winning_trades = [p for p in pnl_values if p > 0]
    losing_trades = [p for p in pnl_values if p < 0]
    
    total_profit = sum(winning_trades) if winning_trades else 0
    total_loss = abs(sum(losing_trades)) if losing_trades else 0
    
    win_rate = len(winning_trades) / total_trades
    loss_rate = len(losing_trades) / total_trades
    
    # Profit factor
    profit_factor = total_profit / total_loss if total_loss > 0 else 10.0
    
    # Averages
    avg_win = total_profit / len(winning_trades) if winning_trades else 0
    avg_loss = total_loss / len(losing_trades) if losing_trades else 0
    avg_pnl = sum(pnl_values) / total_trades
    
    # Sharpe ratio (simplified daily)
    if len(pnl_values) > 1:
        mean = sum(pnl_values) / len(pnl_values)
        variance = sum((x - mean) ** 2 for x in pnl_values) / (len(pnl_values) - 1)
        std_dev = math.sqrt(variance)
        sharpe_ratio = (mean / std_dev) * math.sqrt(252) if std_dev > 0 else 0
    else:
        sharpe_ratio = 0
    
    # Expectancy
    expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
    
    # Max drawdown
    cumulative = 0
    peak = 0
    max_drawdown = 0
    for pnl in pnl_values:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        drawdown = (peak - cumulative) / peak * 100 if peak > 0 else 0
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    return {
        "session_id": session_id,
        "period": {
            "start": trades[0].ExitTime.isoformat() if trades else None,
            "end": trades[-1].ExitTime.isoformat() if trades else None,
            "total_trades": total_trades
        },
        "win_rate": {
            "value": win_rate,
            "percentage": f"{win_rate * 100:.2f}%",
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades)
        },
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "expectancy": round(expectancy, 2),
        "max_drawdown": round(max_drawdown, 2),
        "totals": {
            "net_pnl": round(sum(pnl_values), 2),
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "average_win": round(avg_win, 2),
            "average_loss": round(avg_loss, 2)
        },
        "interpretation": _interpret_statistics(win_rate, profit_factor, sharpe_ratio, expectancy, max_drawdown)
    }

def _interpret_statistics(win_rate, pf, sharpe, expectancy, max_dd):
    """Generate actionable interpretation"""
    interp = {}
    
    # Win rate
    if win_rate >= 0.55:
        interp["win_rate"] = "✅ Strong win rate. Entry timing is effective."
    elif win_rate >= 0.45:
        interp["win_rate"] = "⚠️ Acceptable. Monitor for improvement opportunities."
    else:
        interp["win_rate"] = "❌ Low win rate. Review entry criteria."
    
    # Profit factor
    if pf >= 2.0:
        interp["profit_factor"] = "✅ Excellent. Winners significantly outweigh losers."
    elif pf >= 1.5:
        interp["profit_factor"] = "✅ Good edge present."
    elif pf >= 1.0:
        interp["profit_factor"] = "⚠️ Marginal edge. Room for improvement."
    else:
        interp["profit_factor"] = "❌ Negative edge. Strategy needs revision."
    
    # Sharpe
    if sharpe >= 2.0:
        interp["sharpe"] = "✅ Excellent risk-adjusted returns."
    elif sharpe >= 1.0:
        interp["sharpe"] = "✅ Good risk-adjusted returns."
    else:
        interp["sharpe"] = "⚠️ Low Sharpe. Consider volatility reduction."
    
    # Overall
    if expectancy > 0 and pf > 1.5 and sharpe > 1.0 and max_dd < 15:
        interp["overall"] = "🟢 CONTINUE: Strong quantitative edge."
    elif expectancy > 0:
        interp["overall"] = "🟡 MONITOR: Positive expectancy but needs optimization."
    else:
        interp["overall"] = "🔴 REVISE: Negative expectancy detected."
    
    return interp
```

```python
# trade-mind-mcp/src/tools/pnl.py
from typing import Optional, Dict, Any
import pyodbc
from datetime import datetime, timedelta

SQL_CONFIG = (
    "DRIVER={SQL Server};"
    "SERVER=localhost;"
    "DATABASE=TradingDB;"
    "Trusted_Connection=yes;"
)

async def get_daily_pnl_impl(
    session_id: str,
    days: int = 30
) -> Dict[str, Any]:
    """Get daily P&L breakdown with equity curve and drawdown analysis."""
    conn = pyodbc.connect(SQL_CONFIG)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT TOP (?)
            Date, StartingEquity, EndingEquity,
            DailyPnL, DailyPnLPercent, 
            NumTrades, WinningTrades, LosingTrades,
            MaxDrawdown
        FROM DailyPerformance
        ORDER BY Date DESC
    """, (days,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"error": "No daily performance data found"}
    
    daily_returns = []
    positive_days = 0
    negative_days = 0
    total_pnl = 0
    best_day = float('-inf')
    worst_day = float('inf')
    
    for row in rows:
        pnl = float(row.DailyPnL or 0)
        total_pnl += pnl
        
        if pnl > 0:
            positive_days += 1
        elif pnl < 0:
            negative_days += 1
        
        if pnl > best_day:
            best_day = pnl
        if pnl < worst_day:
            worst_day = pnl
        
        daily_returns.append({
            "date": row.Date.strftime("%Y-%m-%d"),
            "pnl": pnl,
            "pnl_percent": float(row.DailyPnLPercent or 0),
            "equity": float(row.EndingEquity or 0),
            "trades": row.NumTrades,
            "wins": row.WinningTrades,
            "losses": row.LosingTrades
        })
    
    # Reverse for chronological order in response
    daily_returns.reverse()
    
    # Calculate volatility
    pnl_values = [d["pnl"] for d in daily_returns]
    avg_daily = sum(pnl_values) / len(pnl_values) if pnl_values else 0
    
    if len(pnl_values) > 1:
        variance = sum((x - avg_daily) ** 2 for x in pnl_values) / (len(pnl_values) - 1)
        volatility = variance ** 0.5
    else:
        volatility = 0
    
    return {
        "session_id": session_id,
        "period": {
            "days_analyzed": len(daily_returns),
            "start": daily_returns[0]["date"] if daily_returns else None,
            "end": daily_returns[-1]["date"] if daily_returns else None
        },
        "summary": {
            "total_pnl": round(total_pnl, 2),
            "positive_days": positive_days,
            "negative_days": negative_days,
            "win_day_rate": positive_days / len(daily_returns) if daily_returns else 0,
            "best_day": round(best_day, 2) if best_day != float('-inf') else 0,
            "worst_day": round(worst_day, 2) if worst_day != float('inf') else 0,
            "average_daily_pnl": round(avg_daily, 2),
            "daily_volatility": round(volatility, 2)
        },
        "daily_returns": daily_returns[-14:],  # Last 2 weeks for brevity
        "agent_insights": _generate_pnl_insights({
            "total_pnl": total_pnl,
            "win_day_rate": positive_days / len(daily_returns) if daily_returns else 0,
            "volatility": volatility,
            "worst_day": worst_day if worst_day != float('inf') else 0
        })
    }

def _generate_pnl_insights(summary: Dict) -> Dict[str, Any]:
    """Generate actionable insights for the agent"""
    insights = {
        "risk_level": "NORMAL",
        "recommendations": []
    }
    
    if summary["win_day_rate"] < 0.4:
        insights["risk_level"] = "ELEVATED"
        insights["recommendations"].append({
            "action": "REVIEW_DAILY_PATTERNS",
            "reason": f"Only {summary['win_day_rate']*100:.0f}% profitable days"
        })
    
    if summary["volatility"] > abs(summary["total_pnl"] / 10):
        insights["recommendations"].append({
            "action": "REDUCE_POSITION_SIZE",
            "reason": "High volatility relative to returns"
        })
    
    if summary["worst_day"] < -1000:  # Configurable threshold
        insights["risk_level"] = "HIGH"
        insights["recommendations"].append({
            "action": "TIGHTEN_STOP_LOSS",
            "reason": f"Large single-day loss of ${abs(summary['worst_day']):.0f}"
        })
    
    if not insights["recommendations"]:
        insights["recommendations"].append({
            "action": "CONTINUE",
            "reason": "Daily P&L metrics within acceptable ranges"
        })
    
    return insights
```
---

### Component 4: Streamlit Dashboard (Python)

**File:** `dashboard/app.py`

```python
import streamlit as st
import pandas as pd
import pyodbc
import plotly.graph_objects as go
from datetime import datetime, timedelta

# SQL connection
@st.cache_resource
def get_connection():
    return pyodbc.connect(
        "DRIVER={SQL Server};"
        "SERVER=localhost;"
        "DATABASE=TradingDB;"
        "Trusted_Connection=yes;"
    )

conn = get_connection()

st.title("🚀 TQQQ/SQQQ Scalping Bot Dashboard")

# Sidebar controls
st.sidebar.header("Bot Controls")
if st.sidebar.button("▶️ Start Bot", type="primary"):
    st.sidebar.success("Bot started!")
    # TODO: Trigger LEAN algorithm start

if st.sidebar.button("⏸️ Pause Bot"):
    st.sidebar.warning("Bot paused")

if st.sidebar.button("🛑 EMERGENCY STOP", type="primary"):
    st.sidebar.error("EMERGENCY STOP ACTIVATED")
    # TODO: Call Liquidate() API

st.sidebar.divider()

# Parameter controls
st.sidebar.header("Strategy Parameters")
rsi_oversold = st.sidebar.slider("RSI Oversold", 20, 40, 30)
rsi_overbought = st.sidebar.slider("RSI Overbought", 60, 80, 70)
stop_loss = st.sidebar.slider("Stop Loss %", 1.0, 5.0, 2.0)

if st.sidebar.button("Update Parameters"):
    cursor = conn.cursor()
    cursor.execute("UPDATE StrategyParameters SET ParamValue=? WHERE ParamName='rsi_oversold'", (rsi_oversold,))
    cursor.execute("UPDATE StrategyParameters SET ParamValue=? WHERE ParamName='rsi_overbought'", (rsi_overbought,))
    cursor.execute("UPDATE StrategyParameters SET ParamValue=? WHERE ParamName='stop_loss_pct'", (stop_loss/100,))
    conn.commit()
    st.sidebar.success("Parameters updated!")

# Main dashboard
col1, col2, col3, col4 = st.columns(4)

# Fetch metrics
cursor = conn.cursor()
cursor.execute("SELECT TOP 1 * FROM DailyPerformance ORDER BY Date DESC")
today = cursor.fetchone()

cursor.execute("SELECT SUM(PnL) FROM Trades WHERE ExitTime >= CAST(GETDATE() AS DATE)")
daily_pnl = cursor.fetchone()[0] or 0

cursor.execute("SELECT TOP 1 TotalEquity FROM AccountSnapshots ORDER BY Timestamp DESC")
total_equity = cursor.fetchone()[0] or 100000

cursor.execute("SELECT COUNT(*) FROM Trades WHERE ExitTime >= CAST(GETDATE() AS DATE)")
trades_today = cursor.fetchone()[0] or 0

with col1:
    st.metric("Total Equity", f"${total_equity:,.2f}", delta=f"{daily_pnl:+,.2f}")

with col2:
    win_rate = (today[6] / today[5] * 100) if today and today[5] > 0 else 0
    st.metric("Win Rate", f"{win_rate:.1f}%")

with col3:
    st.metric("Trades Today", trades_today)

with col4:
    st.metric("Daily P&L", f"${daily_pnl:,.2f}", delta=f"{(daily_pnl/total_equity*100):.2f}%")

# Equity curve
st.subheader("📈 Equity Curve")
df_equity = pd.read_sql("SELECT Timestamp, TotalEquity FROM AccountSnapshots ORDER BY Timestamp", conn)
if not df_equity.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_equity['Timestamp'], y=df_equity['TotalEquity'], mode='lines', name='Equity'))
    st.plotly_chart(fig, use_container_width=True)

# Recent trades table
st.subheader("📋 Recent Trades")
df_trades = pd.read_sql("""
    SELECT TOP 20 
        Symbol, EntryTime, ExitTime, 
        EntryPrice, ExitPrice, Quantity, 
        PnL, PnLPercent, NumEntries
    FROM Trades 
    ORDER BY ExitTime DESC
""", conn)
st.dataframe(df_trades, use_container_width=True)

# Daily performance
st.subheader("📊 Daily Performance")
df_daily = pd.read_sql("""
    SELECT TOP 30 
        Date, DailyPnL, DailyPnLPercent, 
        NumTrades, WinningTrades, LosingTrades
    FROM DailyPerformance 
    ORDER BY Date DESC
""", conn)
st.dataframe(df_daily, use_container_width=True)
```

---

## Technology Stack

### Core Framework
- **QuantConnect LEAN Engine** (C#/.NET) - Execution engine
- **Python 3.10+** - Algorithm development language
- **Alpaca API** - Brokerage (paper & live trading)

### Data & Persistence
- **SQL Server 2019+** (LocalDB acceptable) - Database
- **pyodbc** - Python SQL driver
- **QuantConnect Data** - Historical market data (free via Alpaca)

### Analytics & Control
- **TypeScript 5.0+** - MCP Server language
- **@modelcontextprotocol/sdk** - MCP protocol SDK
- **mssql (npm)** - SQL Server Node.js driver
- **Streamlit 1.30+** - Dashboard framework
- **plotly** - Interactive charts

### Deployment
- **Docker Compose** - Service orchestration
- **Windows Server / Windows 10+** - Hosting OS
- **Git** - Version control

### Development Tools
- **VS Code** - IDE
- **Pylance** - Python language server
- **SQL Server Management Studio** - Database management
- **Postman** - API testing

---

## Development Roadmap

### Phase 1: Foundation (Days 1-8)

**Week 1: Days 1-3 — Strategy Core (#1)** ✅ COMPLETED
- ✅ Set up QuantConnect LEAN environment (Docker or local)
- ✅ Create `TQQQScalpingAlgorithm.py` skeleton
- ✅ Implement RSI + VWAP + Bollinger Bands indicators
- ✅ Add QQQ EMA trend filter
- ✅ Implement entry logic (first entry at 50% capital)
- ✅ Implement pyramiding logic (PositionTracker class)
- ✅ Implement exit logic (take profit + stop loss)
- ✅ Add intraday schedule (3:50 PM close)

**Files Created:**
- `Algorithm.Python/TQQQScalpingAlgorithm.py` - Main algorithm
- `Algorithm.Python/tqqq_config.json` - Configuration
- `Algorithm.Python/TQQQ_STRATEGY_README.md` - Documentation

**Week 1: Day 4 — SQL Schema (#2)**
- ✅ Design SQL schema (`create_schema.sql`)
- ✅ Create database: `CREATE DATABASE TradingDB`
- ✅ Run schema scripts (Orders, Trades, PositionEntries, etc.)
- ✅ Create learning tables (`create_learning_tables.sql`):
  - `BacktestResults` - Store all backtest outcomes
  - `ParameterCorrelations` - Parameter → Performance mappings
  - `MarketRegimes` - Regime classifications
  - `LearningPatterns` - Discovered patterns

**Week 1: Days 5-6 — Backtest Pipeline (#3)**
- ✅ Configure LEAN backtest settings
- ✅ Run first backtest on 2023 data
- ✅ Refine entry/exit rules based on results
- ✅ Optimize parameters (RSI thresholds, profit targets)
- ✅ Run full 2020-2024 backtest
- ✅ Document baseline results (Sharpe, win rate, drawdown)

**Week 2: Days 7-8 — SQL Connector (#4)**
- ✅ Add `OnOrderEvent()` callback to algorithm
- ✅ Implement `save_order_to_sql()` method
- ✅ Add daily performance snapshot logic
- ✅ Add signal logging (RSI, VWAP values at decision points)
- ✅ Test database writes during backtest
- ✅ Validate data integrity (check trades match orders)

**Phase 1 Deliverable:** Working Python algorithm with SQL persistence, validated via backtest

---

### Phase 2: Core MCP Servers (Days 9-16)

**Week 2: Days 9-11 — LEAN-Ops MCP Server (#5)**
- ⏳ Create `lean-ops-mcp/` directory structure
- ⏳ Initialize Python project (`pyproject.toml`)
- ⏳ Install dependencies: `mcp`, `pyodbc`, `subprocess`
- ⏳ Implement core tools:
  ```
  ├── run_backtest        → Execute LEAN backtest
  ├── get_backtest_results → Retrieve statistics
  ├── update_parameters   → Hot-reload params in SQL
  ├── deploy_paper        → Start paper trading
  ├── stop_algorithm      → Emergency stop
  └── get_algorithm_status → Current state
  ```
- ⏳ Implement LEAN adapter (subprocess or API calls)
- ⏳ Test with Claude Desktop

**Week 2-3: Days 12-14 — Trade-Mind MCP Server (#6)**
- ⏳ Create `trade-mind-mcp/` directory structure
- ⏳ Initialize Python project
- ⏳ Implement analytics tools:
  ```
  ├── get_last_trades      → Recent trade history
  ├── calculate_win_rate   → Win rate + Sharpe + PF
  └── get_daily_pnl        → Daily P&L breakdown
  ```
- ⏳ Implement learning tools:
  ```
  ├── detect_market_regime → Trending/MeanReverting/Volatile
  ├── suggest_corrections  → AI-driven improvements
  └── get_optimal_params   → Best params for regime
  ```
- ⏳ Create SQL adapter for querying trade data
- ⏳ Test MCP server with Claude Desktop
- ⏳ Verify queries return correct data

**Week 3: Days 15-16 — Streamlit Dashboard (#7)**
- ⏳ Create `dashboard/app.py`
- ⏳ Install Streamlit: `pip install streamlit plotly pyodbc`
- ⏳ Build UI components:
  - Equity curve chart (real-time updates)
  - Recent trades table
  - Daily performance metrics
  - Current position display
  - Strategy parameters display
  - Control buttons (Start/Stop/Emergency)
- ⏳ Connect to SQL Server
- ⏳ Test parameter hot-reload (update SQL → algorithm reads)

**Phase 2 Deliverable:** Both MCP servers operational, Dashboard showing real-time data

---

### Phase 3: Intelligence Layer (Days 17-23)

**Week 3: Days 17-18 — Learning Store (#8)**
- ⏳ Design learning schema:
  ```sql
  BacktestOutcomes (
    outcome_id, strategy_id, params_json, 
    sharpe, win_rate, max_drawdown, profit_factor,
    market_regime, start_date, end_date, timestamp
  )
  
  ParameterPerformance (
    param_name, param_value, regime,
    avg_sharpe, avg_win_rate, sample_count
  )
  
  CorrectionHistory (
    correction_id, session_id, correction_type,
    before_metrics, after_metrics, was_effective
  )
  ```
- ⏳ Implement `LearningStore` class in Trade-Mind MCP
- ⏳ Add methods:
  - `record_backtest_outcome()`
  - `get_best_params_for_regime()`
  - `find_similar_patterns()`
- ⏳ Backfill with initial backtest results

**Week 3-4: Days 19-20 — Adaptive Agent Logic (#9)**
- ⏳ Implement performance grading (A-F scale)
- ⏳ Create correction triggers:
  ```python
  CORRECTION_TRIGGERS = {
    "win_rate < 0.40": {
      "action": "tighten_entry",
      "priority": "HIGH"
    },
    "profit_factor < 1.0": {
      "action": "review_exits",
      "priority": "CRITICAL"
    },
    "max_drawdown > 15%": {
      "action": "reduce_position_size",
      "priority": "CRITICAL"
    },
    "sharpe < 0.5": {
      "action": "regime_check",
      "priority": "MEDIUM"
    }
  }
  ```
- ⏳ Implement `suggest_corrections` with data-backed reasoning
- ⏳ Add correction application flow (via LEAN-Ops MCP)
- ⏳ Create feedback loop (record correction outcomes)

**Week 4: Days 21-23 — Integration Testing (#10)**
- ⏳ End-to-end test: Strategy → SQL → MCP → Dashboard
- ⏳ Test learning loop:
  1. Run backtest with params A
  2. Query Trade-Mind for suggestions
  3. Apply corrections via LEAN-Ops
  4. Run backtest with params B
  5. Verify improvement recorded
- ⏳ Paper trading validation (1-2 days minimum)
- ⏳ Verify:
  - Orders execute correctly
  - SQL database updates in real-time
  - MCP queries work
  - Pyramiding adds correctly
  - 3:50 PM close triggers
  - Learning store records patterns
- ⏳ Fix any bugs discovered

**Phase 3 Deliverable:** Fully operational adaptive trading system

---

### Phase 4: Production Deployment (Day 24+)

**Week 4+: Paper Trading Period**
- ⏳ Run paper trading for minimum 30 days
- ⏳ Monitor via Dashboard daily
- ⏳ Use Claude + MCP for weekly reviews:
  - "What's my win rate this week?"
  - "Suggest corrections based on performance"
  - "What regime is the market in?"
- ⏳ Let learning store accumulate patterns
- ⏳ Review agent suggestions before applying

**Post 30-Day Paper Trading**
- ⏳ Review paper trading results (win rate, drawdown, consistency)
- ⏳ If profitable: Switch to live Alpaca account (real money)
- ⏳ Start with small capital ($1,000-$5,000)
- ⏳ Monitor closely for first week
- ⏳ Scale up capital gradually if performance holds

**Deliverable:** System trading live with real capital, continuously learning

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Alpaca API downtime** | Medium | High | Implement retry logic, fallback to manual trading |
| **SQL Server connection loss** | Low | Medium | Queue writes in memory, persist on reconnect |
| **QuantConnect bugs** | Low | Medium | Use stable release (not latest), test extensively |
| **Parameter hot-reload issues** | Medium | Low | Add validation checks before applying new params |
| **Market hours enforcement failure** | Low | Critical | Double-check with Alpaca API market status |

### Trading Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Flash crash losses** | Low | Critical | Stop loss at -2%, max position size 10% |
| **Slippage exceeds model** | Medium | Medium | Use limit orders instead of market orders |
| **Over-trading (commission drain)** | Medium | High | Max 10 trades/day, min profit target 1.5% |
| **Pyramiding magnifies losses** | Medium | High | Stop loss applies to entire position, not per entry |
| **Gap down at open** | Low | High | No overnight positions (intraday only) |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Developer error in strategy** | Medium | Critical | Extensive backtesting, paper trading 30+ days |
| **SQL Server disk full** | Low | Medium | Monitor disk usage, auto-archive old data |
| **Dashboard shows stale data** | Low | Low | Add "Last Updated" timestamp, refresh button |
| **MCP server crashes** | Medium | Low | Analytics only, doesn't affect trading |

---

## Next Steps

### Immediate Actions (This Week)

1. ✅ **Set up QuantConnect LEAN locally**
   ```bash
   cd c:\Users\anand\Documents\trading_plan\quantconnect-lean
   # Follow Docker setup or local build instructions
   ```

2. ✅ **Create algorithm skeleton**
   - File: `Algorithm.Python/TQQQScalpingAlgorithm.py`
   - Copy template from Component 1 section above

3. ✅ **Run first backtest**
   ```bash
   lean backtest "TQQQScalpingAlgorithm"
   ```

4. ✅ **Set up SQL Server database**
   - Create `TradingDB` database
   - Run `create_schema.sql` script

### Next Week

5. ⏳ **Implement pyramiding logic**
6. ⏳ **Add SQL persistence**
7. ⏳ **Build MCP server**
8. ⏳ **Create Streamlit dashboard**

### Month 1 Goal

- **Working system in paper trading mode** with:
  - Profitable backtest results (Sharpe > 1.5, win rate > 55%)
  - Live execution on Alpaca paper account
  - Real-time dashboard monitoring
  - Natural language analytics via MCP

---

## Appendix: Key Configuration Files

### config.json (QuantConnect)

```json
{
  "algorithm-type-name": "TQQQScalpingAlgorithm",
  "algorithm-language": "Python",
  "algorithm-location": "Algorithm.Python/TQQQScalpingAlgorithm.py",
  
  "live-mode": false,
  "live-mode-brokerage": "AlpacaBrokerage",
  
  "alpaca-key-id": "YOUR_ALPACA_KEY",
  "alpaca-secret-key": "YOUR_ALPACA_SECRET",
  "alpaca-paper-trading": true,
  
  "data-folder": "./Data",
  "results-destination-folder": "./Results",
  
  "log-handler": "ConsoleLogHandler",
  "messaging-handler": "StreamingMessageHandler",
  
  "close-automatically": true
}
```

### docker-compose.yml (Deployment)

```yaml
version: '3.8'

services:
  lean-engine:
    image: quantconnect/lean:latest
    volumes:
      - ./Algorithm.Python:/Lean/Algorithm.Python
      - ./config.json:/Lean/config.json
      - ./Data:/Lean/Data
    environment:
      - ALPACA_KEY_ID=${ALPACA_KEY}
      - ALPACA_SECRET_KEY=${ALPACA_SECRET}
    restart: unless-stopped

  sqlserver:
    image: mcr.microsoft.com/mssql/server:2019-latest
    environment:
      - ACCEPT_EULA=Y
      - SA_PASSWORD=YourStrong@Password
    volumes:
      - sqldata:/var/opt/mssql
    ports:
      - "1433:1433"

  lean-ops-mcp:
    build: ./lean-ops-mcp
    depends_on:
      - sqlserver
      - lean-engine
    environment:
      - SQL_SERVER=sqlserver
      - SQL_DATABASE=TradingDB
      - LEAN_API_URL=http://lean-engine:5000
    stdin_open: true
    tty: true

  trade-mind-mcp:
    build: ./trade-mind-mcp
    depends_on:
      - sqlserver
    environment:
      - SQL_SERVER=sqlserver
      - SQL_DATABASE=TradingDB
    stdin_open: true
    tty: true

  dashboard:
    build: ./dashboard
    depends_on:
      - sqlserver
    ports:
      - "8501:8501"
    environment:
      - SQL_SERVER=sqlserver

volumes:
  sqldata:
```

---

## Summary

### Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                    ADAPTIVE TRADING SYSTEM                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────┐                                                │
│  │   AI Agent     │  "What's my win rate? Suggest corrections."   │
│  │   (Claude)     │                                                │
│  └───────┬────────┘                                                │
│          │                                                         │
│    ┌─────┴─────┐                                                   │
│    ▼           ▼                                                   │
│ ┌──────────┐ ┌──────────┐                                          │
│ │LEAN-Ops  │ │Trade-Mind│  ◀── Two specialized MCP servers        │
│ │   MCP    │ │   MCP    │                                          │
│ │(Operate) │ │ (Learn)  │                                          │
│ └────┬─────┘ └────┬─────┘                                          │
│      │            │                                                │
│      │     ┌──────┴──────┐                                         │
│      │     │             │                                         │
│      ▼     ▼             ▼                                         │
│ ┌─────────────┐   ┌─────────────┐                                  │
│ │    LEAN     │   │ SQL Server  │                                  │
│ │   Engine    │──▶│  (Central   │◀── Dashboard reads from here    │
│ │             │   │    Hub)     │                                  │
│ └──────┬──────┘   └─────────────┘                                  │
│        │                                                           │
│        ▼                                                           │
│ ┌─────────────┐                                                    │
│ │   Alpaca    │  ◀── Paper or Live trading                        │
│ │   API       │                                                    │
│ └─────────────┘                                                    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### MCP Server Summary

| Server | Name | Purpose | Key Tools |
|--------|------|---------|-----------|
| **MCP Server 1** | `lean-ops-mcp` | Algorithm Operations | `run_backtest`, `deploy_paper`, `stop_algorithm`, `update_parameters` |
| **MCP Server 2** | `trade-mind-mcp` | Analytics & Learning | `get_last_trades`, `calculate_win_rate`, `get_daily_pnl`, `suggest_corrections` |

### What QuantConnect LEAN Provides (70%+)
- ✅ Alpaca integration (native)
- ✅ Backtesting engine (production-grade)
- ✅ Indicators (RSI, VWAP, BB built-in)
- ✅ Order management (SetHoldings, Liquidate)
- ✅ Scheduling (3:50 PM close)
- ✅ Market hours enforcement

### Custom Development Required

| Component | Effort | Description |
|-----------|--------|-------------|
| 🔧 Pyramiding logic | 2 days | Multi-level position tracking |
| 🔧 SQL Server persistence | 2 days | Trade/order/signal logging |
| 🔧 **LEAN-Ops MCP** | 3 days | Algorithm operation tools |
| 🔧 **Trade-Mind MCP** | 3 days | Analytics + learning tools |
| 🔧 Learning Store | 2 days | Pattern storage for adaptation |
| 🔧 Streamlit Dashboard | 2 days | UI for monitoring & control |
| 🔧 Integration testing | 3 days | End-to-end validation |

**Total estimated time: 4 weeks**

### Build Order Summary

| Phase | Items | Duration |
|-------|-------|----------|
| **1. Foundation** | Strategy Core → SQL Schema → Backtest Pipeline → SQL Connector | Days 1-8 |
| **2. MCP Servers** | LEAN-Ops MCP → Trade-Mind MCP → Dashboard | Days 9-16 |
| **3. Intelligence** | Learning Store → Adaptive Agent → Integration Testing | Days 17-23 |
| **4. Deployment** | Paper Trading (30 days) → Live Trading | Day 24+ |

### Agent Capabilities After Implementation

The AI agent will be able to:

1. **Query Performance:** "What's my win rate this week?"
2. **Analyze Trades:** "Show me my last 10 losing trades"
3. **Get Insights:** "What's the current market regime?"
4. **Receive Suggestions:** "Suggest corrections based on performance"
5. **Execute Changes:** "Run a backtest with RSI oversold at 25"
6. **Deploy:** "Deploy to paper trading"
7. **Emergency Control:** "Stop the algorithm immediately"

**Risk level: Medium** (proven framework + custom extensions)

**Recommendation: ✅ Proceed with dual MCP architecture** - Best balance of operational control and adaptive learning for objective, data-driven trading.

---

**Document Status:** Draft v2.0 - Adaptive Learning Agent Architecture  
**Last Updated:** January 2026  
**Next Review:** After Phase 1 completion  
**Questions/Feedback:** Contact development team
