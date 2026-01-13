"""
Integration tests for database connectivity and schema.
"""

import pytest
from datetime import datetime


@pytest.mark.database
class TestDatabaseConnection:
    """Tests for database connectivity."""
    
    def test_connection_established(self, db_connection):
        """Should establish database connection."""
        assert db_connection is not None
    
    def test_can_execute_query(self, db_cursor):
        """Should execute basic query."""
        db_cursor.execute("SELECT 1 AS test")
        result = db_cursor.fetchone()
        
        assert result[0] == 1
    
    def test_database_exists(self, db_cursor):
        """Should connect to correct database."""
        db_cursor.execute("SELECT DB_NAME()")
        result = db_cursor.fetchone()
        
        assert result[0] in ["TradingDB", "TradingDB_Test"]


@pytest.mark.database
class TestCoreTablesExist:
    """Tests that required tables exist."""
    
    @pytest.mark.parametrize("table_name", [
        "Trades",
        "MarketData",
        "StrategyParameters",
        "BacktestResults",
        "PerformanceMetrics",
    ])
    def test_core_table_exists(self, db_cursor, table_name):
        """Should have required core tables."""
        db_cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = ?
        """, (table_name,))
        result = db_cursor.fetchone()
        
        assert result[0] == 1, f"Table {table_name} does not exist"
    
    @pytest.mark.parametrize("table_name", [
        "Patterns",
        "Recommendations",
    ])
    def test_learning_tables_exist(self, db_cursor, table_name):
        """Should have learning store tables."""
        db_cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = ?
        """, (table_name,))
        result = db_cursor.fetchone()
        
        assert result[0] == 1, f"Table {table_name} does not exist"
    
    @pytest.mark.parametrize("table_name", [
        "AgentActions",
        "AgentDecisions",
        "AgentState",
        "AgentAlerts",
    ])
    def test_agent_tables_exist(self, db_cursor, table_name):
        """Should have adaptive agent tables."""
        db_cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = ?
        """, (table_name,))
        result = db_cursor.fetchone()
        
        assert result[0] == 1, f"Table {table_name} does not exist"


@pytest.mark.database
class TestStoredProcedures:
    """Tests for stored procedures."""
    
    @pytest.mark.parametrize("proc_name", [
        "sp_RecordTrade",
        "sp_GetPerformanceMetrics",
        "sp_GetTopPatterns",
        "sp_GetActiveRecommendations",
        "sp_GetAgentSummary",
    ])
    def test_procedure_exists(self, db_cursor, proc_name):
        """Should have required stored procedures."""
        db_cursor.execute("""
            SELECT COUNT(*) FROM sys.procedures 
            WHERE name = ?
        """, (proc_name,))
        result = db_cursor.fetchone()
        
        assert result[0] == 1, f"Procedure {proc_name} does not exist"


@pytest.mark.database
class TestViews:
    """Tests for database views."""
    
    @pytest.mark.parametrize("view_name", [
        "vw_RecentTrades",
        "vw_DailyPerformance",
        "vw_PatternAnalysis",
        "vw_RecentAgentActivity",
    ])
    def test_view_exists(self, db_cursor, view_name):
        """Should have required views."""
        db_cursor.execute("""
            SELECT COUNT(*) FROM sys.views 
            WHERE name = ?
        """, (view_name,))
        result = db_cursor.fetchone()
        
        assert result[0] == 1, f"View {view_name} does not exist"


@pytest.mark.database
class TestDataOperations:
    """Tests for data operations."""
    
    def test_insert_and_read_trade(self, db_cursor, clean_test_data):
        """Should insert and read trade records."""
        # Insert
        db_cursor.execute("""
            INSERT INTO Trades (
                TradeId, Symbol, Side, Quantity, EntryPrice, EntryTime,
                Status, CreatedAt
            ) VALUES (
                'TEST_001', 'TQQQ', 'BUY', 100, 45.00, GETDATE(),
                'OPEN', GETDATE()
            )
        """)
        
        # Read back
        db_cursor.execute("""
            SELECT Symbol, Quantity, EntryPrice 
            FROM Trades WHERE TradeId = 'TEST_001'
        """)
        result = db_cursor.fetchone()
        
        assert result is not None
        assert result[0] == "TQQQ"
        assert result[1] == 100
        
        # Cleanup
        db_cursor.execute("DELETE FROM Trades WHERE TradeId = 'TEST_001'")
    
    def test_insert_market_data(self, db_cursor, clean_test_data):
        """Should insert market data."""
        db_cursor.execute("""
            INSERT INTO MarketData (
                Symbol, Timestamp, Price, Volume, RSI, Momentum
            ) VALUES (
                'TQQQ', GETDATE(), 45.50, 100000, 55.0, 0.02
            )
        """)
        
        db_cursor.execute("""
            SELECT TOP 1 Price, RSI FROM MarketData 
            WHERE Symbol = 'TQQQ' ORDER BY Timestamp DESC
        """)
        result = db_cursor.fetchone()
        
        assert result is not None
        assert result[0] == 45.50
    
    def test_strategy_parameters_crud(self, db_cursor, clean_test_data):
        """Should perform CRUD on strategy parameters."""
        # Create/Update via MERGE
        db_cursor.execute("""
            MERGE StrategyParameters AS target
            USING (SELECT 'TestParam' AS Name, '100' AS Value) AS source
            ON target.Name = source.Name
            WHEN MATCHED THEN UPDATE SET Value = source.Value
            WHEN NOT MATCHED THEN INSERT (Name, Value) VALUES (source.Name, source.Value);
        """)
        
        # Read
        db_cursor.execute("""
            SELECT Value FROM StrategyParameters WHERE Name = 'TestParam'
        """)
        result = db_cursor.fetchone()
        
        assert result is not None
        assert result[0] == "100"
        
        # Cleanup
        db_cursor.execute("DELETE FROM StrategyParameters WHERE Name = 'TestParam'")


@pytest.mark.database
class TestTransactions:
    """Tests for transaction handling."""
    
    def test_transaction_rollback(self, db_connection, db_cursor):
        """Should rollback transaction on error."""
        db_connection.autocommit = False
        
        try:
            db_cursor.execute("""
                INSERT INTO Trades (
                    TradeId, Symbol, Side, Quantity, EntryPrice, EntryTime, Status
                ) VALUES ('ROLLBACK_TEST', 'TQQQ', 'BUY', 100, 45.00, GETDATE(), 'OPEN')
            """)
            
            # Force rollback
            db_connection.rollback()
            
            # Verify not inserted
            db_cursor.execute("SELECT COUNT(*) FROM Trades WHERE TradeId = 'ROLLBACK_TEST'")
            result = db_cursor.fetchone()
            
            assert result[0] == 0
            
        finally:
            db_connection.autocommit = True
