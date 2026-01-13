"""
Shared test fixtures and configuration.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, Optional
from unittest.mock import MagicMock, AsyncMock

import pytest
import pyodbc
from dotenv import load_dotenv

# Add parent directories to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "adaptive-agent" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "learning-store" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "lean-ops" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "trade-mind" / "src"))

# Load test environment
load_dotenv(PROJECT_ROOT / ".env.test")
load_dotenv(PROJECT_ROOT / ".env")


# ============================================
# Database Fixtures
# ============================================

@pytest.fixture(scope="session")
def db_connection_string() -> str:
    """Get database connection string."""
    server = os.getenv("DB_SERVER", "localhost")
    database = os.getenv("DB_NAME", "TradingDB")
    driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"Trusted_Connection=yes"
    )


@pytest.fixture(scope="session")
def db_connection(db_connection_string) -> Generator[pyodbc.Connection, None, None]:
    """Create a database connection for the test session."""
    try:
        conn = pyodbc.connect(db_connection_string, autocommit=True)
        yield conn
        conn.close()
    except pyodbc.Error as e:
        pytest.skip(f"Database connection failed: {e}")


@pytest.fixture
def db_cursor(db_connection) -> Generator[pyodbc.Cursor, None, None]:
    """Create a cursor for individual tests."""
    cursor = db_connection.cursor()
    yield cursor
    cursor.close()


@pytest.fixture
def clean_test_data(db_cursor):
    """Clean up test data before and after tests."""
    # Cleanup before test
    _cleanup_test_data(db_cursor)
    yield
    # Cleanup after test
    _cleanup_test_data(db_cursor)


def _cleanup_test_data(cursor):
    """Remove test data from tables."""
    tables = [
        "AgentDecisions",
        "AgentActions",
        "AgentAlerts",
        "Recommendations",
        "Patterns",
    ]
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table} WHERE CreatedAt > DATEADD(minute, -5, GETDATE())")
        except pyodbc.Error:
            pass  # Table may not exist


# ============================================
# Configuration Fixtures
# ============================================

@pytest.fixture
def agent_config():
    """Create a test configuration for the adaptive agent."""
    from adaptive_agent.config import AgentConfig, DatabaseConfig, ThresholdConfig, RiskConfig
    
    return AgentConfig(
        mode="paper",
        cycle_interval_seconds=5,
        learning_enabled=True,
        auto_apply_recommendations=False,
        dry_run=True,
        debug=True,
        database=DatabaseConfig(
            server=os.getenv("DB_SERVER", "localhost"),
            database=os.getenv("DB_NAME", "TradingDB"),
        ),
        thresholds=ThresholdConfig(
            min_confidence_to_act=0.7,
            max_daily_parameter_changes=10,
            emergency_drawdown_pct=0.15,
        ),
        risk=RiskConfig(
            max_position_size_pct=0.20,
            max_daily_loss_pct=0.05,
        ),
    )


@pytest.fixture
def learning_store_config():
    """Create a test configuration for the learning store."""
    from learning_store.config import LearningStoreConfig
    
    return LearningStoreConfig(
        db_server=os.getenv("DB_SERVER", "localhost"),
        db_name=os.getenv("DB_NAME", "TradingDB"),
        min_pattern_confidence=0.3,
        pattern_decay_days=30,
    )


# ============================================
# Mock Fixtures
# ============================================

@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    mock_conn = MagicMock(spec=pyodbc.Connection)
    mock_cursor = MagicMock(spec=pyodbc.Cursor)
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_client.post.return_value = mock_response
    mock_client.get.return_value = mock_response
    return mock_client


# ============================================
# Data Fixtures
# ============================================

@pytest.fixture
def sample_market_snapshot():
    """Create a sample market snapshot."""
    from adaptive_agent.models import MarketSnapshot, MarketRegime
    
    return MarketSnapshot(
        timestamp=datetime.now(),
        tqqq_price=45.50,
        sqqq_price=12.30,
        qqq_price=380.25,
        rsi=55.0,
        momentum=0.02,
        volatility=0.018,
        trend_strength=0.35,
        volume_ratio=1.2,
        regime=MarketRegime.NEUTRAL,
        regime_confidence=0.65,
        hour_of_day=11,
        day_of_week=2,
        is_market_open=True,
    )


@pytest.fixture
def sample_performance_snapshot():
    """Create a sample performance snapshot."""
    from adaptive_agent.models import PerformanceSnapshot
    
    return PerformanceSnapshot(
        timestamp=datetime.now(),
        daily_pnl=125.50,
        daily_trades=8,
        daily_win_rate=0.625,
        weekly_pnl=450.00,
        weekly_trades=35,
        weekly_win_rate=0.57,
        total_pnl=2500.00,
        total_trades=150,
        overall_win_rate=0.55,
        sharpe_ratio=1.8,
        max_drawdown=0.08,
        current_drawdown=0.03,
        current_streak=2,
    )


@pytest.fixture
def sample_positions():
    """Create sample position snapshots."""
    from adaptive_agent.models import PositionSnapshot
    
    return [
        PositionSnapshot(
            symbol="TQQQ",
            quantity=100,
            avg_entry_price=44.50,
            current_price=45.50,
            unrealized_pnl=100.00,
            unrealized_pnl_pct=2.25,
            side="long",
        ),
    ]


@pytest.fixture
def sample_trade_data():
    """Create sample trade records."""
    now = datetime.now()
    return [
        {
            "trade_id": "T001",
            "symbol": "TQQQ",
            "side": "BUY",
            "quantity": 100,
            "entry_price": 44.50,
            "exit_price": 45.50,
            "pnl": 100.00,
            "entry_time": now - timedelta(hours=2),
            "exit_time": now - timedelta(hours=1),
            "status": "CLOSED",
        },
        {
            "trade_id": "T002",
            "symbol": "TQQQ",
            "side": "BUY",
            "quantity": 50,
            "entry_price": 45.20,
            "exit_price": 44.80,
            "pnl": -20.00,
            "entry_time": now - timedelta(hours=1),
            "exit_time": now - timedelta(minutes=30),
            "status": "CLOSED",
        },
    ]


# ============================================
# Component Fixtures
# ============================================

@pytest.fixture
def observer(agent_config):
    """Create an Observer instance."""
    from adaptive_agent.observer import Observer
    return Observer(agent_config)


@pytest.fixture
def analyzer(agent_config):
    """Create an Analyzer instance."""
    from adaptive_agent.analyzer import Analyzer
    return Analyzer(agent_config)


@pytest.fixture
def executor(agent_config):
    """Create an Executor instance."""
    from adaptive_agent.executor import Executor
    return Executor(agent_config)


@pytest.fixture
def decision_engine(agent_config):
    """Create a DecisionEngine instance."""
    from adaptive_agent.decision_engine import DecisionEngine
    return DecisionEngine(agent_config)


@pytest.fixture
def adaptive_agent(agent_config):
    """Create an AdaptiveAgent instance."""
    from adaptive_agent.agent import AdaptiveAgent
    return AdaptiveAgent(agent_config)


@pytest.fixture
def learning_store(learning_store_config):
    """Create a LearningStore instance."""
    from learning_store.store import LearningStore
    return LearningStore(learning_store_config)


# ============================================
# Async Fixtures
# ============================================

@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================
# Markers
# ============================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "database: marks tests that require database")
    config.addinivalue_line("markers", "slow: marks tests as slow running")
    config.addinivalue_line("markers", "mcp: marks tests that require MCP servers")
    config.addinivalue_line("markers", "e2e: marks end-to-end tests")
