# Learning Store - Intelligence Persistence Layer

The Learning Store is the intelligence persistence layer for the TQQQ/SQQQ adaptive trading system. It manages pattern recognition, learning from trades, and adaptive parameter optimization.

## Features

### 🧠 Pattern Recognition
- Trade pattern detection and classification
- Market regime pattern learning
- Entry/exit timing pattern analysis
- Volume and momentum pattern recognition

### 📊 Learning Engine
- Win/loss pattern correlation
- Parameter performance tracking
- Regime-specific optimization
- Continuous learning from new trades

### 💾 Persistence
- SQL Server backed storage
- Versioned learning snapshots
- Pattern confidence scoring
- Historical learning audit trail

### 🎯 Recommendations
- Real-time parameter suggestions
- Regime-aware trading adjustments
- Confidence-weighted recommendations
- A/B testing support for parameters

## Architecture

```
learning-store/
├── src/learning_store/
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── database.py         # SQL Server connection
│   ├── models.py           # Pydantic data models
│   ├── patterns.py         # Pattern recognition engine
│   ├── learner.py          # Learning algorithms
│   ├── recommender.py      # Recommendation engine
│   ├── store.py            # Main store interface
│   └── utils.py            # Utility functions
└── pyproject.toml
```

## Installation

```bash
cd learning-store
pip install -e .
```

## Usage

```python
from learning_store import LearningStore

# Initialize store
store = LearningStore()

# Record a learning from trade data
store.record_pattern(
    pattern_type="ENTRY_TIMING",
    description="RSI oversold bounce in bullish regime",
    parameters={"rsi_threshold": 30, "regime": "BULLISH"},
    confidence=0.85,
    source="backtest_analysis"
)

# Get recommendations for current conditions
recommendations = store.get_recommendations(
    regime="BULLISH",
    rsi=35,
    momentum=0.02
)

# Update learning based on trade outcome
store.update_learning(
    learning_id=123,
    outcome="SUCCESS",
    actual_pnl=150.00
)
```

## Core Components

### Pattern Types
- `ENTRY_TIMING` - When to enter trades
- `EXIT_TIMING` - When to exit trades
- `POSITION_SIZING` - How much to trade
- `REGIME_DETECTION` - Market regime classification
- `RISK_MANAGEMENT` - Stop loss and take profit levels
- `PARAMETER_OPTIMIZATION` - Algorithm parameter tuning

### Confidence Scoring
- 0.0-0.3: Low confidence (needs more data)
- 0.3-0.6: Medium confidence (use with caution)
- 0.6-0.8: High confidence (recommended)
- 0.8-1.0: Very high confidence (validated)

### Learning Loop
1. **Observe**: Collect trade outcomes and market data
2. **Analyze**: Detect patterns in successful/failed trades
3. **Learn**: Update pattern confidence based on outcomes
4. **Recommend**: Suggest parameter adjustments
5. **Validate**: Track recommendation effectiveness
6. **Iterate**: Continuously improve

## Integration

The Learning Store integrates with:
- **Trade-Mind MCP**: Provides learning data to the analytics server
- **LEAN-Ops MCP**: Receives parameter update requests
- **Dashboard**: Visualizes learning progress and recommendations
- **Adaptive Agent**: Powers the agent's decision making

## License

MIT License
