"""
Database Module
===============
SQL Server database operations for LEAN-Ops MCP.
"""

import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False
    pyodbc = None

from .config import get_config

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Database operation error."""
    pass


class Database:
    """
    SQL Server database interface for LEAN-Ops MCP.
    
    Provides access to TradingDB for:
    - Backtest sessions and outcomes
    - Algorithm parameters
    - Trade history
    - Operation audit logs
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or get_config().database.get_connection_string()
        self._conn: Optional["pyodbc.Connection"] = None
    
    def connect(self) -> bool:
        """Establish database connection."""
        if not HAS_PYODBC:
            logger.warning("pyodbc not installed - database operations disabled")
            return False
        
        try:
            self._conn = pyodbc.connect(self.connection_string)
            logger.info("Connected to TradingDB")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
    
    @property
    def connected(self) -> bool:
        """Check if connected."""
        return self._conn is not None
    
    @contextmanager
    def cursor(self):
        """Context manager for database cursor."""
        if not self._conn:
            raise DatabaseError("Not connected to database")
        cursor = self._conn.cursor()
        try:
            yield cursor
            self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            raise DatabaseError(f"Database operation failed: {e}") from e
        finally:
            cursor.close()
    
    # ============================================
    # SESSION MANAGEMENT
    # ============================================
    
    def create_session(
        self,
        session_id: str,
        session_type: str,
        algorithm_name: str,
        start_date: date,
        end_date: date,
        initial_cash: float,
        parameters: Dict[str, Any]
    ) -> bool:
        """Create a new trading/backtest session."""
        try:
            with self.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO Sessions (
                        SessionId, SessionType, AlgorithmName, StartDate, EndDate,
                        InitialCash, Status, Parameters, CreatedAt
                    ) VALUES (?, ?, ?, ?, ?, ?, 'CREATED', ?, GETDATE())
                """, (
                    session_id, session_type, algorithm_name,
                    start_date, end_date, initial_cash,
                    str(parameters)
                ))
            logger.info(f"Created session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return False
    
    def update_session_status(self, session_id: str, status: str, notes: Optional[str] = None) -> bool:
        """Update session status."""
        try:
            with self.cursor() as cursor:
                if notes:
                    cursor.execute("""
                        UPDATE Sessions 
                        SET Status = ?, Notes = ?, UpdatedAt = GETDATE()
                        WHERE SessionId = ?
                    """, (status, notes, session_id))
                else:
                    cursor.execute("""
                        UPDATE Sessions 
                        SET Status = ?, UpdatedAt = GETDATE()
                        WHERE SessionId = ?
                    """, (status, session_id))
            return True
        except Exception as e:
            logger.error(f"Failed to update session status: {e}")
            return False
    
    def complete_session(
        self,
        session_id: str,
        total_return: float,
        sharpe_ratio: float,
        max_drawdown: float,
        win_rate: float,
        total_trades: int
    ) -> bool:
        """Mark session as completed with final statistics."""
        try:
            with self.cursor() as cursor:
                cursor.execute("""
                    UPDATE Sessions SET
                        Status = 'COMPLETED',
                        TotalReturn = ?,
                        SharpeRatio = ?,
                        MaxDrawdown = ?,
                        WinRate = ?,
                        TotalTrades = ?,
                        CompletedAt = GETDATE(),
                        UpdatedAt = GETDATE()
                    WHERE SessionId = ?
                """, (
                    total_return, sharpe_ratio, max_drawdown,
                    win_rate, total_trades, session_id
                ))
            logger.info(f"Completed session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to complete session: {e}")
            return False
    
    # ============================================
    # BACKTEST QUERIES
    # ============================================
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details."""
        try:
            with self.cursor() as cursor:
                cursor.execute("""
                    SELECT SessionId, SessionType, AlgorithmName, StartDate, EndDate,
                           InitialCash, Status, TotalReturn, SharpeRatio, MaxDrawdown,
                           WinRate, TotalTrades, Parameters, CreatedAt, CompletedAt
                    FROM Sessions WHERE SessionId = ?
                """, (session_id,))
                row = cursor.fetchone()
                if row:
                    columns = [col[0] for col in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    def list_sessions(
        self,
        session_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List sessions with optional filters."""
        try:
            with self.cursor() as cursor:
                query = """
                    SELECT TOP (?) SessionId, SessionType, AlgorithmName, StartDate, EndDate,
                           Status, TotalReturn, SharpeRatio, MaxDrawdown, WinRate,
                           TotalTrades, CreatedAt, CompletedAt
                    FROM Sessions
                    WHERE 1=1
                """
                params = [limit]
                
                if session_type:
                    query += " AND SessionType = ?"
                    params.append(session_type)
                if status:
                    query += " AND Status = ?"
                    params.append(status)
                
                query += " ORDER BY CreatedAt DESC"
                
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    def get_backtest_trades(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all trades for a backtest session."""
        try:
            with self.cursor() as cursor:
                cursor.execute("""
                    SELECT TradeId, Symbol, Side, Quantity, EntryPrice, ExitPrice,
                           RealizedPnL, RealizedPnLPct, EntryTime, ExitTime,
                           EntryReason, ExitReason, HoldingPeriodSeconds
                    FROM Trades
                    WHERE SessionId = ?
                    ORDER BY EntryTime
                """, (session_id,))
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get backtest trades: {e}")
            return []
    
    # ============================================
    # PARAMETER MANAGEMENT
    # ============================================
    
    def get_parameters(self, algorithm_name: str) -> Dict[str, Any]:
        """Get current parameters for algorithm."""
        try:
            with self.cursor() as cursor:
                cursor.execute("""
                    SELECT ParamName, ParamValue, ParamType
                    FROM Parameters
                    WHERE AlgorithmName = ? AND IsActive = 1
                """, (algorithm_name,))
                
                params = {}
                for row in cursor.fetchall():
                    name, value, param_type = row
                    # Convert to appropriate type
                    if param_type == 'int':
                        params[name] = int(value)
                    elif param_type == 'float':
                        params[name] = float(value)
                    elif param_type == 'bool':
                        params[name] = value.lower() == 'true'
                    else:
                        params[name] = value
                return params
        except Exception as e:
            logger.error(f"Failed to get parameters: {e}")
            return {}
    
    def update_parameter(
        self,
        algorithm_name: str,
        param_name: str,
        param_value: Any,
        param_type: str = "string"
    ) -> bool:
        """Update or create a parameter."""
        try:
            with self.cursor() as cursor:
                # Try update first
                cursor.execute("""
                    UPDATE Parameters SET ParamValue = ?, UpdatedAt = GETDATE()
                    WHERE AlgorithmName = ? AND ParamName = ? AND IsActive = 1
                """, (str(param_value), algorithm_name, param_name))
                
                if cursor.rowcount == 0:
                    # Insert new parameter
                    cursor.execute("""
                        INSERT INTO Parameters (AlgorithmName, ParamName, ParamValue, ParamType, IsActive, CreatedAt)
                        VALUES (?, ?, ?, ?, 1, GETDATE())
                    """, (algorithm_name, param_name, str(param_value), param_type))
            
            logger.info(f"Updated parameter {param_name}={param_value}")
            return True
        except Exception as e:
            logger.error(f"Failed to update parameter: {e}")
            return False
    
    def update_parameters_batch(
        self,
        algorithm_name: str,
        params: Dict[str, Any]
    ) -> bool:
        """Update multiple parameters at once."""
        success = True
        for name, value in params.items():
            # Infer type
            if isinstance(value, bool):
                param_type = "bool"
            elif isinstance(value, int):
                param_type = "int"
            elif isinstance(value, float):
                param_type = "float"
            else:
                param_type = "string"
            
            if not self.update_parameter(algorithm_name, name, value, param_type):
                success = False
        return success
    
    # ============================================
    # AUDIT LOGGING
    # ============================================
    
    def log_operation(
        self,
        operation: str,
        session_id: Optional[str],
        details: Dict[str, Any],
        success: bool,
        error_message: Optional[str] = None
    ) -> bool:
        """Log an operation for audit trail."""
        try:
            with self.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO AuditLog (
                        Operation, SessionId, Details, Success, ErrorMessage, Timestamp
                    ) VALUES (?, ?, ?, ?, ?, GETDATE())
                """, (
                    operation, session_id, str(details),
                    1 if success else 0, error_message
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to log operation: {e}")
            return False


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
        _db.connect()
    return _db


def close_db():
    """Close the global database connection."""
    global _db
    if _db is not None:
        _db.disconnect()
        _db = None
