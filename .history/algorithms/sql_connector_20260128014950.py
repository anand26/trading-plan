"""
TQQQ/SQQQ Trading System - SQL Connector
=========================================
Database persistence layer for the trading algorithm.

This module provides SQL Server connectivity for:
- Real-time trade logging
- Signal persistence for analysis
- Session management
- Parameter hot-reload from database

Designed to integrate with both LEAN backtesting and live trading,
feeding data to Trade-Mind MCP for adaptive learning.

Usage in Algorithm:
    from sql_connector import TradingDBConnector
    
    def Initialize(self):
        self.db = TradingDBConnector(self)
        self.db.start_session("PAPER")
    
    def OnOrderEvent(self, orderEvent):
        self.db.log_order(orderEvent)
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass

# Conditional import for type checking (LEAN environment may not have pyodbc)
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False
    pyodbc = None  # type: ignore

if TYPE_CHECKING:
    from AlgorithmImports import QCAlgorithm


@dataclass
class ConnectionConfig:
    """SQL Server connection configuration"""
    server: str = "localhost"
    database: str = "TradingDB"
    driver: str = "{ODBC Driver 17 for SQL Server}"
    trusted_connection: bool = True
    username: str = ""
    password: str = ""
    
    def to_connection_string(self) -> str:
        """Generate pyodbc connection string"""
        if self.trusted_connection:
            return (
                f"Driver={self.driver};"
                f"Server={self.server};"
                f"Database={self.database};"
                f"Trusted_Connection=yes;"
            )
        else:
            return (
                f"Driver={self.driver};"
                f"Server={self.server};"
                f"Database={self.database};"
                f"UID={self.username};"
                f"PWD={self.password};"
            )


class TradingDBConnector:
    """
    SQL Server connector for trading algorithm persistence.
    
    Provides:
    - Session management (start/end trading sessions)
    - Trade logging (entry, exit, P&L)
    - Signal logging (for Trade-Mind analysis)
    - Order tracking
    - Parameter loading/hot-reload
    - Daily performance aggregation
    
    Data feeds into Trade-Mind MCP tools:
    - sp_GetLastTrades
    - sp_CalculateWinRate
    - sp_GetDailyPnL
    - sp_SuggestCorrections
    """
    
    def __init__(
        self,
        algorithm: Optional['QCAlgorithm'] = None,
        config: Optional[ConnectionConfig] = None,
        enabled: bool = True
    ):
        self.algorithm = algorithm
        self.config = config or ConnectionConfig()
        self.enabled = enabled and HAS_PYODBC
        self.conn: Optional[Any] = None
        self.session_id: Optional[str] = None
        self.strategy_id: str = "TQQQ_SCALPING"
        
        # Batch queue for performance (batch inserts)
        self._signal_queue: List[Dict] = []
        self._order_queue: List[Dict] = []
        self._batch_size = 50
        
        if not HAS_PYODBC:
            self._log("WARNING: pyodbc not available - SQL persistence disabled")
    
    def _log(self, message: str) -> None:
        """Log message via algorithm or print"""
        if self.algorithm:
            self.algorithm.Debug(f"[SQL] {message}")
        else:
            print(f"[SQL] {message}")
    
    # ============================================
    # CONNECTION MANAGEMENT
    # ============================================
    
    def connect(self) -> bool:
        """Establish database connection"""
        if not self.enabled:
            return False
        
        try:
            self.conn = pyodbc.connect(self.config.to_connection_string())
            self._log("Connected to TradingDB")
            return True
        except Exception as e:
            self._log(f"Connection failed: {e}")
            self.enabled = False
            return False
    
    def disconnect(self) -> None:
        """Close database connection"""
        if self.conn:
            # Flush any pending batches
            self._flush_signal_queue()
            self._flush_order_queue()
            
            self.conn.close()
            self.conn = None
            self._log("Disconnected from TradingDB")
    
    def _ensure_connected(self) -> bool:
        """Ensure connection is active, reconnect if needed"""
        if not self.enabled:
            return False
        
        if self.conn is None:
            return self.connect()
        
        try:
            # Test connection with simple query
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except:
            return self.connect()
    
    # ============================================
    # SESSION MANAGEMENT
    # ============================================
    
    def start_session(
        self,
        session_type: str = "BACKTEST",
        parameters: Optional[Dict] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Start a new trading session.
        
        Args:
            session_type: BACKTEST, PAPER, or LIVE
            parameters: Strategy parameters dict to snapshot
            session_id: Optional explicit session ID (for backtests)
            
        Returns:
            session_id: Unique identifier for this session
        """
        if not self._ensure_connected():
            # Use provided session ID or generate new one
            self.session_id = session_id or self._generate_session_id(session_type)
            return self.session_id
        
        self.session_id = session_id or self._generate_session_id(session_type)
        
        params_json = json.dumps(parameters) if parameters else None
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO Sessions (
                    SessionId, SessionType, StrategyId, StartTime, Status, ParametersJson
                ) VALUES (?, ?, ?, GETUTCDATE(), 'RUNNING', ?)
            """, (self.session_id, session_type, self.strategy_id, params_json))
            
            self.conn.commit()
            self._log(f"Started session: {self.session_id}")
            
        except Exception as e:
            self._log(f"Failed to start session: {e}")
        
        return self.session_id
    
    def end_session(
        self,
        total_return: float = 0.0,
        sharpe_ratio: float = 0.0,
        max_drawdown: float = 0.0,
        total_trades: int = 0,
        win_rate: float = 0.0
    ) -> None:
        """End the current trading session with final statistics"""
        if not self._ensure_connected() or not self.session_id:
            return
        
        # Flush pending queues
        self._flush_signal_queue()
        self._flush_order_queue()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE Sessions
                SET EndTime = GETUTCDATE(),
                    Status = 'COMPLETED',
                    TotalReturn = ?,
                    SharpeRatio = ?,
                    MaxDrawdown = ?,
                    TotalTrades = ?,
                    WinRate = ?
                WHERE SessionId = ?
            """, (total_return, sharpe_ratio, max_drawdown, total_trades, win_rate, self.session_id))
            
            self.conn.commit()
            self._log(f"Ended session: {self.session_id}")
            
        except Exception as e:
            self._log(f"Failed to end session: {e}")
    
    def _generate_session_id(self, prefix: str) -> str:
        """Generate unique session ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        import uuid
        short_uuid = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{short_uuid}"
    
    # ============================================
    # TRADE LOGGING (For Trade-Mind MCP)
    # ============================================
    
    def log_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        entry_time: datetime,
        exit_time: datetime,
        entry_reason: str = "",
        exit_reason: str = "",
        commission: float = 0.0,
        entry_signal_id: Optional[int] = None,
        exit_signal_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Log a completed trade (round-trip).
        
        This populates the Trades table for:
        - sp_GetLastTrades (Trade-Mind MCP)
        - sp_CalculateWinRate (Trade-Mind MCP)
        """
        if not self._ensure_connected():
            return None
        
        # Calculate P&L
        if side == "BUY":
            realized_pnl = (exit_price - entry_price) * quantity - commission
        else:
            realized_pnl = (entry_price - exit_price) * quantity - commission
        
        realized_pnl_pct = realized_pnl / (entry_price * quantity) * 100 if entry_price > 0 else 0
        duration = int((exit_time - entry_time).total_seconds() / 60)  # Duration in minutes
        
        try:
            cursor = self.conn.cursor()
            # Schema: TradeId, Symbol, Direction, EntryTime, EntryPrice, EntryQuantity,
            #         ExitTime, ExitPrice, ExitQuantity, ExitReason, GrossPnL, Commission,
            #         NetPnL, PnLPercent, NumEntries, MaxQuantity, HighestPrice, LowestPrice,
            #         MAE, MFE, DurationMinutes, SessionId, AlgorithmVersion
            cursor.execute("""
                INSERT INTO Trades (
                    Symbol, Direction, EntryTime, EntryPrice, EntryQuantity,
                    ExitTime, ExitPrice, ExitQuantity, ExitReason,
                    GrossPnL, Commission, NetPnL, PnLPercent,
                    NumEntries, DurationMinutes, SessionId
                ) OUTPUT INSERTED.TradeId
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, side, entry_time, entry_price, quantity,
                exit_time, exit_price, quantity, exit_reason,
                realized_pnl + commission, commission, realized_pnl, realized_pnl_pct,
                1, duration, self.session_id
            ))
            
            trade_id = cursor.fetchone()[0]
            self.conn.commit()
            
            self._log(f"Trade logged: {symbol} {side} PnL=${realized_pnl:.2f}")
            return trade_id
            
        except Exception as e:
            self._log(f"Failed to log trade: {e}")
            return None
    
    def log_trade_from_position(
        self,
        position_tracker: Any,
        exit_price: float,
        exit_time: datetime,
        exit_reason: str = ""
    ) -> Optional[int]:
        """
        Log trade from PositionTracker object.
        
        Convenience method for the algorithm.
        """
        if not position_tracker.entries:
            return None
        
        return self.log_trade(
            symbol=position_tracker.symbol,
            side="BUY" if position_tracker.direction == "LONG" else "SELL",
            quantity=position_tracker.total_quantity,
            entry_price=position_tracker.average_price,
            exit_price=exit_price,
            entry_time=position_tracker.entries[0].timestamp,
            exit_time=exit_time,
            entry_reason=f"PYRAMID_L{position_tracker.num_entries}",
            exit_reason=exit_reason
        )
    
    # ============================================
    # SIGNAL LOGGING (For Analysis)
    # ============================================
    
    def log_signal(
        self,
        symbol: str,
        signal_type: str,
        direction: str,
        strength: float,
        rsi_value: Optional[float] = None,
        vwap_distance: Optional[float] = None,
        bb_position: Optional[float] = None,
        qqq_trend: Optional[str] = None,
        volume_mult: Optional[float] = None,
        price: Optional[float] = None,
        was_acted_on: bool = False,
        reason_not_acted: Optional[str] = None
    ) -> Optional[int]:
        """
        Log a trading signal for analysis.
        
        Signals are batched for performance and stored in Signals table.
        Used by Trade-Mind MCP for signal effectiveness analysis.
        """
        signal_data = {
            "session_id": self.session_id,
            "symbol": symbol,
            "timestamp": datetime.utcnow(),
            "signal_type": signal_type,
            "direction": direction,
            "strength": strength,
            "rsi_value": rsi_value,
            "vwap_distance": vwap_distance,
            "bb_position": bb_position,
            "qqq_trend": qqq_trend,
            "volume_mult": volume_mult,
            "price": price,
            "was_acted_on": was_acted_on,
            "reason_not_acted": reason_not_acted
        }
        
        self._signal_queue.append(signal_data)
        
        if len(self._signal_queue) >= self._batch_size:
            self._flush_signal_queue()
        
        return None  # ID returned on flush
    
    def _flush_signal_queue(self) -> None:
        """Flush batched signals to database"""
        if not self._signal_queue or not self._ensure_connected():
            return
        
        try:
            cursor = self.conn.cursor()
            
            for signal in self._signal_queue:
                cursor.execute("""
                    INSERT INTO Signals (
                        SessionId, Symbol, Timestamp,
                        SignalType, Direction, Strength,
                        RsiValue, VwapDistance, BbPosition, QqqTrend, VolumeMult,
                        Price, WasActedOn, ReasonNotActed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal["session_id"],
                    signal["symbol"],
                    signal["timestamp"],
                    signal["signal_type"],
                    signal["direction"],
                    signal["strength"],
                    signal["rsi_value"],
                    signal["vwap_distance"],
                    signal["bb_position"],
                    signal["qqq_trend"],
                    signal["volume_mult"],
                    signal["price"],
                    signal["was_acted_on"],
                    signal["reason_not_acted"]
                ))
            
            self.conn.commit()
            self._log(f"Flushed {len(self._signal_queue)} signals")
            self._signal_queue = []
            
        except Exception as e:
            self._log(f"Failed to flush signals: {e}")
    
    # ============================================
    # ORDER LOGGING
    # ============================================
    
    def log_order(
        self,
        order_id: str,
        symbol: str,
        order_type: str,
        side: str,
        quantity: float,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        status: str = "SUBMITTED",
        fill_price: Optional[float] = None,
        fill_quantity: Optional[float] = None,
        commission: float = 0.0,
        tag: str = ""
    ) -> None:
        """Log order submission and updates"""
        order_data = {
            "session_id": self.session_id,
            "order_id": order_id,
            "symbol": symbol,
            "order_type": order_type,
            "side": side,
            "quantity": quantity,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "status": status,
            "fill_price": fill_price,
            "fill_quantity": fill_quantity,
            "commission": commission,
            "tag": tag,
            "timestamp": datetime.utcnow()
        }
        
        self._order_queue.append(order_data)
        
        if len(self._order_queue) >= self._batch_size:
            self._flush_order_queue()
    
    def _flush_order_queue(self) -> None:
        """Flush batched orders to database"""
        if not self._order_queue or not self._ensure_connected():
            return
        
        try:
            cursor = self.conn.cursor()
            
            # Schema: OrderId, ExternalOrderId, Symbol, Quantity, FilledQuantity, Price, FillPrice,
            #         OrderType, Direction, Status, TimeInForce, SubmittedAt, FilledAt, Tag, Commission
            for order in self._order_queue:
                cursor.execute("""
                    MERGE Orders AS target
                    USING (SELECT ? AS ExternalOrderId) AS source
                    ON target.ExternalOrderId = source.ExternalOrderId
                    WHEN MATCHED THEN
                        UPDATE SET 
                            Status = ?,
                            FillPrice = ?,
                            FilledQuantity = ?,
                            FilledAt = CASE WHEN ? = 'Filled' THEN GETUTCDATE() ELSE FilledAt END,
                            Commission = ?
                    WHEN NOT MATCHED THEN
                        INSERT (ExternalOrderId, Symbol, OrderType, Direction, Quantity,
                                Price, Status, SubmittedAt, Tag)
                        VALUES (?, ?, ?, ?, ?, ?, ?, GETUTCDATE(), ?);
                """, (
                    order["order_id"],
                    order["status"],
                    order["fill_price"],
                    order["fill_quantity"],
                    order["status"],
                    order["commission"],
                    order["order_id"],
                    order["symbol"],
                    order["order_type"],
                    order["side"],  # maps to Direction
                    order["quantity"],
                    order.get("limit_price", 0) or order.get("fill_price", 0),  # maps to Price
                    order["status"],
                    order.get("tag", "")
                ))
            
            self.conn.commit()
            self._log(f"Flushed {len(self._order_queue)} orders")
            self._order_queue = []
            
        except Exception as e:
            self._log(f"Failed to flush orders: {e}")
    
    # ============================================
    # PARAMETER MANAGEMENT
    # ============================================
    
    def load_parameters(self) -> Dict[str, Any]:
        """
        Load strategy parameters from database.
        
        Enables hot-reload of parameters without restarting.
        Returns dict of param_name -> typed value.
        """
        if not self._ensure_connected():
            return {}
        
        params = {}
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT ParamName, ParamValue, ParamType
                FROM StrategyParameters
                WHERE StrategyId = ? AND IsActive = 1
            """, (self.strategy_id,))
            
            for row in cursor.fetchall():
                name, value, param_type = row
                
                # Convert to appropriate type
                if param_type == "INT":
                    params[name] = int(value)
                elif param_type == "FLOAT":
                    params[name] = float(value)
                elif param_type == "BOOL":
                    params[name] = value.lower() in ("true", "1", "yes")
                else:
                    params[name] = value
            
            self._log(f"Loaded {len(params)} parameters from database")
            return params
            
        except Exception as e:
            self._log(f"Failed to load parameters: {e}")
            return {}
    
    def save_parameter(
        self,
        param_name: str,
        param_value: Any,
        changed_by: str = "ALGORITHM"
    ) -> bool:
        """Save a parameter change to database"""
        if not self._ensure_connected():
            return False
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                EXEC sp_UpdateParameter 
                    @ParamName = ?, 
                    @NewValue = ?,
                    @ChangedBy = ?
            """, (param_name, str(param_value), changed_by))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self._log(f"Failed to save parameter: {e}")
            return False
    
    # ============================================
    # DAILY PERFORMANCE
    # ============================================
    
    def update_daily_performance(
        self,
        trading_date: datetime,
        opening_balance: float,
        closing_balance: float,
        realized_pnl: float,
        unrealized_pnl: float,
        trade_count: int,
        win_count: int,
        loss_count: int,
        volume_traded: float = 0.0,
        commission: float = 0.0,
        max_drawdown: float = 0.0
    ) -> None:
        """
        Update daily performance record.
        
        Called at end of each trading day or when session ends.
        Feeds sp_GetDailyPnL for Trade-Mind MCP.
        """
        if not self._ensure_connected():
            return
        
        total_pnl = realized_pnl + unrealized_pnl
        total_pnl_pct = total_pnl / opening_balance if opening_balance > 0 else 0
        
        try:
            cursor = self.conn.cursor()
            # Include both old columns (Date, StartingEquity, EndingEquity) and new columns
            cursor.execute("""
                MERGE DailyPerformance AS target
                USING (SELECT ? AS SessionId, ? AS TradingDate) AS source
                ON target.SessionId = source.SessionId AND target.TradingDate = source.TradingDate
                WHEN MATCHED THEN
                    UPDATE SET 
                        Date = ?,
                        EndingEquity = ?,
                        ClosingBalance = ?,
                        RealizedPnL = ?,
                        UnrealizedPnL = ?,
                        TotalPnL = ?,
                        TotalPnLPct = ?,
                        DailyPnL = ?,
                        DailyPnLPercent = ?,
                        TradeCount = ?,
                        NumTrades = ?,
                        WinCount = ?,
                        WinningTrades = ?,
                        LossCount = ?,
                        LosingTrades = ?,
                        VolumeTraded = ?,
                        Commission = ?,
                        TotalCommission = ?,
                        MaxDrawdownDay = ?,
                        LastUpdated = GETUTCDATE()
                WHEN NOT MATCHED THEN
                    INSERT (Date, SessionId, TradingDate, StartingEquity, OpeningBalance, EndingEquity, ClosingBalance,
                            DailyPnL, DailyPnLPercent, RealizedPnL, UnrealizedPnL, TotalPnL, TotalPnLPct,
                            NumTrades, TradeCount, WinningTrades, WinCount, LosingTrades, LossCount, 
                            VolumeTraded, TotalCommission, Commission, MaxDrawdownDay)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                # MERGE source parameters
                self.session_id, trading_date.date(),
                # UPDATE parameters
                trading_date.date(), closing_balance, closing_balance,
                realized_pnl, unrealized_pnl, total_pnl, total_pnl_pct,
                total_pnl, total_pnl_pct,
                trade_count, trade_count, win_count, win_count, loss_count, loss_count,
                volume_traded, commission, commission, max_drawdown,
                # INSERT parameters
                trading_date.date(), self.session_id, trading_date.date(), 
                opening_balance, opening_balance, closing_balance, closing_balance,
                total_pnl, total_pnl_pct, realized_pnl, unrealized_pnl, total_pnl, total_pnl_pct,
                trade_count, trade_count, win_count, win_count, loss_count, loss_count,
                volume_traded, commission, commission, max_drawdown
            ))
            
            self.conn.commit()
            
        except Exception as e:
            self._log(f"Failed to update daily performance: {e}")
    
    # ============================================
    # MARKET REGIME LOGGING
    # ============================================
    
    def log_market_regime(
        self,
        symbol: str,
        regime_type: str,
        confidence: float,
        trend_direction: str,
        volatility: float,
        vix_level: Optional[float] = None
    ) -> None:
        """
        Log detected market regime change.
        
        Used by sp_DetectMarketRegime for Trade-Mind MCP.
        """
        if not self._ensure_connected():
            return
        
        try:
            cursor = self.conn.cursor()
            
            # Close previous regime if exists
            cursor.execute("""
                UPDATE MarketRegimes
                SET EndTime = GETUTCDATE()
                WHERE Symbol = ? AND EndTime IS NULL
            """, (symbol,))
            
            # Insert new regime - include both old columns (Date, Regime) and new columns
            cursor.execute("""
                INSERT INTO MarketRegimes (
                    Date, Regime, Symbol, RegimeType, Confidence, 
                    TrendDirection, Volatility, VixLevel, StartTime
                ) VALUES (CAST(GETUTCDATE() AS DATE), ?, ?, ?, ?, ?, ?, ?, GETUTCDATE())
            """, (regime_type, symbol, regime_type, confidence, trend_direction, volatility, vix_level))
            
            self.conn.commit()
            self._log(f"Market regime: {symbol} → {regime_type}")
            
        except Exception as e:
            self._log(f"Failed to log market regime: {e}")
    
    # ============================================
    # AUDIT LOGGING
    # ============================================
    
    def log_audit(
        self,
        event_type: str,
        event_details: str,
        severity: str = "INFO"
    ) -> None:
        """Log audit event for system tracking"""
        if not self._ensure_connected():
            return
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO AuditLog (SessionId, EventType, EventDetails, Severity)
                VALUES (?, ?, ?, ?)
            """, (self.session_id, event_type, event_details, severity))
            
            self.conn.commit()
            
        except Exception as e:
            self._log(f"Failed to log audit: {e}")


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def create_connector(
    algorithm: Optional['QCAlgorithm'] = None,
    server: str = "localhost",
    database: str = "TradingDB",
    enabled: bool = True
) -> TradingDBConnector:
    """
    Factory function to create a configured connector.
    
    Usage:
        db = create_connector(self)  # In algorithm Initialize()
    """
    config = ConnectionConfig(server=server, database=database)
    return TradingDBConnector(algorithm=algorithm, config=config, enabled=enabled)


# ============================================
# STANDALONE TEST
# ============================================

if __name__ == "__main__":
    # Test connection
    connector = TradingDBConnector()
    
    if connector.connect():
        print("Connection successful!")
        
        # Start test session
        session_id = connector.start_session(
            session_type="TEST",
            parameters={"rsi_period": 14, "stop_loss_pct": 0.02}
        )
        print(f"Session: {session_id}")
        
        # Log test signal
        connector.log_signal(
            symbol="TQQQ",
            signal_type="ENTRY",
            direction="LONG",
            strength=0.8,
            rsi_value=28.5,
            vwap_distance=-0.02,
            was_acted_on=True
        )
        connector._flush_signal_queue()
        
        # Log test trade
        from datetime import timedelta
        now = datetime.utcnow()
        connector.log_trade(
            symbol="TQQQ",
            side="BUY",
            quantity=100,
            entry_price=45.50,
            exit_price=46.20,
            entry_time=now - timedelta(hours=1),
            exit_time=now,
            entry_reason="RSI_OVERSOLD",
            exit_reason="TAKE_PROFIT"
        )
        
        # End session
        connector.end_session(
            total_return=0.015,
            sharpe_ratio=1.5,
            max_drawdown=0.02,
            total_trades=1,
            win_rate=1.0
        )
        
        connector.disconnect()
        print("Test complete!")
    else:
        print("Connection failed - check SQL Server is running")
