"""
Database connection and query utilities for the trading dashboard.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING
import streamlit as st

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
    """SQL Server database connection manager."""
    
    def __init__(self):
        from typing import Any
        self._connection: Any = None  # pyodbc.Connection
    
    def connect(self) -> bool:
        """Establish database connection."""
        if not PYODBC_AVAILABLE or pyodbc is None:
            st.error("pyodbc not installed")
            return False
        try:
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
            return pd.read_sql(sql, self._connection, params=params)
        except Exception as e:
            st.error(f"Query failed: {e}")
            return pd.DataFrame()
    
    def execute(self, sql: str, params: tuple = ()) -> bool:
        """Execute a non-query SQL statement."""
        if not self.is_connected:
            self.connect()
        
        if not self.is_connected or self._connection is None:
            return False
        
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, params)
            self._connection.commit()
            return True
        except Exception as e:
            st.error(f"Execution failed: {e}")
            return False


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
            s.SharpeRatio as FinalEquity,
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
