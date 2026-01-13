# Adaptive Trading Agent

The Adaptive Agent is the orchestration layer for the TQQQ/SQQQ adaptive trading system. It coordinates all components to make intelligent, learning-based trading decisions.

## Core Philosophy

> "An agent who acts on quantifiable data and changes the plan at runtime to time the market. It learns based on sentiment, repetitive backtested data and tries to correct itself."

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      ADAPTIVE AGENT                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Observer   │  │   Analyzer   │  │   Executor   │          │
│  │  (Monitor)   │→ │  (Decide)    │→ │  (Act)       │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↓                ↓                 ↓                    │
│  ┌──────────────────────────────────────────────────┐          │
│  │              Decision Engine                      │          │
│  │  • Pattern Matching    • Risk Assessment         │          │
│  │  • Regime Detection    • Parameter Selection     │          │
│  └──────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ LEAN-Ops   │      │ Trade-Mind  │      │  Learning   │
│   MCP      │      │    MCP      │      │   Store     │
└─────────────┘      └─────────────┘      └─────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │    TradingDB    │
                    │   SQL Server    │
                    └─────────────────┘
```

## Features

### 🔄 Continuous Learning Loop
1. **Observe**: Monitor market data, positions, and performance
2. **Analyze**: Use patterns and learnings to assess conditions
3. **Decide**: Generate action recommendations with confidence scores
4. **Execute**: Apply parameter changes or trading signals
5. **Learn**: Record outcomes and update pattern confidence

### 📊 Decision Types
- **PARAMETER_ADJUSTMENT**: Modify algorithm parameters
- **REGIME_ADAPTATION**: Adapt strategy to market regime
- **RISK_SCALING**: Adjust position sizes based on performance
- **TIMING_OPTIMIZATION**: Optimize entry/exit timing
- **EMERGENCY_STOP**: Halt trading during adverse conditions

### 🧠 Intelligence Integration
- Pattern recognition from Learning Store
- Confidence-weighted recommendations
- Regime-aware decision making
- Performance-based self-correction

## Installation

```bash
cd adaptive-agent
pip install -e .
```

## Usage

### As a Service
```bash
# Start the agent
adaptive-agent start

# Start with custom config
adaptive-agent start --config config.yaml

# Run in dry-run mode (no actual execution)
adaptive-agent start --dry-run
```

### Programmatic Usage
```python
from adaptive_agent import AdaptiveAgent, AgentConfig

# Initialize agent
config = AgentConfig(
    mode="paper",  # or "live"
    learning_enabled=True,
    auto_apply_recommendations=False
)
agent = AdaptiveAgent(config)

# Start the agent loop
await agent.start()

# Or run a single decision cycle
decision = await agent.run_cycle()
print(f"Decision: {decision.action} with {decision.confidence:.1%} confidence")
```

## Configuration

```yaml
# config.yaml
agent:
  mode: paper  # paper | live
  cycle_interval_seconds: 60
  learning_enabled: true
  auto_apply_recommendations: false
  
thresholds:
  min_confidence_to_act: 0.7
  max_daily_parameter_changes: 5
  emergency_drawdown_pct: 0.15
  
risk:
  max_position_size_pct: 0.20
  max_daily_loss_pct: 0.05
  
notifications:
  enabled: true
  on_parameter_change: true
  on_emergency_stop: true
```

## Components

### Observer
Monitors:
- Current market conditions (RSI, momentum, volatility)
- Open positions and P&L
- Recent trade performance
- Market regime indicators

### Analyzer  
Processes:
- Pattern matching against current conditions
- Historical performance analysis
- Risk assessment
- Recommendation generation

### Executor
Actions:
- Parameter updates via LEAN-Ops MCP
- Position adjustments
- Emergency stops
- Audit logging

### Decision Engine
Coordinates:
- Multi-factor decision scoring
- Confidence aggregation
- Conflict resolution
- Action prioritization

## Safety Features

1. **Confidence Thresholds**: Only acts on high-confidence decisions
2. **Rate Limiting**: Max parameter changes per day
3. **Drawdown Circuit Breaker**: Emergency stop on excessive losses
4. **Dry-Run Mode**: Test decisions without execution
5. **Audit Trail**: All decisions logged with reasoning
6. **Manual Override**: Human can always intervene

## License

MIT License
