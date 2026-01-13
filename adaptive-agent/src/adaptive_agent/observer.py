"""
Observer Component - Market and Performance Monitoring

Gathers real-time data from multiple sources to create snapshots
of current market conditions and trading performance.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import pyodbc

from .config import AgentConfig
from .models import (
    MarketSnapshot,
    MarketRegime,
    PositionSnapshot,
    PerformanceSnapshot,
)


logger = logging.getLogger(__name__)


class Observer:
    """
    Monitors market conditions and trading performance.
    
    Responsibilities:
    - Gather market data (prices, indicators)
    - Track current positions
    - Calculate performance metrics
    - Detect market regime
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self._conn: Optional[pyodbc.Connection] = None
    
    def _get_connection(self) -> pyodbc.Connection:
        """Get or create database connection."""
        if self._conn is None or not self._is_connection_alive():
            self._conn = pyodbc.connect(
                self.config.database.connection_string,
                autocommit=True
            )
        return self._conn
    
    def _is_connection_alive(self) -> bool:
        """Check if the connection is still alive."""
        try:
            if self._conn is None:
                return False
            cursor = self._conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False
    
    def get_market_snapshot(self) -> MarketSnapshot:
        """
        Create a snapshot of current market conditions.
        
        Returns:
            MarketSnapshot with current prices, indicators, and regime.
        """
        snapshot = MarketSnapshot(timestamp=datetime.now())
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get latest prices from MarketData
            cursor.execute("""
                SELECT TOP 1 
                    Symbol, Price, Volume, RSI, Momentum, Volatility,
                    TrendStrength, MarketRegime
                FROM MarketData
                WHERE Symbol IN ('TQQQ', 'QQQ')
                ORDER BY Timestamp DESC
            """)
            
            for row in cursor.fetchall():
                symbol, price, volume, rsi, momentum, volatility, trend, regime = row
                if symbol == "TQQQ":
                    snapshot.tqqq_price = price
                    snapshot.rsi = rsi or 50.0
                    snapshot.momentum = momentum or 0.0
                    snapshot.volatility = volatility or 0.0
                    snapshot.trend_strength = trend or 0.0
                    if regime:
                        try:
                            snapshot.regime = MarketRegime(regime.upper())
                        except ValueError:
                            snapshot.regime = MarketRegime.NEUTRAL
                elif symbol == "QQQ":
                    snapshot.qqq_price = price
            
            # Get SQQQ if exists
            cursor.execute("""
                SELECT TOP 1 Price
                FROM MarketData
                WHERE Symbol = 'SQQQ'
                ORDER BY Timestamp DESC
            """)
            row = cursor.fetchone()
            if row:
                snapshot.sqqq_price = row[0]
            
            # Calculate regime confidence from recent accuracy
            cursor.execute("""
                SELECT AVG(CASE WHEN ActualReturn * PredictedDirection > 0 THEN 1.0 ELSE 0.0 END)
                FROM RegimePredictions
                WHERE PredictionDate >= DATEADD(day, -7, GETDATE())
                AND ActualReturn IS NOT NULL
            """)
            row = cursor.fetchone()
            if row and row[0]:
                snapshot.regime_confidence = float(row[0])
            
            cursor.close()
            
        except pyodbc.Error as e:
            logger.warning(f"Database error in get_market_snapshot: {e}")
        except Exception as e:
            logger.error(f"Error getting market snapshot: {e}")
        
        # Set time context
        now = datetime.now()
        snapshot.hour_of_day = now.hour
        snapshot.day_of_week = now.weekday()
        snapshot.is_market_open = self._is_market_open(now)
        
        return snapshot
    
    def get_positions(self) -> list[PositionSnapshot]:
        """
        Get current positions from the database.
        
        Returns:
            List of PositionSnapshot objects.
        """
        positions = []
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    Symbol,
                    Quantity,
                    AverageEntryPrice,
                    CurrentPrice,
                    UnrealizedPnL,
                    Side
                FROM vw_CurrentPositions
                WHERE Quantity != 0
            """)
            
            for row in cursor.fetchall():
                symbol, qty, entry, current, pnl, side = row
                unrealized_pct = (pnl / (entry * abs(qty))) * 100 if entry and qty else 0
                
                positions.append(PositionSnapshot(
                    symbol=symbol,
                    quantity=qty or 0,
                    avg_entry_price=entry or 0.0,
                    current_price=current or 0.0,
                    unrealized_pnl=pnl or 0.0,
                    unrealized_pnl_pct=unrealized_pct,
                    side=side or "none",
                ))
            
            cursor.close()
            
        except pyodbc.Error as e:
            logger.warning(f"Database error in get_positions: {e}")
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
        
        return positions
    
    def get_performance_snapshot(self) -> PerformanceSnapshot:
        """
        Calculate performance metrics from trade history.
        
        Returns:
            PerformanceSnapshot with daily, weekly, and overall metrics.
        """
        snapshot = PerformanceSnapshot(timestamp=datetime.now())
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Today's metrics
            cursor.execute("""
                SELECT 
                    ISNULL(SUM(PnL), 0) as DailyPnL,
                    COUNT(*) as DailyTrades,
                    ISNULL(AVG(CASE WHEN PnL > 0 THEN 1.0 ELSE 0.0 END), 0) as WinRate
                FROM Trades
                WHERE CAST(ExitTime AS DATE) = CAST(GETDATE() AS DATE)
                AND Status = 'CLOSED'
            """)
            row = cursor.fetchone()
            if row:
                snapshot.daily_pnl = float(row[0] or 0)
                snapshot.daily_trades = int(row[1] or 0)
                snapshot.daily_win_rate = float(row[2] or 0)
            
            # Weekly metrics (last 7 days)
            cursor.execute("""
                SELECT 
                    ISNULL(SUM(PnL), 0) as WeeklyPnL,
                    COUNT(*) as WeeklyTrades,
                    ISNULL(AVG(CASE WHEN PnL > 0 THEN 1.0 ELSE 0.0 END), 0) as WinRate
                FROM Trades
                WHERE ExitTime >= DATEADD(day, -7, GETDATE())
                AND Status = 'CLOSED'
            """)
            row = cursor.fetchone()
            if row:
                snapshot.weekly_pnl = float(row[0] or 0)
                snapshot.weekly_trades = int(row[1] or 0)
                snapshot.weekly_win_rate = float(row[2] or 0)
            
            # Overall metrics
            cursor.execute("""
                SELECT 
                    ISNULL(SUM(PnL), 0) as TotalPnL,
                    COUNT(*) as TotalTrades,
                    ISNULL(AVG(CASE WHEN PnL > 0 THEN 1.0 ELSE 0.0 END), 0) as WinRate
                FROM Trades
                WHERE Status = 'CLOSED'
            """)
            row = cursor.fetchone()
            if row:
                snapshot.total_pnl = float(row[0] or 0)
                snapshot.total_trades = int(row[1] or 0)
                snapshot.overall_win_rate = float(row[2] or 0)
            
            # Get Sharpe ratio and drawdown from metrics table
            cursor.execute("""
                SELECT TOP 1 
                    SharpeRatio, 
                    MaxDrawdown,
                    CurrentDrawdown
                FROM PerformanceMetrics
                ORDER BY CalculatedAt DESC
            """)
            row = cursor.fetchone()
            if row:
                snapshot.sharpe_ratio = float(row[0] or 0)
                snapshot.max_drawdown = float(row[1] or 0)
                snapshot.current_drawdown = float(row[2] or 0)
            
            # Calculate current streak
            cursor.execute("""
                WITH RecentTrades AS (
                    SELECT TOP 20
                        CASE WHEN PnL > 0 THEN 1 ELSE -1 END as Result
                    FROM Trades
                    WHERE Status = 'CLOSED'
                    ORDER BY ExitTime DESC
                ),
                Streaks AS (
                    SELECT 
                        Result,
                        ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) as rn
                    FROM RecentTrades
                )
                SELECT TOP 1 Result, COUNT(*) as StreakLen
                FROM Streaks
                WHERE rn <= (
                    SELECT MIN(rn) - 1
                    FROM Streaks s2
                    WHERE s2.Result != (SELECT Result FROM Streaks WHERE rn = 1)
                ) OR NOT EXISTS (
                    SELECT 1 FROM Streaks s2
                    WHERE s2.Result != (SELECT Result FROM Streaks WHERE rn = 1)
                )
                GROUP BY Result
            """)
            row = cursor.fetchone()
            if row:
                direction, length = row
                snapshot.current_streak = direction * length
            
            cursor.close()
            
        except pyodbc.Error as e:
            logger.warning(f"Database error in get_performance_snapshot: {e}")
        except Exception as e:
            logger.error(f"Error getting performance snapshot: {e}")
        
        return snapshot
    
    def _is_market_open(self, dt: datetime) -> bool:
        """
        Check if the market is currently open.
        
        Note: Simplified check - real implementation should use
        exchange calendars and handle holidays.
        """
        # Check if weekday (0=Monday, 6=Sunday)
        if dt.weekday() >= 5:
            return False
        
        # Check market hours (9:30 AM - 4:00 PM ET)
        # This assumes the system is running in ET timezone
        market_open = dt.replace(hour=9, minute=30, second=0)
        market_close = dt.replace(hour=16, minute=0, second=0)
        
        return market_open <= dt <= market_close
    
    def get_full_context(self) -> tuple[MarketSnapshot, list[PositionSnapshot], PerformanceSnapshot]:
        """
        Get complete market context in a single call.
        
        Returns:
            Tuple of (MarketSnapshot, list[PositionSnapshot], PerformanceSnapshot)
        """
        market = self.get_market_snapshot()
        positions = self.get_positions()
        performance = self.get_performance_snapshot()
        return market, positions, performance
    
    def close(self):
        """Close database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
