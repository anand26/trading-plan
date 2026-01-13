"""
Database connection and query utilities for the trading dashboard.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import streamlit as st

try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

from .config import db_config


class DatabaseConnection:
    """SQL Server database connection manager."""
    
    def __init__(self):
        self._connection: Optional["pyodbc.Connection"] = None
    
    def connect(self) -> bool:
        """Establish database connection."""
        if not PYODBC_AVAILABLE:
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
        
        if not self.is_connected:
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
        
        if not self.is_connected:
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

def get_trades(
    days: int = 30,
    symbol: Optional[str] = None,
    limit: int = 1000
) -> pd.DataFrame:
    """Get recent trades."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            TradeID, Symbol, EntryTime, ExitTime, Side,
            EntryPrice, ExitPrice, Quantity, PnL, PnLPercent,
            Commission, Slippage, HoldingPeriodSeconds,
            EntryReason, ExitReason, MarketRegime
        FROM dbo.Trades
        WHERE EntryTime >= DATEADD(day, -?, GETDATE())
    """
    params = [days]
    
    if symbol:
        sql += " AND Symbol = ?"
        params.append(symbol)
    
    sql += " ORDER BY EntryTime DESC"
    
    if limit:
        sql = f"SELECT TOP {limit} * FROM ({sql}) AS T ORDER BY EntryTime DESC"
    
    return db.query(sql, tuple(params))


def get_trade_summary(days: int = 30) -> dict:
    """Get trade summary statistics."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            COUNT(*) as TotalTrades,
            SUM(CASE WHEN PnL > 0 THEN 1 ELSE 0 END) as WinningTrades,
            SUM(CASE WHEN PnL < 0 THEN 1 ELSE 0 END) as LosingTrades,
            SUM(PnL) as TotalPnL,
            AVG(PnL) as AvgPnL,
            MAX(PnL) as MaxWin,
            MIN(PnL) as MaxLoss,
            AVG(CASE WHEN PnL > 0 THEN PnL END) as AvgWin,
            AVG(CASE WHEN PnL < 0 THEN PnL END) as AvgLoss,
            AVG(HoldingPeriodSeconds) as AvgHoldingSeconds
        FROM dbo.Trades
        WHERE EntryTime >= DATEADD(day, -?, GETDATE())
    """
    
    df = db.query(sql, (days,))
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


# ==================== Performance Queries ====================

def get_daily_performance(days: int = 90) -> pd.DataFrame:
    """Get daily performance data."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            Date, TotalTrades, WinningTrades, LosingTrades,
            GrossPnL, NetPnL, WinRate, ProfitFactor,
            MaxDrawdown, SharpeRatio, PortfolioValue
        FROM dbo.DailyPerformance
        WHERE Date >= DATEADD(day, -?, GETDATE())
        ORDER BY Date ASC
    """
    
    return db.query(sql, (days,))


def get_equity_curve(days: int = 365) -> pd.DataFrame:
    """Get equity curve data."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            Date,
            PortfolioValue,
            SUM(NetPnL) OVER (ORDER BY Date) as CumulativePnL
        FROM dbo.DailyPerformance
        WHERE Date >= DATEADD(day, -?, GETDATE())
        ORDER BY Date ASC
    """
    
    return db.query(sql, (days,))


def get_drawdown_analysis(days: int = 365) -> pd.DataFrame:
    """Get drawdown analysis data."""
    db = get_db_connection()
    
    sql = """
        WITH EquityCurve AS (
            SELECT 
                Date,
                PortfolioValue,
                MAX(PortfolioValue) OVER (ORDER BY Date ROWS UNBOUNDED PRECEDING) as PeakValue
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
            Timestamp, Symbol, Regime, Confidence,
            RSI, Momentum, Volatility, TrendStrength
        FROM dbo.MarketRegimes
        WHERE Timestamp >= DATEADD(day, -?, GETDATE())
        ORDER BY Timestamp ASC
    """
    
    return db.query(sql, (days,))


def get_regime_performance(days: int = 90) -> pd.DataFrame:
    """Get performance by market regime."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            MarketRegime,
            COUNT(*) as TradeCount,
            SUM(CASE WHEN PnL > 0 THEN 1 ELSE 0 END) as Wins,
            SUM(PnL) as TotalPnL,
            AVG(PnL) as AvgPnL,
            CAST(SUM(CASE WHEN PnL > 0 THEN 1 ELSE 0 END) AS FLOAT) / 
                NULLIF(COUNT(*), 0) * 100 as WinRate
        FROM dbo.Trades
        WHERE EntryTime >= DATEADD(day, -?, GETDATE())
            AND MarketRegime IS NOT NULL
        GROUP BY MarketRegime
        ORDER BY TotalPnL DESC
    """
    
    return db.query(sql, (days,))


# ==================== Learning Queries ====================

def get_learning_history(days: int = 30) -> pd.DataFrame:
    """Get learning history data."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            LearningID, Timestamp, LearningType, Description,
            OldValue, NewValue, ConfidenceScore, Source
        FROM dbo.LearningStore
        WHERE Timestamp >= DATEADD(day, -?, GETDATE())
        ORDER BY Timestamp DESC
    """
    
    return db.query(sql, (days,))


def get_optimal_parameters() -> pd.DataFrame:
    """Get optimal parameter recommendations."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            ParameterID, ParameterName, CurrentValue, OptimalValue,
            ConfidenceScore, LastUpdated, SampleSize, 
            ExpectedImprovement, MarketRegime
        FROM dbo.OptimalParameters
        ORDER BY ConfidenceScore DESC
    """
    
    return db.query(sql)


def get_parameter_performance() -> pd.DataFrame:
    """Get parameter performance comparison."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            ParameterName, ParameterValue, MarketRegime,
            TradeCount, WinRate, AvgPnL, TotalPnL,
            SharpeRatio, MaxDrawdown, FirstUsed, LastUsed
        FROM dbo.ParameterPerformance
        ORDER BY ParameterName, ParameterValue
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
            ParameterID, ParameterName, ParameterValue,
            DataType, Description, LastModified, ModifiedBy
        FROM dbo.Parameters
        ORDER BY ParameterName
    """
    
    return db.query(sql)


def get_audit_log(days: int = 7) -> pd.DataFrame:
    """Get recent audit log entries."""
    db = get_db_connection()
    
    sql = """
        SELECT 
            LogID, Timestamp, Operation, Details,
            UserAgent, Success, ErrorMessage
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
        df = db.query("SELECT MAX(Timestamp) as LastRegime FROM dbo.MarketRegimes")
        if not df.empty and df.iloc[0]["LastRegime"]:
            health["last_regime"] = df.iloc[0]["LastRegime"]
    except:
        pass
    
    return health
