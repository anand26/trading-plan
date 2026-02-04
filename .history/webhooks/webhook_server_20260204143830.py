"""
TQQQ/SQQQ Pairs Trading - Webhook Server
==========================================
Receives alerts from TradingView and executes trades via Alpaca.

This server is intentionally "dumb" - all strategy logic is in Pine Script.
It only:
1. Receives webhook POST from TradingView
2. Validates the payload
3. Checks current position state from Alpaca (source of truth)
4. Executes the trade if valid
5. Logs everything to database

Usage:
    uvicorn webhook_server:app --host 0.0.0.0 --port 8080 --reload

For ngrok testing:
    ngrok http 8080
"""

import os
import json
import logging
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import asyncio
from concurrent.futures import ThreadPoolExecutor

import pyodbc
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("webhook_server")

# Thread pool for blocking database operations
db_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="db-worker")

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Server configuration from environment variables"""
    # Alpaca
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
    ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    
    # Database
    DB_SERVER = os.getenv("DB_SERVER", "localhost")
    DB_NAME = os.getenv("DB_NAME", "TradingDB")
    DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    DB_USERNAME = os.getenv("DB_USERNAME", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    
    # Webhook
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
    WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))
    
    # Trading
    TRADING_MODE = os.getenv("TRADING_MODE", "paper")  # paper or live
    
    @classmethod
    def get_db_connection_string(cls) -> str:
        if cls.DB_USERNAME and cls.DB_PASSWORD:
            return (
                f"DRIVER={{{cls.DB_DRIVER}}};"
                f"SERVER={cls.DB_SERVER};"
                f"DATABASE={cls.DB_NAME};"
                f"UID={cls.DB_USERNAME};"
                f"PWD={cls.DB_PASSWORD};"
                f"TrustServerCertificate=yes"
            )
        else:
            return (
                f"DRIVER={{{cls.DB_DRIVER}}};"
                f"SERVER={cls.DB_SERVER};"
                f"DATABASE={cls.DB_NAME};"
                f"Trusted_Connection=yes;"
                f"TrustServerCertificate=yes"
            )

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class WebhookPayload(BaseModel):
    """Expected payload from TradingView webhook"""
    action: str = Field(..., description="BUY_TQQQ, BUY_SQQQ, or EXIT")
    symbol: Optional[str] = Field(None, description="TQQQ or SQQQ")
    position_size: float = Field(0.57, description="Position size as decimal (0.57 = 57%)")
    stop_loss_pct: float = Field(0.02, description="Stop loss percentage (0.02 = 2%)")
    zscore: Optional[float] = Field(None, description="Current Z-score")
    price: Optional[float] = Field(None, description="Current price")
    ratio: Optional[float] = Field(None, description="TQQQ/SQQQ ratio")
    reason: Optional[str] = Field(None, description="Exit reason if action is EXIT")

class TradeResponse(BaseModel):
    """Response after processing webhook"""
    status: str
    action: str
    message: str
    order_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

# ============================================================================
# ALPACA CLIENT
# ============================================================================

class AlpacaExecutor:
    """Handles all Alpaca API interactions"""
    
    def __init__(self):
        self.api = tradeapi.REST(
            Config.ALPACA_API_KEY,
            Config.ALPACA_SECRET_KEY,
            Config.ALPACA_BASE_URL,
            api_version='v2'
        )
        logger.info(f"Alpaca client initialized - Base URL: {Config.ALPACA_BASE_URL}")
    
    def get_account(self) -> Dict[str, Any]:
        """Get account info"""
        account = self.api.get_account()
        return {
            "equity": float(account.equity),
            "buying_power": float(account.buying_power),
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value)
        }
    
    def get_positions(self) -> list:
        """Get all open positions"""
        return self.api.list_positions()
    
    def has_position(self, symbol: Optional[str] = None) -> bool:
        """Check if we have any position (or specific symbol)"""
        positions = self.get_positions()
        if symbol:
            return any(p.symbol == symbol for p in positions)
        return len(positions) > 0
    
    def get_position_details(self) -> Optional[Dict[str, Any]]:
        """Get current position details"""
        positions = self.get_positions()
        if not positions:
            return None
        pos = positions[0]  # We only hold one position at a time
        return {
            "symbol": pos.symbol,
            "qty": int(pos.qty),
            "side": pos.side,
            "market_value": float(pos.market_value),
            "cost_basis": float(pos.cost_basis),
            "unrealized_pl": float(pos.unrealized_pl),
            "unrealized_plpc": float(pos.unrealized_plpc)
        }
    
    def buy(self, symbol: str, position_size: float) -> Dict[str, Any]:
        """
        Buy a position using percentage of CASH (not margin).
        
        Args:
            symbol: TQQQ or SQQQ
            position_size: Decimal (0.57 = 57% of cash)
        
        Note: Uses cash only, no margin. Position sizing is based on 
        available cash to avoid margin-related issues.
        """
        account = self.get_account()
        
        # Use CASH only - no margin
        available_cash = account["cash"]
        target_value = available_cash * position_size
        
        logger.info(f"Account - Cash: ${available_cash:,.2f}, Equity: ${account['equity']:,.2f}")
        logger.info(f"Position sizing based on CASH only (no margin)")
        
        # Safety check: ensure we're not using margin
        if target_value > available_cash:
            logger.warning(f"Target value ${target_value:,.2f} exceeds cash ${available_cash:,.2f}, limiting to cash")
            target_value = available_cash * 0.95  # Use 95% of cash max for safety
        
        # Get current price
        quote = self.api.get_latest_quote(symbol)
        current_price = float(quote.ask_price) if quote.ask_price else float(quote.bid_price)
        
        # Calculate shares
        qty = int(target_value / current_price)
        
        if qty <= 0:
            raise ValueError(f"Calculated quantity is 0 - cash: ${available_cash:,.2f}, target: ${target_value:,.2f}")
        
        # Final check: order value should not exceed cash
        order_value = qty * current_price
        if order_value > available_cash:
            qty = int(available_cash * 0.95 / current_price)
            order_value = qty * current_price
            logger.warning(f"Adjusted qty to {qty} to stay within cash limit")
        
        logger.info(f"Buying {qty} shares of {symbol} @ ~${current_price:.2f} (order value: ${order_value:,.2f})")
        
        order = self.api.submit_order(
            symbol=symbol,
            qty=qty,
            side='buy',
            type='market',
            time_in_force='day'
        )
        
        return {
            "order_id": order.id,
            "symbol": symbol,
            "qty": qty,
            "side": "buy",
            "type": "market",
            "status": order.status,
            "order_value": order_value,
            "cash_used_pct": (order_value / available_cash) * 100
        }
    
    def close_all(self) -> Dict[str, Any]:
        """Close all positions"""
        positions = self.get_positions()
        if not positions:
            return {"closed": [], "message": "No positions to close"}
        
        closed = []
        for pos in positions:
            order = self.api.close_position(pos.symbol)
            closed.append({
                "symbol": pos.symbol,
                "qty": int(pos.qty),
                "order_id": order.id
            })
            logger.info(f"Closed position: {pos.symbol} ({pos.qty} shares)")
        
        return {"closed": closed, "message": f"Closed {len(closed)} position(s)"}

# ============================================================================
# DATABASE LOGGING
# ============================================================================

class DatabaseLogger:
    """Logs webhook events and trades to SQL Server"""
    
    def __init__(self):
        self.connection_string = Config.get_db_connection_string()
    
    def _get_connection(self):
        """Get a new database connection with proper error handling"""
        try:
            conn = pyodbc.connect(self.connection_string, timeout=10)
            conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
            conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
            conn.setencoding(encoding='utf-8')
            return conn
        except Exception as e:
            logger.error(f"Failed to establish database connection: {e}")
            raise
    
    async def log_webhook_event_async(
        self, 
        payload: Dict[str, Any], 
        status: str, 
        response: Dict[str, Any],
        error: Optional[str] = None
    ):
        """Log webhook event to database (async wrapper)"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            db_executor,
            self.log_webhook_event,
            payload,
            status,
            response,
            error
        )
    
    def log_webhook_event(
        self, 
        payload: Dict[str, Any], 
        status: str, 
        response: Dict[str, Any],
        error: Optional[str] = None
    ):
        """Log webhook event to database"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get or create a session for webhook events
            session_type = "PAPER" if "paper" in Config.ALPACA_BASE_URL else "LIVE"
            cursor.execute("""
                SELECT TOP 1 SessionId FROM dbo.Sessions 
                WHERE SessionType = ? AND Status = 'active'
                ORDER BY StartTime DESC
            """, (session_type,))
            row = cursor.fetchone()
            
            if row:
                session_id = row[0]
            else:
                # Create new session
                import uuid
                session_id = f"WH-{str(uuid.uuid4())[:8]}"
                cursor.execute("""
                    INSERT INTO dbo.Sessions 
                    (SessionId, SessionType, StrategyId, StartTime, Status, Notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    session_type,
                    "TQQQ_SQQQ_PAIRS",
                    datetime.now(timezone.utc),
                    "active",
                    "Auto-created by webhook server"
                ))
                conn.commit()
            
            # Log webhook event - using actual schema columns:
            # WebhookEvents(SessionId, Timestamp, WebhookType, Symbol, TriggerReason, Price, MarketData, Conditions, CreatedAt)
            symbol = payload.get('symbol', payload.get('ticker', 'UNKNOWN'))
            webhook_type = payload.get('action', status)
            trigger_reason = payload.get('reason', error or status)
            price_val = payload.get('price')
            
            cursor.execute("""
                INSERT INTO dbo.WebhookEvents 
                (SessionId, Timestamp, WebhookType, Symbol, TriggerReason, Price, MarketData, Conditions, CreatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.now(timezone.utc),
                webhook_type[:50] if webhook_type else 'UNKNOWN',
                symbol[:20] if symbol else 'UNKNOWN',
                (trigger_reason or '')[:500] if trigger_reason else None,
                float(price_val) if price_val else None,
                json.dumps(payload),  # Store full payload in MarketData
                json.dumps(response),  # Store response in Conditions
                datetime.now(timezone.utc)
            ))
            conn.commit()
            logger.debug(f"Webhook event logged: {status}")
        except Exception as e:
            logger.error(f"Failed to log webhook event: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    async def log_trade_async(
        self,
        action: str,
        symbol: str,
        qty: float,
        price: float,
        order_id: str,
        zscore: Optional[float] = None
    ):
        """Log trade to database (async wrapper)"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            db_executor,
            self.log_trade,
            action,
            symbol,
            qty,
            price,
            order_id,
            zscore
        )
    
    def log_trade(
        self,
        action: str,
        symbol: str,
        qty: float,
        price: float,
        order_id: str,
        zscore: Optional[float] = None
    ):
        """Log trade to database.
        
        Note: The Trades table schema expects full trade lifecycle (entry+exit).
        For webhook-triggered trades, we log as entry initially.
        Schema: Symbol, Direction, EntryTime, EntryPrice, EntryQuantity, SessionId, etc.
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get active session
            session_type = "PAPER" if "paper" in Config.ALPACA_BASE_URL else "LIVE"
            cursor.execute("""
                SELECT TOP 1 SessionId FROM dbo.Sessions 
                WHERE SessionType = ? AND Status = 'active'
                ORDER BY StartTime DESC
            """, (session_type,))
            row = cursor.fetchone()
            session_id = row[0] if row else None
            
            # Determine direction from action
            direction = 'LONG' if action.upper() in ('BUY', 'ENTRY', 'LONG') else 'SHORT' if action.upper() in ('SHORT', 'SELL_SHORT') else 'EXIT'
            
            if direction != 'EXIT':
                # Log as new trade entry
                cursor.execute("""
                    INSERT INTO dbo.Trades
                    (Symbol, Direction, EntryTime, EntryPrice, EntryQuantity, SessionId, CreatedAt)
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
            else:
                # For exit, try to update the most recent open trade for this symbol
                cursor.execute("""
                    UPDATE dbo.Trades
                    SET ExitTime = ?, ExitPrice = ?, ExitQuantity = ?, ExitReason = ?
                    WHERE TradeId = (
                        SELECT TOP 1 TradeId FROM dbo.Trades 
                        WHERE Symbol = ? AND ExitTime IS NULL 
                        ORDER BY EntryTime DESC
                    )
                """, (
                    datetime.now(timezone.utc),
                    price,
                    qty,
                    f"Webhook:{action}",
                    symbol
                ))
                
            conn.commit()
            logger.debug(f"Trade logged to database: {action} {symbol}")
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

# Global instances
alpaca: Optional[AlpacaExecutor] = None
db_logger: Optional[DatabaseLogger] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup"""
    global alpaca, db_logger
    
    logger.info("Starting webhook server...")
    
    # Initialize Alpaca client
    alpaca = AlpacaExecutor()
    
    # Test connection
    try:
        account = alpaca.get_account()
        logger.info(f"Connected to Alpaca - Equity: ${account['equity']:,.2f}")
    except Exception as e:
        logger.error(f"Failed to connect to Alpaca: {e}")
        raise
    
    # Initialize database logger
    db_logger = DatabaseLogger()
    logger.info("Database logger initialized")
    
    yield
    
    logger.info("Shutting down webhook server...")

app = FastAPI(
    title="TQQQ/SQQQ Pairs Trading Webhook",
    description="Receives TradingView alerts and executes trades via Alpaca",
    version="1.0.0",
    lifespan=lifespan
)

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "TQQQ/SQQQ Pairs Webhook Server",
        "mode": Config.TRADING_MODE,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        account = alpaca.get_account()
        positions = alpaca.get_position_details()
        
        return {
            "status": "healthy",
            "alpaca_connected": True,
            "account": {
                "cash": account["cash"],
                "equity": account["equity"],
                "buying_power": account["buying_power"],
                "position_sizing_based_on": "CASH (no margin)"
            },
            "current_position": positions,
            "mode": Config.TRADING_MODE,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    Main webhook endpoint for TradingView alerts.
    
    Expected JSON payload:
    {
        "action": "BUY_TQQQ" | "BUY_SQQQ" | "EXIT",
        "position_size": 0.57,
        "stop_loss_pct": 0.02,
        "zscore": -1.65,
        "price": 85.50,
        "ratio": 1.234
    }
    """
    payload_dict = {}
    try:
        # Parse payload with timeout
        body = await asyncio.wait_for(request.body(), timeout=5.0)
        payload_dict = json.loads(body)
        logger.info(f"Received webhook: {payload_dict}")
        
        payload = WebhookPayload(**payload_dict)
        
        # Validate action
        if payload.action not in ["BUY_TQQQ", "BUY_SQQQ", "EXIT"]:
            raise HTTPException(status_code=400, detail=f"Invalid action: {payload.action}")
        
        # Check current position state from Alpaca
        has_position = alpaca.has_position()
        current_position = alpaca.get_position_details()
        
        response = None
        
        # ================================================================
        # ENTRY LOGIC
        # ================================================================
        if payload.action in ["BUY_TQQQ", "BUY_SQQQ"]:
            symbol = "TQQQ" if payload.action == "BUY_TQQQ" else "SQQQ"
            
            if has_position:
                # Already in position - ignore
                response = TradeResponse(
                    status="ignored",
                    action=payload.action,
                    message=f"Already in position: {current_position['symbol']}",
                    details={"current_position": current_position}
                )
                logger.info(f"Ignored {payload.action} - already in {current_position['symbol']}")
            else:
                # Execute entry
                order = alpaca.buy(symbol, payload.position_size)
                response = TradeResponse(
                    status="executed",
                    action=payload.action,
                    message=f"Bought {order['qty']} shares of {symbol}",
                    order_id=order["order_id"],
                    details=order
                )
                logger.info(f"Executed {payload.action}: {order}")
                
                # Log to database asynchronously (don't block response)
                if db_logger:
                    try:
                        await asyncio.wait_for(
                            db_logger.log_trade_async(
                                action=payload.action,
                                symbol=symbol,
                                qty=order["qty"],
                                price=payload.price or 0.0,
                                order_id=order["order_id"],
                                zscore=payload.zscore or 0.0
                            ),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Database logging timed out, continuing...")
        
        # ================================================================
        # EXIT LOGIC
        # ================================================================
        elif payload.action == "EXIT":
            if not has_position:
                # No position to exit - ignore
                response = TradeResponse(
                    status="ignored",
                    action="EXIT",
                    message="No position to exit",
                    details={}
                )
                logger.info("Ignored EXIT - no position")
            else:
                # Execute exit
                result = alpaca.close_all()
                response = TradeResponse(
                    status="executed",
                    action="EXIT",
                    message=result["message"],
                    order_id=result["closed"][0]["order_id"] if result["closed"] else None,
                    details=result
                )
                logger.info(f"Executed EXIT: {result}")
                
                # Log to database asynchronously (don't block response)
                if db_logger and result["closed"]:
                    for closed in result["closed"]:
                        try:
                            await asyncio.wait_for(
                                db_logger.log_trade_async(
                                    action="EXIT",
                                    symbol=closed["symbol"],
                                    qty=closed["qty"],
                                    price=payload.price or 0.0,
                                    order_id=closed["order_id"],
                                    zscore=payload.zscore or 0.0
                                ),
                                timeout=5.0
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Database logging timed out, continuing...")
        
        # Log webhook event asynchronously
        if db_logger:
            try:
                await asyncio.wait_for(
                    db_logger.log_webhook_event_async(
                        payload=payload_dict,
                        status=response.status,
                        response=response.model_dump()
                    ),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Webhook event logging timed out")
        
        return response
        
    except asyncio.TimeoutError:
        logger.error("Request processing timed out")
        raise HTTPException(status_code=504, detail="Request processing timed out")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        if db_logger:
            try:
                await asyncio.wait_for(
                    db_logger.log_webhook_event_async(
                        payload=payload_dict,
                        status="error",
                        response={},
                        error=str(e)
                    ),
                    timeout=5.0
                )
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/test")
async def test_webhook(request: Request):
    """Test endpoint - logs but doesn't execute"""
    body = await request.body()
    payload = json.loads(body)
    logger.info(f"TEST webhook received: {payload}")
    return {
        "status": "test_received",
        "payload": payload,
        "message": "This is a test endpoint - no trades executed",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/positions")
async def get_positions():
    """Get current positions"""
    positions = alpaca.get_positions()
    return {
        "count": len(positions),
        "positions": [
            {
                "symbol": p.symbol,
                "qty": int(p.qty),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl)
            }
            for p in positions
        ]
    }

@app.post("/close-all")
async def close_all_positions():
    """Emergency close all positions"""
    result = alpaca.close_all()
    return result

@app.post("/cancel-all")
async def cancel_all_orders():
    """Cancel all pending orders"""
    try:
        alpaca.api.cancel_all_orders()
        return {"status": "success", "message": "All pending orders cancelled"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/orders")
async def get_orders():
    """Get recent orders"""
    try:
        orders = alpaca.api.list_orders(status='all', limit=10)
        return {
            "count": len(orders),
            "orders": [
                {
                    "id": o.id,
                    "symbol": o.symbol,
                    "qty": o.qty,
                    "side": o.side,
                    "status": o.status,
                    "submitted_at": str(o.submitted_at),
                    "filled_at": str(o.filled_at) if o.filled_at else None
                }
                for o in orders
            ]
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "webhook_server:app",
        host="0.0.0.0",
        port=Config.WEBHOOK_PORT,
        reload=False,  # Disable reload in production to avoid connection issues
        timeout_keep_alive=30,  # Keep connections alive for 30s
        loop="asyncio"  # Use asyncio event loop
    )
