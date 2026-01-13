# Integration Tests for TQQQ/SQQQ Adaptive Trading System

Comprehensive test suite for validating all system components work together correctly.

## Test Categories

### Unit Tests (`unit/`)
- Individual component tests with mocked dependencies
- Fast execution, no external dependencies

### Integration Tests (`integration/`)
- Tests requiring real database connections
- MCP server integration tests
- Cross-component workflow tests

### End-to-End Tests (`e2e/`)
- Full system workflow validation
- Simulated trading scenarios
- Performance benchmarks

## Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest unit/

# Run only integration tests (requires database)
pytest integration/ -m database

# Run with coverage
pytest --cov=../ --cov-report=html

# Skip slow tests
pytest -m "not slow"

# Run specific test file
pytest integration/test_learning_store.py -v

# Run with verbose output
pytest -v --tb=short
```

## Prerequisites

1. **Database**: SQL Server with TradingDB schema deployed
2. **Environment**: `.env` file with connection strings
3. **Dependencies**: `pip install -e .`

## Test Configuration

Create a `.env.test` file:
```env
DB_SERVER=localhost
DB_NAME=TradingDB_Test
DB_DRIVER=ODBC Driver 17 for SQL Server

# Use test database to avoid affecting production data
TEST_MODE=true
```

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures
├── fixtures/             # Test data and mocks
│   ├── __init__.py
│   ├── market_data.py
│   ├── trade_data.py
│   └── mock_responses.py
├── unit/                 # Unit tests
│   ├── test_models.py
│   ├── test_config.py
│   └── test_utils.py
├── integration/          # Integration tests
│   ├── test_database.py
│   ├── test_learning_store.py
│   ├── test_adaptive_agent.py
│   └── test_mcp_servers.py
└── e2e/                  # End-to-end tests
    ├── test_trading_workflow.py
    └── test_full_cycle.py
```

## Writing Tests

### Naming Convention
- Test files: `test_<component>.py`
- Test functions: `test_<action>_<expected_result>`
- Test classes: `Test<Component><Feature>`

### Example Test
```python
import pytest
from fixtures.market_data import sample_market_snapshot

@pytest.mark.database
async def test_observer_gets_market_data(db_connection):
    """Observer should retrieve current market conditions."""
    from adaptive_agent.observer import Observer
    
    observer = Observer(config)
    snapshot = observer.get_market_snapshot()
    
    assert snapshot is not None
    assert snapshot.tqqq_price > 0
    assert 0 <= snapshot.rsi <= 100
```

## Coverage Goals

| Component | Target Coverage |
|-----------|----------------|
| Models | 90% |
| Config | 85% |
| Observer | 80% |
| Analyzer | 80% |
| Executor | 75% |
| Decision Engine | 80% |
| Learning Store | 80% |
| MCP Servers | 70% |
