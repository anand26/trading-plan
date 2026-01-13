"""
Database Module
===============
SQL Server database operations for Trade-Mind MCP analytics.
"""

import logging
from datetime import datetime, date, timedelta
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


class AnalyticsDatabase:
    """
    SQL Server database interface for Trade-Mind MCP analytics.
    
    Provides read access to:
    - Trade history and statistics
    - Daily performance data
    - Market regime information
    - Parameter performance metrics
    - Learning store
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
            logger.info("Connected to TradingDB for analytics")
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
    # TRADE QUERIES
    # ============================================
    
    def get_last_trades(
        self,
        symbol: Optional[str] = None,
        count: int = 20,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent trades with optional filters."""
        try:
            with self.cursor() as cursor:
                query = """
                    SELECT TOP (?)
                        TradeId, SessionId, Symbol, Side, Quantity,
                        EntryPrice, ExitPrice, RealizedPnL, RealizedPnLPct,
                        EntryTime, ExitTime, EntryReason, ExitReason,
                        HoldingPeriodSeconds
                    FROM Trades
                    WHERE 1=1
                """
                params = [count]
                
                if symbol:
                    query += " AND Symbol = ?"
                    params.append(symbol)
                if session_id:
                    query += " AND SessionId = ?"
                    params.append(session_id)
                
                query += " ORDER BY ExitTime DESC"
                
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get trades: {e}")
            return []
    
    def get_trades_in_range(
        self,
        start_date: date,
        end_date: date,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get trades within date range."""
        try:
            with self.cursor() as cursor:
                query = """
                    SELECT 
                        TradeId, SessionId, Symbol, Side, Quantity,
                        EntryPrice, ExitPrice, RealizedPnL, RealizedPnLPct,
                        EntryTime, ExitTime, EntryReason, ExitReason,
                        HoldingPeriodSeconds
                    FROM Trades
                    WHERE CAST(ExitTime AS DATE) BETWEEN ? AND ?
                """
                params = [start_date, end_date]
                
                if symbol:
                    query += " AND Symbol = ?"
                    params.append(symbol)
                
                query += " ORDER BY ExitTime"
                
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get trades in range: {e}")
            return []
    
    # ============================================
    # STATISTICS QUERIES
    # ============================================
    
    def calculate_win_rate(
        self,
        symbol: Optional[str] = None,
        session_id: Optional[str] = None,
        days_back: Optional[int] = None
    ) -> Dict[str, Any]:
        """Calculate win rate and related statistics."""
        try:
            with self.cursor() as cursor:
                query = """
                    SELECT 
                        COUNT(*) as TotalTrades,
                        SUM(CASE WHEN RealizedPnL > 0 THEN 1 ELSE 0 END) as WinningTrades,
                        SUM(CASE WHEN RealizedPnL < 0 THEN 1 ELSE 0 END) as LosingTrades,
                        SUM(CASE WHEN RealizedPnL = 0 THEN 1 ELSE 0 END) as BreakEvenTrades,
                        SUM(RealizedPnL) as TotalPnL,
                        AVG(RealizedPnL) as AvgPnL,
                        AVG(CASE WHEN RealizedPnL > 0 THEN RealizedPnL END) as AvgWin,
                        AVG(CASE WHEN RealizedPnL < 0 THEN RealizedPnL END) as AvgLoss,
                        MAX(RealizedPnL) as MaxWin,
                        MIN(RealizedPnL) as MaxLoss,
                        AVG(HoldingPeriodSeconds) as AvgDuration
                    FROM Trades
                    WHERE ExitTime IS NOT NULL
                """
                params = []
                
                if symbol:
                    query += " AND Symbol = ?"
                    params.append(symbol)
                if session_id:
                    query += " AND SessionId = ?"
                    params.append(session_id)
                if days_back:
                    query += " AND ExitTime >= DATEADD(day, ?, GETDATE())"
                    params.append(-days_back)
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if not row or row[0] == 0:
                    return {
                        "success": False,
                        "error": "No trades found",
                        "data_quality": "INSUFFICIENT_DATA"
                    }
                
                total = row[0]
                wins = row[1] or 0
                losses = row[2] or 0
                avg_win = row[6] or 0
                avg_loss = abs(row[7] or 1)  # Avoid division by zero
                
                win_rate = wins / total if total > 0 else 0
                profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
                
                min_trades = get_config().analysis.min_trades_for_stats
                data_quality = "STATISTICALLY_VALID" if total >= min_trades else "INSUFFICIENT_DATA"
                
                return {
                    "success": True,
                    "symbol": symbol or "ALL",
                    "total_trades": total,
                    "winning_trades": wins,
                    "losing_trades": losses,
                    "breakeven_trades": row[3] or 0,
                    "win_rate": win_rate,
                    "win_rate_pct": f"{win_rate:.1%}",
                    "total_pnl": float(row[4] or 0),
                    "avg_pnl": float(row[5] or 0),
                    "avg_win": float(avg_win),
                    "avg_loss": float(row[7] or 0),
                    "profit_factor": profit_factor,
                    "max_win": float(row[8] or 0),
                    "max_loss": float(row[9] or 0),
                    "avg_duration_seconds": int(row[10] or 0),
                    "data_quality": data_quality
                }
        except Exception as e:
            logger.error(f"Failed to calculate win rate: {e}")
            return {"success": False, "error": str(e)}
    
    # ============================================
    # DAILY PERFORMANCE
    # ============================================
    
    def get_daily_pnl(
        self,
        days_back: int = 30,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get daily P&L breakdown."""
        try:
            with self.cursor() as cursor:
                query = """
                    SELECT 
                        TradingDate,
                        SessionId,
                        OpeningBalance,
                        ClosingBalance,
                        RealizedPnL,
                        TradeCount,
                        WinCount,
                        LossCount
                    FROM DailyPerformance
                    WHERE TradingDate >= DATEADD(day, ?, GETDATE())
                """
                params = [-days_back]
                
                if session_id:
                    query += " AND SessionId = ?"
                    params.append(session_id)
                
                query += " ORDER BY TradingDate DESC"
                
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get daily P&L: {e}")
            return []
    
    def get_equity_curve(
        self,
        session_id: Optional[str] = None,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """Get equity curve data."""
        try:
            with self.cursor() as cursor:
                query = """
                    SELECT 
                        TradingDate,
                        ClosingBalance as Equity
                    FROM DailyPerformance
                    WHERE TradingDate >= DATEADD(day, ?, GETDATE())
                """
                params = [-days_back]
                
                if session_id:
                    query += " AND SessionId = ?"
                    params.append(session_id)
                
                query += " ORDER BY TradingDate"
                
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get equity curve: {e}")
            return []
    
    # ============================================
    # MARKET REGIME
    # ============================================
    
    def get_current_regime(self, symbol: str = "QQQ") -> Dict[str, Any]:
        """Get current market regime."""
        try:
            with self.cursor() as cursor:
                cursor.execute("""
                    SELECT TOP 1
                        RegimeId, Symbol, RegimeType, StartTime, 
                        TrendDirection, Volatility, Confidence
                    FROM MarketRegimes
                    WHERE Symbol = ? AND EndTime IS NULL
                    ORDER BY StartTime DESC
                """, (symbol,))
                
                row = cursor.fetchone()
                if row:
                    columns = [col[0] for col in cursor.description]
                    return {"success": True, "regime": dict(zip(columns, row))}
                else:
                    return {
                        "success": True,
                        "regime": {
                            "RegimeType": "UNKNOWN",
                            "TrendDirection": "NEUTRAL",
                            "Volatility": "NORMAL",
                            "Confidence": 0.5
                        },
                        "note": "No regime data available"
                    }
        except Exception as e:
            logger.error(f"Failed to get current regime: {e}")
            return {"success": False, "error": str(e)}
    
    def get_regime_history(
        self,
        symbol: str = "QQQ",
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """Get regime change history."""
        try:
            with self.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        RegimeId, Symbol, RegimeType, StartTime, EndTime,
                        TrendDirection, Volatility, Confidence,
                        DATEDIFF(hour, StartTime, ISNULL(EndTime, GETDATE())) as DurationHours
                    FROM MarketRegimes
                    WHERE Symbol = ? 
                      AND StartTime >= DATEADD(day, ?, GETDATE())
                    ORDER BY StartTime DESC
                """, (symbol, -days_back))
                
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get regime history: {e}")
            return []
    
    # ============================================
    # PARAMETER PERFORMANCE
    # ============================================
    
    def get_parameter_performance(
        self,
        param_name: str,
        market_regime: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get performance by parameter value."""
        try:
            with self.cursor() as cursor:
                query = """
                    SELECT 
                        ParamName, ParamValue, MarketRegime,
                        TradeCount, WinRate, AvgPnLWhenUsed,
                        SharpeRatio, MaxDrawdown, AvgHoldingTime,
                        LastUpdated
                    FROM ParameterPerformance
                    WHERE ParamName = ?
                """
                params = [param_name]
                
                if market_regime:
                    query += " AND (MarketRegime = ? OR MarketRegime = 'ALL')"
                    params.append(market_regime)
                
                query += " ORDER BY WinRate DESC, AvgPnLWhenUsed DESC"
                
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get parameter performance: {e}")
            return []
    
    def get_optimal_parameters(
        self,
        strategy_id: str = "TQQQ_SCALPING",
        market_regime: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get optimal parameters for strategy/regime."""
        try:
            with self.cursor() as cursor:
                query = """
                    SELECT 
                        StrategyId, ParamName, MarketRegime,
                        OptimalValue, ConfidenceScore, SampleSize,
                        ExpectedSharpe, ExpectedReturn, ExpectedDrawdown,
                        LastCalculated
                    FROM OptimalParameters
                    WHERE StrategyId = ?
                """
                params = [strategy_id]
                
                if market_regime:
                    query += " AND MarketRegime = ?"
                    params.append(market_regime)
                
                query += " ORDER BY ConfidenceScore DESC"
                
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get optimal parameters: {e}")
            return []
    
    # ============================================
    # LEARNING STORE
    # ============================================
    
    def record_learning(
        self,
        pattern_type: str,
        description: str,
        data: Dict[str, Any],
        confidence: float = 0.5
    ) -> bool:
        """Record a new learning/pattern."""
        try:
            with self.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO LearningStore (
                        PatternType, Description, PatternData, 
                        Confidence, CreatedAt
                    ) VALUES (?, ?, ?, ?, GETDATE())
                """, (pattern_type, description, str(data), confidence))
            logger.info(f"Recorded learning: {pattern_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to record learning: {e}")
            return False
    
    def get_learnings(
        self,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recorded learnings/patterns."""
        try:
            with self.cursor() as cursor:
                query = """
                    SELECT TOP (?)
                        LearningId, PatternType, Description,
                        PatternData, Confidence, CreatedAt
                    FROM LearningStore
                    WHERE Confidence >= ?
                """
                params = [limit, min_confidence]
                
                if pattern_type:
                    query += " AND PatternType = ?"
                    params.append(pattern_type)
                
                query += " ORDER BY CreatedAt DESC"
                
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get learnings: {e}")
            return []
    
    # ============================================
    # DRAWDOWN ANALYSIS
    # ============================================
    
    def analyze_drawdown(
        self,
        session_id: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Analyze drawdown metrics."""
        equity_data = self.get_equity_curve(session_id, days_back)
        
        if not equity_data:
            return {"success": False, "error": "No equity data available"}
        
        # Calculate drawdown series
        equities = [d["Equity"] for d in equity_data]
        dates = [d["TradingDate"] for d in equity_data]
        
        peak = equities[0]
        max_drawdown = 0
        max_drawdown_date = dates[0]
        current_drawdown = 0
        drawdown_start = None
        
        drawdowns = []
        for i, equity in enumerate(equities):
            if equity > peak:
                if current_drawdown > 0:
                    # Record recovered drawdown
                    drawdowns.append({
                        "start_date": drawdown_start,
                        "end_date": dates[i],
                        "depth": current_drawdown,
                        "recovered": True
                    })
                peak = equity
                current_drawdown = 0
                drawdown_start = None
            else:
                dd = (peak - equity) / peak if peak > 0 else 0
                if dd > current_drawdown:
                    current_drawdown = dd
                    if drawdown_start is None:
                        drawdown_start = dates[i]
                if dd > max_drawdown:
                    max_drawdown = dd
                    max_drawdown_date = dates[i]
        
        return {
            "success": True,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": f"{max_drawdown:.1%}",
            "max_drawdown_date": str(max_drawdown_date),
            "current_drawdown": current_drawdown,
            "current_drawdown_pct": f"{current_drawdown:.1%}",
            "drawdown_events": len(drawdowns),
            "avg_drawdown": sum(d["depth"] for d in drawdowns) / len(drawdowns) if drawdowns else 0,
            "drawdowns": drawdowns[:5]  # Last 5 drawdown events
        }


# Global database instance
_db: Optional[AnalyticsDatabase] = None


def get_db() -> AnalyticsDatabase:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = AnalyticsDatabase()
        _db.connect()
    return _db


def close_db():
    """Close the global database connection."""
    global _db
    if _db is not None:
        _db.disconnect()
        _db = None
