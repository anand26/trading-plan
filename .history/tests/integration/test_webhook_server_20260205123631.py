"""
Integration tests for Webhook Server database operations.
Tests all database logging: Orders, Trades, WebhookEvents, Sessions
with transaction rollback to keep database clean.
"""

import pytest
import pyodbc
import uuid
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Add webhooks folder to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'webhooks'))


@pytest.fixture
def db_connection_string():
    """Get database connection string."""
    driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("DB_SERVER", "localhost")
    database = os.getenv("DB_NAME", "TradingDB")
    
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"Trusted_Connection=yes;"
        f"TrustServerCertificate=yes"
    )


@pytest.fixture
def db_connection(db_connection_string):
    """Create database connection with autocommit=False for rollback testing."""
    conn = pyodbc.connect(db_connection_string, timeout=10, autocommit=False)
    yield conn
    # Rollback any uncommitted changes
    conn.rollback()
    conn.close()


@pytest.fixture
def test_session_id():
    """Generate unique test session ID."""
    return f"WH-TEST-{str(uuid.uuid4())[:8]}"


@pytest.fixture
def test_order_id():
    """Generate unique test order ID."""
    return f"test-order-{str(uuid.uuid4())}"


class WebhookServerDBTester:
    """
    Simulates webhook server database operations for testing.
    This mirrors the DatabaseLogger class in webhook_server.py
    """
    
    def __init__(self, conn: pyodbc.Connection):
        self.conn = conn
        self.cursor = conn.cursor()
    
    def create_session(self, session_id: str, session_type: str = "PAPER") -> bool:
        """Create a new session (mirrors log_webhook_event session creation)."""
        try:
            self.cursor.execute("""
                INSERT INTO dbo.Sessions 
                (SessionId, SessionType, StrategyId, StartTime, Status, Notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                session_type,
                "TQQQ_SQQQ_PAIRS",
                datetime.now(timezone.utc),
                "active",
                "Test session - will be rolled back"
            ))
            return True
        except Exception as e:
            print(f"Error creating session: {e}")
            return False
    
    def log_order(
        self,
        order_id: str,
        symbol: str,
        qty: int,
        price: float,
        direction: str,
        session_id: str
    ) -> bool:
        """Log order to Orders table (mirrors log_trade's order logging)."""
        try:
            self.cursor.execute("""
                INSERT INTO dbo.Orders
                (ExternalOrderId, Symbol, Quantity, FilledQuantity, Price, FillPrice, 
                 OrderType, Direction, Status, TimeInForce, SubmittedAt, FilledAt, Tag, CreatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                symbol,
                qty,
                qty,
                price,
                price,
                'market',
                direction,
                'filled',
                'day',
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
                f"Webhook:TEST|Session:{session_id}",
                datetime.now(timezone.utc)
            ))
            return True
        except Exception as e:
            print(f"Error logging order: {e}")
            return False
    
    def log_trade_entry(
        self,
        symbol: str,
        direction: str,
        price: float,
        qty: int,
        session_id: str
    ) -> Optional[int]:
        """Log trade entry to Trades table."""
        try:
            self.cursor.execute("""
                INSERT INTO dbo.Trades
                (Symbol, Direction, EntryTime, EntryPrice, EntryQuantity, SessionId, CreatedAt)
                OUTPUT INSERTED.TradeId
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                direction,
                datetime.now(timezone.utc),
                price,
                qty,
                session_id,
                datetime.now(timezone.utc)
            ))
            row = self.cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"Error logging trade entry: {e}")
            return None
    
    def log_trade_exit(
        self,
        trade_id: int,
        exit_price: float,
        qty: int,
        reason: str,
        session_id: str = None
    ) -> bool:
        """Update trade with exit info and calculate P&L."""
        try:
            # First get entry price to calculate P&L
            self.cursor.execute(
                "SELECT EntryPrice, EntryQuantity FROM dbo.Trades WHERE TradeId = ?",
                (trade_id,)
            )
            row = self.cursor.fetchone()
            if not row:
                return False
            
            entry_price = float(row[0])
            entry_qty = float(row[1])
            
            # Calculate P&L
            gross_pnl = (exit_price - entry_price) * entry_qty
            pnl_pct = ((exit_price / entry_price) - 1) * 100
            
            self.cursor.execute("""
                UPDATE dbo.Trades
                SET ExitTime = ?, ExitPrice = ?, ExitQuantity = ?, ExitReason = ?,
                    GrossPnL = ?, NetPnL = ?, PnLPercent = ?
                WHERE TradeId = ?
            """, (
                datetime.now(timezone.utc),
                exit_price,
                qty,
                reason,
                gross_pnl,
                gross_pnl,
                pnl_pct,
                trade_id
            ))
            
            # Update DailyPerformance if session_id provided
            if session_id:
                today = datetime.now(timezone.utc).date()
                is_win = gross_pnl > 0
                
                # Check if record exists
                self.cursor.execute(
                    "SELECT PerformanceId FROM dbo.DailyPerformance WHERE Date = ? AND SessionId = ?",
                    (today, session_id)
                )
                if self.cursor.fetchone():
                    # Update
                    self.cursor.execute("""
                        UPDATE dbo.DailyPerformance SET
                            NumTrades = ISNULL(NumTrades, 0) + 1,
                            WinningTrades = ISNULL(WinningTrades, 0) + ?,
                            LosingTrades = ISNULL(LosingTrades, 0) + ?,
                            GrossProfit = ISNULL(GrossProfit, 0) + ?,
                            GrossLoss = ISNULL(GrossLoss, 0) + ?,
                            DailyPnL = ISNULL(DailyPnL, 0) + ?,
                            LastUpdated = ?
                        WHERE Date = ? AND SessionId = ?
                    """, (
                        1 if is_win else 0,
                        0 if is_win else 1,
                        gross_pnl if is_win else 0,
                        abs(gross_pnl) if not is_win else 0,
                        gross_pnl,
                        datetime.now(timezone.utc),
                        today,
                        session_id
                    ))
                else:
                    # Insert
                    self.cursor.execute("""
                        INSERT INTO dbo.DailyPerformance 
                        (Date, StartingEquity, EndingEquity, DailyPnL, DailyPnLPercent,
                         NumTrades, WinningTrades, LosingTrades, GrossProfit, GrossLoss, 
                         SessionId, CreatedAt, LastUpdated)
                        VALUES (?, 0, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        today,
                        gross_pnl,  # EndingEquity = P&L for now
                        gross_pnl,
                        pnl_pct,
                        1 if is_win else 0,
                        0 if is_win else 1,
                        gross_pnl if is_win else 0,
                        abs(gross_pnl) if not is_win else 0,
                        session_id,
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc)
                    ))
            
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"Error logging trade exit: {e}")
            return False
    
    def log_webhook_event(
        self,
        session_id: str,
        webhook_type: str,
        symbol: str,
        trigger_reason: str,
        price: Optional[float] = None,
        payload: Optional[Dict] = None,
        response: Optional[Dict] = None
    ) -> bool:
        """Log webhook event to WebhookEvents table."""
        import json
        try:
            self.cursor.execute("""
                INSERT INTO dbo.WebhookEvents 
                (SessionId, Timestamp, WebhookType, Symbol, TriggerReason, Price, MarketData, Conditions, CreatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.now(timezone.utc),
                webhook_type[:50] if webhook_type else 'UNKNOWN',
                symbol[:20] if symbol else 'UNKNOWN',
                (trigger_reason or '')[:500],
                price,
                json.dumps(payload or {}),
                json.dumps(response or {}),
                datetime.now(timezone.utc)
            ))
            return True
        except Exception as e:
            print(f"Error logging webhook event: {e}")
            return False
    
    def close_session(self, session_id: str, reason: str) -> bool:
        """Close session (mirrors close_session method)."""
        try:
            self.cursor.execute("""
                UPDATE dbo.Sessions 
                SET Status = 'completed', 
                    EndTime = ?,
                    Notes = CONCAT(ISNULL(Notes, ''), ' | Closed: ', ?)
                WHERE SessionId = ?
            """, (
                datetime.now(timezone.utc),
                reason,
                session_id
            ))
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"Error closing session: {e}")
            return False
    
    def verify_session_exists(self, session_id: str) -> bool:
        """Check if session was created."""
        self.cursor.execute(
            "SELECT COUNT(*) FROM dbo.Sessions WHERE SessionId = ?",
            (session_id,)
        )
        return self.cursor.fetchone()[0] > 0
    
    def verify_order_exists(self, order_id: str) -> bool:
        """Check if order was created."""
        self.cursor.execute(
            "SELECT COUNT(*) FROM dbo.Orders WHERE ExternalOrderId = ?",
            (order_id,)
        )
        return self.cursor.fetchone()[0] > 0
    
    def verify_trade_exists(self, trade_id: int) -> Dict[str, Any]:
        """Get trade details."""
        self.cursor.execute(
            "SELECT Symbol, Direction, EntryPrice, ExitPrice, ExitReason FROM dbo.Trades WHERE TradeId = ?",
            (trade_id,)
        )
        row = self.cursor.fetchone()
        if row:
            return {
                "symbol": row[0],
                "direction": row[1],
                "entry_price": float(row[2]) if row[2] else None,
                "exit_price": float(row[3]) if row[3] else None,
                "exit_reason": row[4]
            }
        return {}
    
    def verify_webhook_event_exists(self, session_id: str, webhook_type: str) -> bool:
        """Check if webhook event was logged."""
        self.cursor.execute(
            "SELECT COUNT(*) FROM dbo.WebhookEvents WHERE SessionId = ? AND WebhookType = ?",
            (session_id, webhook_type)
        )
        return self.cursor.fetchone()[0] > 0
    
    def count_session_records(self, session_id: str) -> Dict[str, int]:
        """Count all records linked to session."""
        counts = {}
        
        # Sessions
        self.cursor.execute("SELECT COUNT(*) FROM dbo.Sessions WHERE SessionId = ?", (session_id,))
        counts['sessions'] = self.cursor.fetchone()[0]
        
        # Trades
        self.cursor.execute("SELECT COUNT(*) FROM dbo.Trades WHERE SessionId = ?", (session_id,))
        counts['trades'] = self.cursor.fetchone()[0]
        
        # WebhookEvents
        self.cursor.execute("SELECT COUNT(*) FROM dbo.WebhookEvents WHERE SessionId = ?", (session_id,))
        counts['webhook_events'] = self.cursor.fetchone()[0]
        
        # Orders (via Tag containing session_id)
        self.cursor.execute("SELECT COUNT(*) FROM dbo.Orders WHERE Tag LIKE ?", (f"%{session_id}%",))
        counts['orders'] = self.cursor.fetchone()[0]
        
        # DailyPerformance
        self.cursor.execute("SELECT COUNT(*) FROM dbo.DailyPerformance WHERE SessionId = ?", (session_id,))
        counts['daily_performance'] = self.cursor.fetchone()[0]
        
        return counts
    
    def verify_daily_performance(self, session_id: str) -> Dict[str, Any]:
        """Get daily performance details for session."""
        self.cursor.execute("""
            SELECT Date, NumTrades, WinningTrades, LosingTrades, GrossProfit, GrossLoss, DailyPnL
            FROM dbo.DailyPerformance WHERE SessionId = ?
        """, (session_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                "date": row[0],
                "num_trades": row[1],
                "winning_trades": row[2],
                "losing_trades": row[3],
                "gross_profit": float(row[4]) if row[4] else 0,
                "gross_loss": float(row[5]) if row[5] else 0,
                "daily_pnl": float(row[6]) if row[6] else 0
            }
        return {}


@pytest.mark.database
@pytest.mark.integration
class TestWebhookServerDatabaseOperations:
    """Test all database operations performed by webhook server."""
    
    def test_session_creation(self, db_connection, test_session_id):
        """Should create a new session."""
        tester = WebhookServerDBTester(db_connection)
        
        # Create session
        result = tester.create_session(test_session_id, "PAPER")
        assert result is True, "Failed to create session"
        
        # Verify session exists
        assert tester.verify_session_exists(test_session_id), "Session not found after creation"
        
        # Verify session is active
        tester.cursor.execute(
            "SELECT Status FROM dbo.Sessions WHERE SessionId = ?",
            (test_session_id,)
        )
        status = tester.cursor.fetchone()[0]
        assert status == "active", f"Expected status 'active', got '{status}'"
        
        # Rollback happens automatically in fixture
        print(f"✓ Session {test_session_id} created and verified")
    
    def test_order_logging(self, db_connection, test_session_id, test_order_id):
        """Should log order to Orders table."""
        tester = WebhookServerDBTester(db_connection)
        
        # Create session first
        tester.create_session(test_session_id)
        
        # Log order
        result = tester.log_order(
            order_id=test_order_id,
            symbol="TQQQ",
            qty=100,
            price=85.50,
            direction="buy",
            session_id=test_session_id
        )
        assert result is True, "Failed to log order"
        
        # Verify order exists
        assert tester.verify_order_exists(test_order_id), "Order not found after logging"
        
        print(f"✓ Order {test_order_id} logged and verified")
    
    def test_trade_entry_logging(self, db_connection, test_session_id):
        """Should log trade entry to Trades table."""
        tester = WebhookServerDBTester(db_connection)
        
        # Create session first
        tester.create_session(test_session_id)
        
        # Log trade entry
        trade_id = tester.log_trade_entry(
            symbol="TQQQ",
            direction="LONG",
            price=85.50,
            qty=100,
            session_id=test_session_id
        )
        assert trade_id is not None, "Failed to log trade entry"
        
        # Verify trade exists
        trade = tester.verify_trade_exists(trade_id)
        assert trade, "Trade not found after logging"
        assert trade['symbol'] == "TQQQ"
        assert trade['direction'] == "LONG"
        assert trade['entry_price'] == 85.50
        assert trade['exit_price'] is None  # Not exited yet
        
        print(f"✓ Trade entry {trade_id} logged and verified")
    
    def test_trade_exit_logging(self, db_connection, test_session_id):
        """Should update trade with exit info."""
        tester = WebhookServerDBTester(db_connection)
        
        # Create session and trade entry
        tester.create_session(test_session_id)
        trade_id = tester.log_trade_entry(
            symbol="TQQQ",
            direction="LONG",
            price=85.50,
            qty=100,
            session_id=test_session_id
        )
        assert trade_id is not None
        
        # Log trade exit
        result = tester.log_trade_exit(
            trade_id=trade_id,
            exit_price=87.00,
            qty=100,
            reason="Webhook:EXIT"
        )
        assert result is True, "Failed to log trade exit"
        
        # Verify trade has exit info
        trade = tester.verify_trade_exists(trade_id)
        assert trade['exit_price'] == 87.00
        assert trade['exit_reason'] == "Webhook:EXIT"
        
        print(f"✓ Trade exit {trade_id} logged and verified")
    
    def test_webhook_event_logging(self, db_connection, test_session_id):
        """Should log webhook event to WebhookEvents table."""
        tester = WebhookServerDBTester(db_connection)
        
        # Create session
        tester.create_session(test_session_id)
        
        # Log webhook event
        result = tester.log_webhook_event(
            session_id=test_session_id,
            webhook_type="BUY_TQQQ",
            symbol="TQQQ",
            trigger_reason="executed",
            price=85.50,
            payload={"action": "BUY_TQQQ", "price": 85.50},
            response={"status": "executed", "order_id": "test-123"}
        )
        assert result is True, "Failed to log webhook event"
        
        # Verify webhook event exists
        assert tester.verify_webhook_event_exists(test_session_id, "BUY_TQQQ")
        
        print(f"✓ Webhook event logged and verified")
    
    def test_session_close(self, db_connection, test_session_id):
        """Should close session properly."""
        tester = WebhookServerDBTester(db_connection)
        
        # Create session
        tester.create_session(test_session_id)
        
        # Close session
        result = tester.close_session(test_session_id, "Test complete")
        assert result is True, "Failed to close session"
        
        # Verify session is closed
        tester.cursor.execute(
            "SELECT Status, EndTime FROM dbo.Sessions WHERE SessionId = ?",
            (test_session_id,)
        )
        row = tester.cursor.fetchone()
        assert row[0] == "completed", f"Expected status 'completed', got '{row[0]}'"
        assert row[1] is not None, "EndTime should be set"
        
        print(f"✓ Session {test_session_id} closed and verified")


@pytest.mark.database
@pytest.mark.integration
class TestFullTradeLifecycle:
    """Test complete trade lifecycle: session → entry → exit → session close."""
    
    def test_complete_trade_lifecycle_with_rollback(self, db_connection, test_session_id):
        """
        Test full trade lifecycle and verify rollback cleans up all records.
        This is the most important test - ensures webhook server operations work correctly.
        """
        tester = WebhookServerDBTester(db_connection)
        order_id_entry = f"test-order-entry-{uuid.uuid4()}"
        order_id_exit = f"test-order-exit-{uuid.uuid4()}"
        
        print("\n" + "=" * 60)
        print("FULL TRADE LIFECYCLE TEST WITH ROLLBACK")
        print("=" * 60)
        
        # Step 1: Create session
        print("\n1. Creating session...")
        assert tester.create_session(test_session_id)
        assert tester.verify_session_exists(test_session_id)
        print(f"   ✓ Session {test_session_id} created")
        
        # Step 2: Log BUY webhook event
        print("\n2. Logging BUY webhook event...")
        assert tester.log_webhook_event(
            session_id=test_session_id,
            webhook_type="BUY_TQQQ",
            symbol="TQQQ",
            trigger_reason="executed",
            price=85.50,
            payload={"action": "BUY_TQQQ", "price": 85.50, "position_size": 0.57}
        )
        print("   ✓ BUY webhook event logged")
        
        # Step 3: Log entry order
        print("\n3. Logging entry order to Orders table...")
        assert tester.log_order(
            order_id=order_id_entry,
            symbol="TQQQ",
            qty=100,
            price=85.50,
            direction="buy",
            session_id=test_session_id
        )
        assert tester.verify_order_exists(order_id_entry)
        print(f"   ✓ Entry order {order_id_entry} logged")
        
        # Step 4: Log trade entry
        print("\n4. Logging trade entry to Trades table...")
        trade_id = tester.log_trade_entry(
            symbol="TQQQ",
            direction="LONG",
            price=85.50,
            qty=100,
            session_id=test_session_id
        )
        assert trade_id is not None
        print(f"   ✓ Trade entry {trade_id} logged")
        
        # Step 5: Log EXIT webhook event
        print("\n5. Logging EXIT webhook event...")
        assert tester.log_webhook_event(
            session_id=test_session_id,
            webhook_type="EXIT",
            symbol="TQQQ",
            trigger_reason="executed",
            price=87.00,
            payload={"action": "EXIT", "reason": "Take profit"}
        )
        print("   ✓ EXIT webhook event logged")
        
        # Step 6: Log exit order
        print("\n6. Logging exit order to Orders table...")
        assert tester.log_order(
            order_id=order_id_exit,
            symbol="TQQQ",
            qty=100,
            price=87.00,
            direction="sell",
            session_id=test_session_id
        )
        assert tester.verify_order_exists(order_id_exit)
        print(f"   ✓ Exit order {order_id_exit} logged")
        
        # Step 7: Update trade with exit (with P&L and DailyPerformance)
        print("\n7. Updating trade with exit info and DailyPerformance...")
        assert tester.log_trade_exit(
            trade_id=trade_id,
            exit_price=87.00,
            qty=100,
            reason="Webhook:EXIT",
            session_id=test_session_id  # This triggers DailyPerformance update
        )
        trade = tester.verify_trade_exists(trade_id)
        assert trade['exit_price'] == 87.00
        print(f"   ✓ Trade {trade_id} updated with exit")
        
        # Verify DailyPerformance was populated
        perf = tester.verify_daily_performance(test_session_id)
        assert perf, "DailyPerformance should be populated"
        print(f"   ✓ DailyPerformance: {perf['num_trades']} trade(s), P&L=${perf['daily_pnl']:.2f}")
        
        # Step 8: Close session
        print("\n8. Closing session...")
        assert tester.close_session(test_session_id, "All positions closed")
        print(f"   ✓ Session {test_session_id} closed")
        
        # Step 9: Verify all records exist before rollback
        print("\n9. Verifying all records exist before rollback...")
        counts_before = tester.count_session_records(test_session_id)
        print(f"   Sessions: {counts_before['sessions']}")
        print(f"   Trades: {counts_before['trades']}")
        print(f"   Orders: {counts_before['orders']}")
        print(f"   WebhookEvents: {counts_before['webhook_events']}")
        print(f"   DailyPerformance: {counts_before['daily_performance']}")
        
        assert counts_before['sessions'] == 1, "Should have 1 session"
        assert counts_before['trades'] == 1, "Should have 1 trade"
        assert counts_before['orders'] == 2, "Should have 2 orders (entry + exit)"
        assert counts_before['webhook_events'] == 2, "Should have 2 webhook events"
        assert counts_before['daily_performance'] == 1, "Should have 1 DailyPerformance record"
        
        print("   ✓ All records verified")
        
        # Step 10: Rollback (done by fixture, but we can verify)
        print("\n10. Rolling back transaction...")
        db_connection.rollback()
        
        # Create new cursor after rollback
        cursor = db_connection.cursor()
        
        # Verify all records are gone
        cursor.execute("SELECT COUNT(*) FROM dbo.Sessions WHERE SessionId = ?", (test_session_id,))
        session_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dbo.Trades WHERE SessionId = ?", (test_session_id,))
        trade_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dbo.Orders WHERE Tag LIKE ?", (f"%{test_session_id}%",))
        order_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dbo.WebhookEvents WHERE SessionId = ?", (test_session_id,))
        event_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dbo.DailyPerformance WHERE SessionId = ?", (test_session_id,))
        perf_count = cursor.fetchone()[0]
        
        print(f"   After rollback:")
        print(f"   Sessions: {session_count}")
        print(f"   Trades: {trade_count}")
        print(f"   Orders: {order_count}")
        print(f"   WebhookEvents: {event_count}")
        print(f"   DailyPerformance: {perf_count}")
        
        assert session_count == 0, "Sessions should be rolled back"
        assert trade_count == 0, "Trades should be rolled back"
        assert order_count == 0, "Orders should be rolled back"
        assert event_count == 0, "WebhookEvents should be rolled back"
        assert perf_count == 0, "DailyPerformance should be rolled back"
        
        print("   ✓ All records rolled back successfully!")
        
        print("\n" + "=" * 60)
        print("✓ FULL TRADE LIFECYCLE TEST PASSED")
        print("=" * 60)


@pytest.mark.database
@pytest.mark.integration
class TestMultipleTradesInSession:
    """Test multiple trades within a single session."""
    
    def test_multiple_trades_same_session(self, db_connection, test_session_id):
        """Should handle multiple trades in one session."""
        tester = WebhookServerDBTester(db_connection)
        
        # Create session
        tester.create_session(test_session_id)
        
        trades = []
        
        # Trade 1: TQQQ Long
        trade1_id = tester.log_trade_entry("TQQQ", "LONG", 85.00, 100, test_session_id)
        tester.log_trade_exit(trade1_id, 86.50, 100, "Take profit")
        trades.append(trade1_id)
        
        # Trade 2: SQQQ Long  
        trade2_id = tester.log_trade_entry("SQQQ", "LONG", 12.00, 500, test_session_id)
        tester.log_trade_exit(trade2_id, 11.50, 500, "Stop loss")
        trades.append(trade2_id)
        
        # Trade 3: TQQQ Long again
        trade3_id = tester.log_trade_entry("TQQQ", "LONG", 84.00, 120, test_session_id)
        tester.log_trade_exit(trade3_id, 85.50, 120, "EOD exit")
        trades.append(trade3_id)
        
        # Verify all trades
        for trade_id in trades:
            trade = tester.verify_trade_exists(trade_id)
            assert trade is not None, f"Trade {trade_id} not found"
            assert trade['exit_price'] is not None, f"Trade {trade_id} should have exit"
        
        # Verify count
        counts = tester.count_session_records(test_session_id)
        assert counts['trades'] == 3, f"Should have 3 trades, got {counts['trades']}"
        
        print(f"✓ Multiple trades ({len(trades)}) in session verified")


def run_all_tests():
    """Run all webhook server tests."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 8 + "WEBHOOK SERVER DATABASE TEST SUITE" + " " * 15 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    # Run with pytest
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "-s", "--tb=short"],
        cwd=os.path.dirname(__file__)
    )
    return result.returncode


if __name__ == "__main__":
    # Can run directly for quick testing
    import sys
    
    # Quick test without pytest
    print("Running quick database test...")
    
    try:
        conn_string = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=localhost;"
            "DATABASE=TradingDB;"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes"
        )
        conn = pyodbc.connect(conn_string, timeout=10, autocommit=False)
        
        test_session_id = f"WH-TEST-{str(uuid.uuid4())[:8]}"
        tester = WebhookServerDBTester(conn)
        
        # Run quick lifecycle test
        test = TestFullTradeLifecycle()
        test.test_complete_trade_lifecycle_with_rollback(conn, test_session_id)
        
        print("\n✓ Quick test passed!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    
    # Keep window open so user can see results
    input("\nPress Enter to exit...")
