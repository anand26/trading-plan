"""
Database connection and query utilities for the trading dashboard.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING
import streamlit as st
import threading

if TYPE_CHECKING:
    import pyodbc

try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False
    pyodbc = None  # type: ignore

import warnings
warnings.filterwarnings('ignore', message='pandas only supports SQLAlchemy')

from dashboard.config import db_config


class DatabaseConnection:
    """SQL Server database connection manager with thread-safe query execution."""
    
    def __init__(self):
        from typing import Any
        self._connection: Any = None  # pyodbc.Connection
        self._lock = threading.RLock()  # Reentrant lock for thread-safe operations
    
    def connect(self) -> bool:
        """Establish database connection."""
        if not PYODBC_AVAILABLE or pyodbc is None:
            st.error("pyodbc not installed")
            return False
        
        with self._lock:
            try:
                if self._connection:
                    # Try to close existing connection first
                    try:
                        self._connection.close()
                    except:
                        pass
                
                self._connection = pyodbc.connect(db_config.connection_string)
                return True
            except Exception as e:
                st.error(f"Database connection failed: {e}")
                return False
    
    def disconnect(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to database."""
        return self._connection is not None
    
    def query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        """Execute a query and return results as DataFrame."""
        if not self.is_connected:
            self.connect()
        
        if not self.is_connected or self._connection is None:
            return pd.DataFrame()
        
        try:
            # Create a new cursor for each query to avoid "connection is busy" errors
            cursor = self._connection.cursor()
            cursor.execute(sql, params)
            
            # Fetch all results and get column names
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
            
            # Convert to DataFrame
            return pd.DataFrame.from_records(rows, columns=columns)
        except Exception as e:
            st.error(f"Query failed: {e}")
            return pd.DataFrame()
    
    def execute(self, sql: str, params: tuple = ()) -> bool:
        """Execute a non-query SQL statement."""
        if not self.is_connected:
            self.connect()
        
        if not self.is_connected or self._connection is None:
            return False
        
        cursor = None
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, params)
            self._connection.commit()
            return True
        except Exception as e:
            st.error(f"Execution failed: {e}")
            return False
        finally:
            if cursor:
                cursor.close()


@st.cache_resource
def get_db_connection() -> DatabaseConnection:
    """Get cached database connection."""
    db = DatabaseConnection()
    db.connect()
    return db


# ==================== Trade Queries ====================

def get_session_type_filter() -> Optional[str]:
    """Get current data source filter from session state."""
    import streamlit as st
    data_source = st.session_state.get("data_source", "All")
    if data_source == "All":
        return None
    return data_source.upper()  # BACKTEST, PAPER, LIVE


def get_trades(
    days: Optional[int] = 30,
    symbol: Optional[str] = None,
    limit: int = 1000,
    session_type: Optional[str] = None
) -> pd.DataFrame:
    """Get recent trades.
    
    Args:
        days: Number of days to look back (None = all time)
        symbol: Optional symbol filter (TQQQ, SQQQ)
        limit: Maximum number of trades to return
        session_type: Optional session type filter (BACKTEST, PAPER, LIVE)
                     If None, uses session_state data_source
    """
    db = get_db_connection()
    
    # Use provided session_type or get from session state
    if session_type is None:
        session_type = get_session_type_filter()
    
    top_clause = f"TOP {limit}" if limit else ""
    
    # Base query with optional Sessions join for filtering
    if session_type:
        if days is None:
            # All time - no date filter
            sql = f"""
                SELECT {top_clause}
                    t.TradeId, t.Symbol, t.EntryTime, t.ExitTime, t.Direction,
                    t.EntryPrice, t.ExitPrice, t.EntryQuantity as Quantity, 
                    t.NetPnL, t.PnLPercent,
                    t.Commission, t.DurationMinutes,
                    t.ExitReason,
                    s.SessionType
                FROM dbo.Trades t
                INNER JOIN dbo.Sessions s ON t.SessionId = s.SessionId
                WHERE s.SessionType = ?
            """
            params: list = [session_type]
        else:
            sql = f"""
                SELECT {top_clause}
                    t.TradeId, t.Symbol, t.EntryTime, t.ExitTime, t.Direction,
                    t.EntryPrice, t.ExitPrice, t.EntryQuantity as Quantity, 
                    t.NetPnL, t.PnLPercent,
                    t.Commission, t.DurationMinutes,
                    t.ExitReason,
                    s.SessionType
                FROM dbo.Trades t
                INNER JOIN dbo.Sessions s ON t.SessionId = s.SessionId
                WHERE t.EntryTime >= DATEADD(day, -?, GETDATE())
                    AND s.SessionType = ?
            """
            params: list = [days, session_type]
    else:
        if days is None:
            # All time - no date filter
            sql = f"""
                SELECT {top_clause}
                    t.TradeId, t.Symbol, t.EntryTime, t.ExitTime, t.Direction,
                    t.EntryPrice, t.ExitPrice, t.EntryQuantity as Quantity, 
                    t.NetPnL, t.PnLPercent,
                    t.Commission, t.DurationMinutes,
                    t.ExitReason
                FROM dbo.Trades t
            """
            params = []
        else:
            sql = f"""
                SELECT {top_clause}
                    t.TradeId, t.Symbol, t.EntryTime, t.ExitTime, t.Direction,
                    t.EntryPrice, t.ExitPrice, t.EntryQuantity as Quantity, 
                    t.NetPnL, t.PnLPercent,
                    t.Commission, t.DurationMinutes,
                    t.ExitReason
                FROM dbo.Trades t
                WHERE t.EntryTime >= DATEADD(day, -?, GETDATE())
            """
            params = [days]
    
    if symbol:
        if days is None and not session_type:
            sql += " WHERE t.Symbol = ?"
        else:
            sql += " AND t.Symbol = ?"
        params.append(symbol)
    
    sql += " ORDER BY t.EntryTime DESC"
    
    return db.query(sql, tuple(params))


def get_trade_summary(days: Optional[int] = 30, session_type: Optional[str] = None) -> dict:
    """Get trade summary statistics.
    
    Args:
        days: Number of days to look back (None = all time)
        session_type: Optional session type filter (BACKTEST, PAPER, LIVE)
                     If None, uses session_state data_source
    """
    db = get_db_connection()
    
    # Use provided session_type or get from session state
    if session_type is None:
        session_type = get_session_type_filter()
    
    if session_type:
        if days is None:
            # All time
            sql = """
                SELECT 
                    COUNT(*) as TotalTrades,
                    SUM(CASE WHEN t.NetPnL > 0 THEN 1 ELSE 0 END) as WinningTrades,
                    SUM(CASE WHEN t.NetPnL < 0 THEN 1 ELSE 0 END) as LosingTrades,
                    SUM(t.NetPnL) as TotalPnL,
                    AVG(t.NetPnL) as AvgPnL,
                    MAX(t.NetPnL) as MaxWin,
                    MIN(t.NetPnL) as MaxLoss,
                    AVG(CASE WHEN t.NetPnL > 0 THEN t.NetPnL END) as AvgWin,
                    AVG(CASE WHEN t.NetPnL < 0 THEN t.NetPnL END) as AvgLoss,
                    AVG(t.DurationMinutes) as AvgHoldingMinutes
                FROM dbo.Trades t
                INNER JOIN dbo.Sessions s ON t.SessionId = s.SessionId
                WHERE s.SessionType = ?
            """
            df = db.query(sql, (session_type,))
        else:
            sql = """
                SELECT 
                    COUNT(*) as TotalTrades,
                    SUM(CASE WHEN t.NetPnL > 0 THEN 1 ELSE 0 END) as WinningTrades,
                    SUM(CASE WHEN t.NetPnL < 0 THEN 1 ELSE 0 END) as LosingTrades,
                    SUM(t.NetPnL) as TotalPnL,
                    AVG(t.NetPnL) as AvgPnL,
                    MAX(t.NetPnL) as MaxWin,
                    MIN(t.NetPnL) as MaxLoss,
                    AVG(CASE WHEN t.NetPnL > 0 THEN t.NetPnL END) as AvgWin,
                    AVG(CASE WHEN t.NetPnL < 0 THEN t.NetPnL END) as AvgLoss,
                    AVG(t.DurationMinutes) as AvgHoldingMinutes
                FROM dbo.Trades t
                INNER JOIN dbo.Sessions s ON t.SessionId = s.SessionId
                WHERE t.EntryTime >= DATEADD(day, -?, GETDATE())
                    AND s.SessionType = ?
            """
            df = db.query(sql, (days, session_type))
    else:
        if days is None:
            # All time
            sql = """
                SELECT 
                    COUNT(*) as TotalTrades,
                    SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) as WinningTrades,
                    SUM(CASE WHEN NetPnL < 0 THEN 1 ELSE 0 END) as LosingTrades,
                    SUM(NetPnL) as TotalPnL,
                    AVG(NetPnL) as AvgPnL,
                    MAX(NetPnL) as MaxWin,
                    MIN(NetPnL) as MaxLoss,
                    AVG(CASE WHEN NetPnL > 0 THEN NetPnL END) as AvgWin,
                    AVG(CASE WHEN NetPnL < 0 THEN NetPnL END) as AvgLoss,
                    AVG(DurationMinutes) as AvgHoldingMinutes
                FROM dbo.Trades
            """
            df = db.query(sql, ())
        else:
            sql = """
                SELECT 
                    COUNT(*) as TotalTrades,
                    SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) as WinningTrades,
                    SUM(CASE WHEN NetPnL < 0 THEN 1 ELSE 0 END) as LosingTrades,
                    SUM(NetPnL) as TotalPnL,
                    AVG(NetPnL) as AvgPnL,
                    MAX(NetPnL) as MaxWin,
                    MIN(NetPnL) as MaxLoss,
                    AVG(CASE WHEN NetPnL > 0 THEN NetPnL END) as AvgWin,
                    AVG(CASE WHEN NetPnL < 0 THEN NetPnL END) as AvgLoss,
                    AVG(DurationMinutes) as AvgHoldingMinutes
                FROM dbo.Trades
                WHERE EntryTime >= DATEADD(day, -?, GETDATE())
            """
            df = db.query(sql, (days,))
    
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


# ==================== Performance Queries ====================

def get_daily_performance(days: Optional[int] = 90, session_type: Optional[str] = None) -> pd.DataFrame:
    """Get daily performance data.
    
    Args:
        days: Number of days to look back (None = all time)
        session_type: Optional session type filter (BACKTEST, PAPER, LIVE)
                     If None, uses session_state data_source
    """
    db = get_db_connection()
    
    # Use provided session_type or get from session state
    if session_type is None:
        session_type = get_session_type_filter()
    
    if session_type:
        # Join with Sessions to filter by session type
        if days is None:
            sql = """
                SELECT 
                    dp.Date, 
                    dp.NumTrades as TotalTrades,
                    dp.WinningTrades, 
                    dp.LosingTrades,
                    dp.GrossProfit,
                    dp.GrossLoss,
                    dp.DailyPnL,
                    dp.DailyPnLPercent,
                    dp.EndingEquity,
                    dp.MaxDrawdown,
                    CASE WHEN dp.LosingTrades > 0 
                        THEN CAST(dp.WinningTrades AS FLOAT) / CAST(dp.NumTrades AS FLOAT) * 100
                        ELSE 0 END as WinRate,
                    CASE WHEN dp.GrossLoss <> 0 
                        THEN ABS(dp.GrossProfit / dp.GrossLoss) 
                        ELSE 0 END as ProfitFactor
                FROM dbo.DailyPerformance dp
                WHERE dp.SessionId IN (
                        SELECT SessionId FROM dbo.Sessions WHERE SessionType = ?
                    )
                ORDER BY dp.Date ASC
            """
            return db.query(sql, (session_type,))
        else:
            sql = """
                SELECT 
                    dp.Date, 
                    dp.NumTrades as TotalTrades,
                    dp.WinningTrades, 
                    dp.LosingTrades,
                    dp.GrossProfit,
                    dp.GrossLoss,
                    dp.DailyPnL,
                    dp.DailyPnLPercent,
                    dp.EndingEquity,
                    dp.MaxDrawdown,
                    CASE WHEN dp.LosingTrades > 0 
                        THEN CAST(dp.WinningTrades AS FLOAT) / CAST(dp.NumTrades AS FLOAT) * 100
                        ELSE 0 END as WinRate,
                    CASE WHEN dp.GrossLoss <> 0 
                        THEN ABS(dp.GrossProfit / dp.GrossLoss) 
                        ELSE 0 END as ProfitFactor
                FROM dbo.DailyPerformance dp
                WHERE dp.Date >= DATEADD(day, -?, GETDATE())
                    AND dp.SessionId IN (
                        SELECT SessionId FROM dbo.Sessions WHERE SessionType = ?
                    )
                ORDER BY dp.Date ASC
            """
            return db.query(sql, (days, session_type))
    else:
        if days is None:
            sql = """
                SELECT 
                    Date, 
                    NumTrades as TotalTrades,
                    WinningTrades, 
                    LosingTrades,
                    GrossProfit,
                    GrossLoss,
                    DailyPnL,
                    DailyPnLPercent,
                    EndingEquity,
                    MaxDrawdown,
                    CASE WHEN LosingTrades > 0 
                        THEN CAST(WinningTrades AS FLOAT) / CAST(NumTrades AS FLOAT) * 100
                        ELSE 0 END as WinRate,
                    CASE WHEN GrossLoss <> 0 
                        THEN ABS(GrossProfit / GrossLoss) 
                        ELSE 0 END as ProfitFactor
                FROM dbo.DailyPerformance
                ORDER BY Date ASC
            """
            return db.query(sql, ())
        else:
            sql = """
                SELECT 
                    Date, 
                    NumTrades as TotalTrades,
                    WinningTrades, 
                    LosingTrades,
                    GrossProfit,
                    GrossLoss,
                    DailyPnL,
                    DailyPnLPercent,
                    EndingEquity,
                    MaxDrawdown,
                    CASE WHEN LosingTrades > 0 
                        THEN CAST(WinningTrades AS FLOAT) / CAST(NumTrades AS FLOAT) * 100
                        ELSE 0 END as WinRate,
                    CASE WHEN GrossLoss <> 0 
                        THEN ABS(GrossProfit / GrossLoss) 
                        ELSE 0 END as ProfitFactor
                FROM dbo.DailyPerformance
                WHERE Date >= DATEADD(day, -?, GETDATE())
                ORDER BY Date ASC
            """
            return db.query(sql, (days,))
        return db.query(sql, (days,))


def get_equity_curve(days: int = 365, session_type: Optional[str] = None) -> pd.DataFrame:
    """Get equity curve data.
    
    Args:
        days: Number of days to look back
        session_type: Optional session type filter (BACKTEST, PAPER, LIVE)
                     If None, uses session_state data_source
    """
    db = get_db_connection()
    
    # Use provided session_type or get from session state
    if session_type is None:
        session_type = get_session_type_filter()
    
    if session_type:
        sql = """
            SELECT 
                dp.Date,
                dp.EndingEquity as PortfolioValue,
                dp.CumulativePnL
            FROM dbo.DailyPerformance dp
            WHERE dp.Date >= DATEADD(day, -?, GETDATE())
                AND dp.SessionId IN (
                    SELECT SessionId FROM dbo.Sessions WHERE SessionType = ?
                )
            ORDER BY dp.Date ASC
        """
        return db.query(sql, (days, session_type))
    else:
        sql = """
            SELECT 
                Date,
                EndingEquity as PortfolioValue,
                CumulativePnL
            FROM dbo.DailyPerformance
            WHERE Date >= DATEADD(day, -?, GETDATE())
            ORDER BY Date ASC
        """
        return db.query(sql, (days,))


def get_drawdown_analysis(days: int = 365, session_type: Optional[str] = None) -> pd.DataFrame:
    """Get drawdown analysis data.
    
    Args:
        days: Number of days to look back
        session_type: Optional session type filter (BACKTEST, PAPER, LIVE)
                     If None, uses session_state data_source
    """
    db = get_db_connection()
    
    # Use provided session_type or get from session state
    if session_type is None:
        session_type = get_session_type_filter()
    
    if session_type:
        sql = """
            WITH EquityCurve AS (
                SELECT 
                    dp.Date,
                    dp.EndingEquity as PortfolioValue,
                    MAX(dp.EndingEquity) OVER (ORDER BY dp.Date ROWS UNBOUNDED PRECEDING) as PeakValue
                FROM dbo.DailyPerformance dp
                WHERE dp.Date >= DATEADD(day, -?, GETDATE())
                    AND dp.SessionId IN (
                        SELECT SessionId FROM dbo.Sessions WHERE SessionType = ?
                    )
            )
            SELECT 
                Date,
                PortfolioValue,
                PeakValue,
                (PortfolioValue - PeakValue) / PeakValue * 100 as DrawdownPercent
            FROM EquityCurve
            ORDER BY Date ASC
        """
        return db.query(sql, (days, session_type))
    else:
        sql = """
            WITH EquityCurve AS (
                SELECT 
                    Date,
                    EndingEquity as PortfolioValue,
                    MAX(EndingEquity) OVER (ORDER BY Date ROWS UNBOUNDED PRECEDING) as PeakValue
                FROM dbo.DailyPerformance
                WHERE Date >= DATEADD(day, -?, GETDATE())
            )
            SELECT 
                Date,
                PortfolioValue,
                PeakValue,
                (PortfolioValue - PeakValue) / PeakValue * 100 as DrawdownPercent
            FROM EquityCurve
            ORDER BY Date ASC
        """
        return db.query(sql, (days,))


# ==================== Regime Queries ====================

def get_market_regimes(days: int = 90) -> pd.DataFrame:
    """Get market regime data."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            Date as Timestamp,
            'QQQ' as Symbol,
            Regime, 
            Confidence,
            QQQ_Close as RSI,
            EMA_Spread as Momentum,
            QQQ_ATR as Volatility,
            TrendStrength
        FROM dbo.MarketRegimes
        WHERE Date >= DATEADD(day, -?, GETDATE())
        ORDER BY Date ASC
    """
    
    return db.query(sql, (days,))


def get_regime_performance(days: int = 90, session_type: Optional[str] = None) -> pd.DataFrame:
    """Get performance by market regime.
    
    Args:
        days: Number of days to look back
        session_type: Optional session type filter (BACKTEST, PAPER, LIVE)
                     If None, uses session_state data_source
    """
    db = get_db_connection()
    
    # Use provided session_type or get from session state
    if session_type is None:
        session_type = get_session_type_filter()
    
    # Note: MarketRegime column doesn't exist in Trades table yet
    # This query will return empty until the column is added
    if session_type:
        sql = """
            SELECT 
                'N/A' as MarketRegime,
                COUNT(*) as TradeCount,
                SUM(CASE WHEN t.NetPnL > 0 THEN 1 ELSE 0 END) as Wins,
                SUM(t.NetPnL) as TotalPnL,
                AVG(t.NetPnL) as AvgPnL,
                CAST(SUM(CASE WHEN t.NetPnL > 0 THEN 1 ELSE 0 END) AS FLOAT) / 
                    NULLIF(COUNT(*), 0) * 100 as WinRate
            FROM dbo.Trades t
            INNER JOIN dbo.Sessions s ON t.SessionId = s.SessionId
            WHERE t.EntryTime >= DATEADD(day, -?, GETDATE())
                AND s.SessionType = ?
        """
        return db.query(sql, (days, session_type))
    else:
        sql = """
            SELECT 
                'N/A' as MarketRegime,
                COUNT(*) as TradeCount,
                SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) as Wins,
                SUM(NetPnL) as TotalPnL,
                AVG(NetPnL) as AvgPnL,
                CAST(SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) AS FLOAT) / 
                    NULLIF(COUNT(*), 0) * 100 as WinRate
            FROM dbo.Trades
            WHERE EntryTime >= DATEADD(day, -?, GETDATE())
        """
        return db.query(sql, (days,))


# ==================== Learning Queries ====================

def get_learning_history(days: int = 30) -> pd.DataFrame:
    """Get learning history data."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            LearningId as LearningID,
            CreatedAt as Timestamp,
            PatternType as LearningType,
            Description,
            NULL as OldValue,
            PatternData as NewValue,
            Confidence as ConfidenceScore,
            COALESCE(JSON_VALUE(Metadata, '$.source'), 'system') as Source
        FROM dbo.LearningStore
        WHERE CreatedAt >= DATEADD(day, -?, GETDATE())
        ORDER BY CreatedAt DESC
    """
    
    return db.query(sql, (days,))


def get_optimal_parameters() -> pd.DataFrame:
    """Get optimal parameter recommendations."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            OptParamId as ParameterID,
            StrategyId as ParameterName,
            ExpectedSharpe as CurrentValue,
            ExpectedWinRate as OptimalValue,
            ConfidenceScore,
            LastUpdated,
            BasedOnBacktests as SampleSize,
            ExpectedDrawdown as ExpectedImprovement,
            MarketRegime
        FROM dbo.OptimalParameters
        WHERE IsActive = 1
        ORDER BY ConfidenceScore DESC
    """
    
    return db.query(sql)


def get_parameter_performance() -> pd.DataFrame:
    """Get parameter performance comparison."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            ParamName as ParameterName, 
            ParamValue as ParameterValue, 
            MarketRegime,
            SampleCount as TradeCount, 
            AvgWinRate as WinRate, 
            AvgReturn as AvgPnL, 
            AvgReturn * SampleCount as TotalPnL,
            AvgSharpeRatio as SharpeRatio, 
            AvgMaxDrawdown as MaxDrawdown, 
            LastUpdated as FirstUsed, 
            LastUpdated as LastUsed
        FROM dbo.ParameterPerformance
        ORDER BY ParamName, ParamValue
    """
    
    return db.query(sql)


# ==================== Backtest Queries ====================

def get_backtest_runs(limit: int = 20) -> pd.DataFrame:
    """Get recent backtest runs."""
    db = get_db_connection()
    
    sql = f"""
        SELECT TOP {limit}
            RunID, StartTime, EndTime, Status,
            AlgorithmName, BacktestStartDate, BacktestEndDate,
            InitialCapital
        FROM dbo.BacktestRuns
        ORDER BY StartTime DESC
    """
    
    return db.query(sql)


def get_backtest_metrics(run_id: str) -> pd.DataFrame:
    """Get metrics for a specific backtest run."""
    db = get_db_connection()
    
    sql = """
        SELECT *
        FROM dbo.BacktestMetrics
        WHERE RunID = ?
    """
    
    return db.query(sql, (run_id,))


# ==================== System Queries ====================

def get_current_parameters() -> pd.DataFrame:
    """Get current algorithm parameters."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            ParameterId as ParameterID, 
            AlgorithmName,
            ParamName as ParameterName, 
            ParamValue as ParameterValue,
            ParamType as DataType, 
            IsActive,
            CreatedAt as LastModified,
            'System' as ModifiedBy
        FROM dbo.Parameters
        WHERE IsActive = 1
        ORDER BY AlgorithmName, ParamName
    """
    
    return db.query(sql)


def get_audit_log(days: int = 7) -> pd.DataFrame:
    """Get recent audit log entries."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            LogId as LogID,
            Timestamp,
            EventType as Operation,
            Message as Details,
            Source as UserAgent,
            CASE WHEN Severity = 'ERROR' THEN 0 ELSE 1 END as Success,
            CASE WHEN Severity = 'ERROR' THEN Message ELSE NULL END as ErrorMessage
        FROM dbo.AuditLog
        WHERE Timestamp >= DATEADD(day, -?, GETDATE())
        ORDER BY Timestamp DESC
    """
    
    return db.query(sql, (days,))


def check_database_health() -> dict:
    """Check database connection health."""
    db = get_db_connection()
    
    health = {
        "connected": db.is_connected,
        "tables": {},
        "last_trade": None,
        "last_regime": None,
    }
    
    if not db.is_connected:
        return health
    
    # Check table row counts
    tables = ["Trades", "DailyPerformance", "MarketRegimes", "LearningStore", "Parameters"]
    for table in tables:
        try:
            df = db.query(f"SELECT COUNT(*) as cnt FROM dbo.{table}")
            health["tables"][table] = df.iloc[0]["cnt"] if not df.empty else 0
        except:
            health["tables"][table] = -1
    
    # Get last trade time
    try:
        df = db.query("SELECT MAX(EntryTime) as LastTrade FROM dbo.Trades")
        if not df.empty and df.iloc[0]["LastTrade"]:
            health["last_trade"] = df.iloc[0]["LastTrade"]
    except:
        pass
    
    # Get last regime detection time
    try:
        df = db.query("SELECT MAX(Date) as LastRegime FROM dbo.MarketRegimes")
        if not df.empty and df.iloc[0]["LastRegime"]:
            health["last_regime"] = df.iloc[0]["LastRegime"]
    except:
        pass
    
    return health


# ==================== Webhook Event Queries ====================

def get_webhook_events(session_id: str, limit: int = 100) -> pd.DataFrame:
    """Get webhook events for a backtest session."""
    db = get_db_connection()
    
    # Try to get from WebhookEvents table first
    sql = f"""
        SELECT TOP {limit}
            EventId,
            SessionId,
            Timestamp,
            WebhookType,
            Symbol,
            TriggerReason,
            Price,
            MarketData,
            Conditions
        FROM dbo.WebhookEvents
        WHERE SessionId = ?
        ORDER BY Timestamp DESC
    """
    
    try:
        df = db.query(sql, (session_id,))
        if not df.empty:
            return df
    except Exception:
        # Table might not exist yet
        pass
    
    return pd.DataFrame()


def store_webhook_event(
    session_id: str,
    timestamp: str,
    webhook_type: str,
    symbol: str,
    trigger_reason: str,
    price: float,
    market_data: str,
    conditions: str
) -> bool:
    """Store a webhook event in the database."""
    db = get_db_connection()
    
    sql = """
        INSERT INTO dbo.WebhookEvents 
        (SessionId, Timestamp, WebhookType, Symbol, TriggerReason, Price, MarketData, Conditions)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    try:
        return db.execute(sql, (session_id, timestamp, webhook_type, symbol, trigger_reason, price, market_data, conditions))
    except Exception:
        return False


# ==================== Backtest Session Queries ====================

def create_backtest_session(
    session_id: str,
    algorithm_name: str,
    start_date: str,
    end_date: str,
    initial_cash: float,
    parameters: str
) -> bool:
    """Create a new backtest session record."""
    db = get_db_connection()
    
    sql = """
        INSERT INTO dbo.Sessions 
        (SessionId, SessionType, AlgorithmName, StartTime, Status, InitialCash, Parameters)
        VALUES (?, 'BACKTEST', ?, GETDATE(), 'RUNNING', ?, ?)
    """
    
    try:
        return db.execute(sql, (session_id, algorithm_name, initial_cash, parameters))
    except Exception as e:
        import streamlit as st
        st.error(f"Failed to create session: {e}")
        return False


def update_backtest_session_status(session_id: str, status: str, final_equity: float = None) -> bool:
    """Update backtest session status."""
    db = get_db_connection()
    
    if final_equity:
        sql = """
            UPDATE dbo.Sessions 
            SET Status = ?, EndTime = GETDATE(), FinalEquity = ?
            WHERE SessionId = ?
        """
        return db.execute(sql, (status, final_equity, session_id))
    else:
        sql = """
            UPDATE dbo.Sessions 
            SET Status = ?, EndTime = GETDATE()
            WHERE SessionId = ?
        """
        return db.execute(sql, (status, session_id))


def get_backtest_sessions(limit: int = 20) -> pd.DataFrame:
    """Get recent backtest sessions."""
    db = get_db_connection()
    
    sql = f"""
        SELECT TOP {limit}
            s.SessionId as RunID,
            s.StrategyId as AlgorithmName,
            s.Status,
            s.StartTime,
            s.EndTime,
            s.TotalReturn as InitialCapital,
            s.TotalReturn as FinalEquity,
            s.ParametersJson as Parameters,
            s.TotalTrades
        FROM dbo.Sessions s
        WHERE s.SessionType = 'BACKTEST'
        ORDER BY s.StartTime DESC
    """
    
    try:
        return db.query(sql)
    except Exception:
        return pd.DataFrame()


# ==================== Optimization Results Queries ====================

def get_optimization_runs(limit: int = 50) -> pd.DataFrame:
    """Get recent optimization runs."""
    db = get_db_connection()
    
    sql = f"""
        SELECT TOP {limit}
            RunId,
            StartTime,
            EndTime,
            TotalCombinations,
            CompletedCombinations,
            Status,
            SourceFile,
            DATEDIFF(MINUTE, StartTime, ISNULL(EndTime, GETDATE())) as DurationMinutes
        FROM OptimizationRuns
        ORDER BY StartTime DESC
    """
    
    try:
        return db.query(sql)
    except Exception:
        return pd.DataFrame()


def get_optimization_results(
    run_id: Optional[str] = None,
    min_sharpe: Optional[float] = None,
    max_drawdown: Optional[float] = None,
    min_trades: Optional[int] = None,
    min_win_rate: Optional[float] = None,
    limit: int = 500
) -> pd.DataFrame:
    """
    Get optimization results with filtering.
    
    Args:
        run_id: Filter by optimization run ID
        min_sharpe: Minimum Sharpe ratio
        max_drawdown: Maximum drawdown (as positive decimal, e.g., 0.10 for 10%)
        min_trades: Minimum number of trades
        min_win_rate: Minimum win rate (as decimal, e.g., 0.5 for 50%)
        limit: Maximum results to return
    """
    db = get_db_connection()
    
    conditions = ["1=1"]
    params: list = []
    
    if run_id:
        conditions.append("b.OptimizationRunId = ?")
        params.append(run_id)
    
    if min_sharpe is not None:
        conditions.append("b.SharpeRatio >= ?")
        params.append(min_sharpe)
    
    if max_drawdown is not None:
        conditions.append("ABS(b.MaxDrawdown) <= ?")
        params.append(max_drawdown)
    
    if min_trades is not None:
        conditions.append("b.TotalTrades >= ?")
        params.append(min_trades)
    
    if min_win_rate is not None:
        conditions.append("b.WinRate >= ?")
        params.append(min_win_rate)
    
    where_clause = " AND ".join(conditions)
    
    sql = f"""
        SELECT TOP {limit}
            b.BacktestId,
            b.StrategyId,
            b.StartDate,
            b.EndDate,
            b.TotalReturn,
            b.SharpeRatio,
            b.MaxDrawdown,
            b.TotalTrades,
            b.WinRate,
            b.ProfitFactor,
            b.ParametersJson,
            b.OptimizationRunId,
            b.CreatedAt,
            -- Extract individual parameters from JSON
            TRY_CAST(CAST(JSON_VALUE(b.ParametersJson, '$.rsi_period') AS FLOAT) AS INT) as rsi_period,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.rsi_oversold') AS FLOAT) as rsi_oversold,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.rsi_overbought') AS FLOAT) as rsi_overbought,
            TRY_CAST(CAST(JSON_VALUE(b.ParametersJson, '$.bb_period') AS FLOAT) AS INT) as bb_period,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.bb_std_dev') AS FLOAT) as bb_std_dev,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.stop_loss_pct') AS FLOAT) as stop_loss_pct,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.take_profit_pct') AS FLOAT) as take_profit_pct,
            JSON_VALUE(b.ParametersJson, '$._hash') as combination_hash
        FROM BacktestOutcomes b
        WHERE {where_clause}
        ORDER BY b.SharpeRatio DESC, b.TotalReturn DESC
    """
    
    try:
        return db.query(sql, tuple(params))
    except Exception as e:
        import streamlit as st
        st.error(f"Query failed: {e}")
        return pd.DataFrame()


def get_parameter_impact_analysis(
    param_name: str,
    run_id: Optional[str] = None
) -> pd.DataFrame:
    """
    Analyze how a specific parameter impacts performance.
    
    Groups results by parameter value and calculates aggregate metrics.
    """
    db = get_db_connection()
    
    # Map parameter names to JSON paths
    param_map = {
        'rsi_period': 'rsi_period',
        'rsi_oversold': 'rsi_oversold',
        'rsi_overbought': 'rsi_overbought',
        'bb_period': 'bb_period',
        'bb_std_dev': 'bb_std_dev',
        'stop_loss_pct': 'stop_loss_pct',
        'take_profit_pct': 'take_profit_pct',
        'ema_fast_period': 'ema_fast_period',
        'ema_slow_period': 'ema_slow_period',
    }
    
    if param_name not in param_map:
        return pd.DataFrame()
    
    json_path = f'$.{param_map[param_name]}'
    
    run_filter = ""
    params: list = []
    if run_id:
        run_filter = "AND b.OptimizationRunId = ?"
        params.append(run_id)
    
    sql = f"""
        SELECT 
            TRY_CAST(JSON_VALUE(b.ParametersJson, '{json_path}') AS FLOAT) as ParamValue,
            COUNT(*) as SampleCount,
            AVG(b.TotalReturn) as AvgReturn,
            AVG(b.SharpeRatio) as AvgSharpe,
            AVG(b.WinRate) as AvgWinRate,
            AVG(ABS(b.MaxDrawdown)) as AvgDrawdown,
            AVG(b.TotalTrades) as AvgTrades,
            AVG(b.ProfitFactor) as AvgProfitFactor,
            MIN(b.TotalReturn) as MinReturn,
            MAX(b.TotalReturn) as MaxReturn,
            MIN(b.SharpeRatio) as MinSharpe,
            MAX(b.SharpeRatio) as MaxSharpe
        FROM BacktestOutcomes b
        WHERE JSON_VALUE(b.ParametersJson, '{json_path}') IS NOT NULL
            {run_filter}
        GROUP BY TRY_CAST(JSON_VALUE(b.ParametersJson, '{json_path}') AS FLOAT)
        ORDER BY AvgSharpe DESC
    """
    
    try:
        return db.query(sql, tuple(params))
    except Exception as e:
        import streamlit as st
        st.error(f"Parameter impact query failed: {e}")
        return pd.DataFrame()


def get_top_parameter_combinations(
    top_n: int = 10,
    metric: str = "sharpe",
    run_id: Optional[str] = None
) -> pd.DataFrame:
    """
    Get top performing parameter combinations.
    
    Args:
        top_n: Number of top combinations to return
        metric: Sort by 'sharpe', 'return', 'win_rate', or 'profit_factor'
        run_id: Filter by optimization run ID
    """
    db = get_db_connection()
    
    metric_map = {
        'sharpe': 'SharpeRatio',
        'return': 'TotalReturn',
        'win_rate': 'WinRate',
        'profit_factor': 'ProfitFactor'
    }
    
    order_col = metric_map.get(metric, 'SharpeRatio')
    
    run_filter = ""
    params: list = []
    if run_id:
        run_filter = "WHERE b.OptimizationRunId = ?"
        params.append(run_id)
    
    sql = f"""
        SELECT TOP {top_n}
            b.BacktestId,
            b.TotalReturn,
            b.SharpeRatio,
            b.MaxDrawdown,
            b.WinRate,
            b.TotalTrades,
            b.ProfitFactor,
            b.ParametersJson,
            TRY_CAST(CAST(JSON_VALUE(b.ParametersJson, '$.rsi_period') AS FLOAT) AS INT) as rsi_period,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.rsi_oversold') AS FLOAT) as rsi_oversold,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.rsi_overbought') AS FLOAT) as rsi_overbought,
            TRY_CAST(CAST(JSON_VALUE(b.ParametersJson, '$.bb_period') AS FLOAT) AS INT) as bb_period,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.bb_std_dev') AS FLOAT) as bb_std_dev,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.stop_loss_pct') AS FLOAT) as stop_loss_pct
        FROM BacktestOutcomes b
        {run_filter}
        ORDER BY b.{order_col} DESC
    """
    
    try:
        return db.query(sql, tuple(params))
    except Exception as e:
        import streamlit as st
        st.error(f"Top combinations query failed: {e}")
        return pd.DataFrame()


def get_parameter_heatmap_data(
    param1: str,
    param2: str,
    metric: str = "sharpe",
    run_id: Optional[str] = None
) -> pd.DataFrame:
    """
    Get data for parameter heatmap visualization.
    
    Returns a pivot-ready DataFrame with param1 x param2 and metric values.
    """
    db = get_db_connection()
    
    param_map = {
        'rsi_period': 'rsi_period',
        'rsi_oversold': 'rsi_oversold',
        'rsi_overbought': 'rsi_overbought',
        'bb_period': 'bb_period',
        'bb_std_dev': 'bb_std_dev',
        'stop_loss_pct': 'stop_loss_pct',
        'take_profit_pct': 'take_profit_pct',
    }
    
    if param1 not in param_map or param2 not in param_map:
        return pd.DataFrame()
    
    metric_map = {
        'sharpe': 'SharpeRatio',
        'return': 'TotalReturn',
        'win_rate': 'WinRate',
        'drawdown': 'MaxDrawdown'
    }
    
    metric_col = metric_map.get(metric, 'SharpeRatio')
    
    run_filter = ""
    params: list = []
    if run_id:
        run_filter = "AND b.OptimizationRunId = ?"
        params.append(run_id)
    
    sql = f"""
        SELECT 
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.{param_map[param1]}') AS FLOAT) as {param1},
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.{param_map[param2]}') AS FLOAT) as {param2},
            AVG(b.{metric_col}) as {metric}
        FROM BacktestOutcomes b
        WHERE JSON_VALUE(b.ParametersJson, '$.{param_map[param1]}') IS NOT NULL
            AND JSON_VALUE(b.ParametersJson, '$.{param_map[param2]}') IS NOT NULL
            {run_filter}
        GROUP BY 
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.{param_map[param1]}') AS FLOAT),
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.{param_map[param2]}') AS FLOAT)
        ORDER BY {param1}, {param2}
    """
    
    try:
        return db.query(sql, tuple(params))
    except Exception as e:
        import streamlit as st
        st.error(f"Heatmap query failed: {e}")
        return pd.DataFrame()


def get_optimization_summary(run_id: Optional[str] = None) -> dict:
    """Get summary statistics for optimization results."""
    db = get_db_connection()
    
    run_filter = ""
    params: list = []
    if run_id:
        run_filter = "WHERE b.OptimizationRunId = ?"
        params.append(run_id)
    
    sql = f"""
        SELECT 
            COUNT(*) as total_backtests,
            AVG(b.TotalReturn) as avg_return,
            MAX(b.TotalReturn) as best_return,
            MIN(b.TotalReturn) as worst_return,
            AVG(b.SharpeRatio) as avg_sharpe,
            MAX(b.SharpeRatio) as best_sharpe,
            AVG(b.WinRate) as avg_win_rate,
            MAX(b.WinRate) as best_win_rate,
            AVG(ABS(b.MaxDrawdown)) as avg_drawdown,
            MIN(ABS(b.MaxDrawdown)) as best_drawdown,
            SUM(b.TotalTrades) as total_trades,
            COUNT(CASE WHEN b.TotalReturn > 0 THEN 1 END) as profitable_runs,
            COUNT(CASE WHEN b.SharpeRatio > 0.1 THEN 1 END) as good_sharpe_runs
        FROM BacktestOutcomes b
        {run_filter}
    """
    
    try:
        df = db.query(sql, tuple(params))
        if df.empty:
            return {}
        return df.iloc[0].to_dict()
    except Exception:
        return {}
