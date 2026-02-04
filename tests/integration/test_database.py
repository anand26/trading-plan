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
        "Orders",
        "StrategyParameters",
        "BacktestOutcomes",
        "DailyPerformance",
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
        "sp_GetLastTrades",
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
        "v_RecentTrades",
        "v_DailyTradeStats",
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
        # Insert using actual Trades schema (02_core_schema.sql)
        db_cursor.execute("""
            INSERT INTO Trades (
                Symbol, Direction, EntryTime, EntryPrice, EntryQuantity,
                SessionId, CreatedAt
            ) VALUES (
                'TQQQ', 'LONG', GETDATE(), 45.00, 100,
                'TEST_SESSION', GETDATE()
            )
        """)
        
        # Get the inserted ID
        db_cursor.execute("SELECT @@IDENTITY")
        trade_id = db_cursor.fetchone()[0]
        
        # Read back
        db_cursor.execute("""
            SELECT Symbol, EntryQuantity, EntryPrice 
            FROM Trades WHERE TradeId = ?
        """, (trade_id,))
        result = db_cursor.fetchone()
        
        assert result is not None
        assert result[0] == "TQQQ"
        assert result[1] == 100
        
        # Cleanup
        db_cursor.execute("DELETE FROM Trades WHERE TradeId = ?", (trade_id,))
    
    def test_insert_signal_data(self, db_cursor, clean_test_data):
        """Should insert signal data."""
        db_cursor.execute("""
            INSERT INTO Signals (
                Timestamp, Symbol, SignalType, Action, Price, RSI, SessionId
            ) VALUES (
                GETDATE(), 'TQQQ', 'ENTRY_L1', 'BUY', 45.50, 32.5, 'TEST_SESSION'
            )
        """)
        
        db_cursor.execute("""
            SELECT TOP 1 Price, RSI FROM Signals 
            WHERE Symbol = 'TQQQ' AND SessionId = 'TEST_SESSION' 
            ORDER BY Timestamp DESC
        """)
        result = db_cursor.fetchone()
        
        assert result is not None
        assert result[0] == 45.50
        
        # Cleanup
        db_cursor.execute("DELETE FROM Signals WHERE SessionId = 'TEST_SESSION'")
    
    def test_strategy_parameters_crud(self, db_cursor, clean_test_data):
        """Should perform CRUD on strategy parameters."""
        # Create/Update via MERGE using actual column names (ParamType is required)
        db_cursor.execute("""
            MERGE StrategyParameters AS target
            USING (SELECT 'TQQQ_SCALPING' AS StrategyId, 'TestParam' AS ParamName, 
                          '100' AS ParamValue, 'decimal' AS ParamType) AS source
            ON target.StrategyId = source.StrategyId AND target.ParamName = source.ParamName
            WHEN MATCHED THEN UPDATE SET ParamValue = source.ParamValue, LastUpdated = GETDATE()
            WHEN NOT MATCHED THEN INSERT (StrategyId, ParamName, ParamValue, ParamType, IsActive) 
                VALUES (source.StrategyId, source.ParamName, source.ParamValue, source.ParamType, 1);
        """)
        
        # Read
        db_cursor.execute("""
            SELECT ParamValue FROM StrategyParameters 
            WHERE StrategyId = 'TQQQ_SCALPING' AND ParamName = 'TestParam'
        """)
        result = db_cursor.fetchone()
        
        assert result is not None
        assert result[0] == "100"
        
        # Cleanup
        db_cursor.execute("""
            DELETE FROM StrategyParameters 
            WHERE StrategyId = 'TQQQ_SCALPING' AND ParamName = 'TestParam'
        """)


@pytest.mark.database
class TestTransactions:
    """Tests for transaction handling."""
    
    def test_transaction_rollback(self, db_connection, db_cursor):
        """Should rollback transaction on error."""
        db_connection.autocommit = False
        
        try:
            db_cursor.execute("""
                INSERT INTO Trades (
                    Symbol, Direction, EntryTime, EntryPrice, EntryQuantity, SessionId
                ) VALUES ('TQQQ', 'LONG', GETDATE(), 45.00, 100, 'ROLLBACK_TEST')
            """)
            
            # Force rollback
            db_connection.rollback()
            
            # Verify not inserted
            db_cursor.execute("SELECT COUNT(*) FROM Trades WHERE SessionId = 'ROLLBACK_TEST'")
            result = db_cursor.fetchone()
            
            assert result[0] == 0
            
        finally:
            db_connection.autocommit = True
