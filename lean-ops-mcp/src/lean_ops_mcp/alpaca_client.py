"""
Alpaca Brokerage Interface
==========================
Interface to Alpaca for paper and live trading.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    httpx = None

from .config import get_config

logger = logging.getLogger(__name__)


class TradingMode(str, Enum):
    """Trading mode enumeration."""
    PAPER = "paper"
    LIVE = "live"


class AlpacaError(Exception):
    """Alpaca API error."""
    pass


@dataclass
class Position:
    """Represents a position in the account."""
    symbol: str
    quantity: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    current_price: float
    side: str  # "long" or "short"


@dataclass
class AccountInfo:
    """Account information."""
    account_id: str
    status: str
    currency: str
    cash: float
    portfolio_value: float
    buying_power: float
    day_trade_count: int
    pattern_day_trader: bool
    trading_blocked: bool


@dataclass
class Order:
    """Order information."""
    order_id: str
    symbol: str
    side: str
    type: str
    quantity: float
    filled_quantity: float
    status: str
    created_at: datetime
    filled_at: Optional[datetime]
    filled_avg_price: Optional[float]


class AlpacaClient:
    """
    Alpaca brokerage client for paper and live trading.
    
    Provides:
    - Account information
    - Position management
    - Order submission and tracking
    - Market data (basic)
    """
    
    def __init__(self, mode: TradingMode = TradingMode.PAPER):
        self.mode = mode
        self.config = get_config().alpaca
        self.safety = get_config().safety
        
        # Set credentials based on mode
        if mode == TradingMode.PAPER:
            self.api_key = self.config.paper_key
            self.api_secret = self.config.paper_secret
            self.base_url = self.config.paper_url
        else:
            self.api_key = self.config.live_key
            self.api_secret = self.config.live_secret
            self.base_url = self.config.live_url
        
        self._client: Optional["httpx.Client"] = None
    
    @property
    def configured(self) -> bool:
        """Check if client is properly configured."""
        return bool(self.api_key and self.api_secret)
    
    def _get_client(self) -> "httpx.Client":
        """Get or create HTTP client."""
        if not HAS_HTTPX:
            raise AlpacaError("httpx library not installed")
        
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers={
                    "APCA-API-KEY-ID": self.api_key,
                    "APCA-API-SECRET-KEY": self.api_secret,
                },
                timeout=30.0
            )
        return self._client
    
    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request."""
        client = self._get_client()
        try:
            response = client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            raise AlpacaError(f"API error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise AlpacaError(f"Request failed: {str(e)}")
    
    # ============================================
    # ACCOUNT
    # ============================================
    
    def get_account(self) -> AccountInfo:
        """Get account information."""
        data = self._request("GET", "/v2/account")
        return AccountInfo(
            account_id=data["id"],
            status=data["status"],
            currency=data["currency"],
            cash=float(data["cash"]),
            portfolio_value=float(data["portfolio_value"]),
            buying_power=float(data["buying_power"]),
            day_trade_count=int(data["daytrade_count"]),
            pattern_day_trader=data["pattern_day_trader"],
            trading_blocked=data["trading_blocked"]
        )
    
    # ============================================
    # POSITIONS
    # ============================================
    
    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        data = self._request("GET", "/v2/positions")
        return [
            Position(
                symbol=p["symbol"],
                quantity=float(p["qty"]),
                market_value=float(p["market_value"]),
                cost_basis=float(p["cost_basis"]),
                unrealized_pnl=float(p["unrealized_pl"]),
                unrealized_pnl_pct=float(p["unrealized_plpc"]),
                current_price=float(p["current_price"]),
                side=p["side"]
            )
            for p in data
        ]
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for specific symbol."""
        try:
            data = self._request("GET", f"/v2/positions/{symbol}")
            return Position(
                symbol=data["symbol"],
                quantity=float(data["qty"]),
                market_value=float(data["market_value"]),
                cost_basis=float(data["cost_basis"]),
                unrealized_pnl=float(data["unrealized_pl"]),
                unrealized_pnl_pct=float(data["unrealized_plpc"]),
                current_price=float(data["current_price"]),
                side=data["side"]
            )
        except AlpacaError:
            return None
    
    def close_position(self, symbol: str) -> bool:
        """Close position for symbol."""
        try:
            self._request("DELETE", f"/v2/positions/{symbol}")
            logger.info(f"Closed position: {symbol}")
            return True
        except AlpacaError as e:
            logger.error(f"Failed to close position {symbol}: {e}")
            return False
    
    def close_all_positions(self) -> bool:
        """Close all positions (emergency liquidation)."""
        try:
            self._request("DELETE", "/v2/positions")
            logger.warning("EMERGENCY: Closed all positions")
            return True
        except AlpacaError as e:
            logger.error(f"Failed to close all positions: {e}")
            return False
    
    # ============================================
    # ORDERS
    # ============================================
    
    def submit_order(
        self,
        symbol: str,
        quantity: float,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Order:
        """Submit an order."""
        # Safety check for live mode
        if self.mode == TradingMode.LIVE:
            if not self.safety.live_deploy_enabled:
                raise AlpacaError("Live trading is disabled")
            
            # Check position size limit
            if limit_price:
                order_value = quantity * limit_price
            else:
                # Estimate with current price
                pos = self.get_position(symbol)
                if pos:
                    order_value = quantity * pos.current_price
                else:
                    order_value = quantity * 100  # Conservative estimate
            
            if order_value > self.safety.max_position_size:
                raise AlpacaError(
                    f"Order value ${order_value:.2f} exceeds max position size ${self.safety.max_position_size}"
                )
        
        payload = {
            "symbol": symbol,
            "qty": str(quantity),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force
        }
        
        if limit_price:
            payload["limit_price"] = str(limit_price)
        if stop_price:
            payload["stop_price"] = str(stop_price)
        
        data = self._request("POST", "/v2/orders", json=payload)
        
        return Order(
            order_id=data["id"],
            symbol=data["symbol"],
            side=data["side"],
            type=data["type"],
            quantity=float(data["qty"]),
            filled_quantity=float(data.get("filled_qty", 0)),
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            filled_at=datetime.fromisoformat(data["filled_at"].replace("Z", "+00:00")) if data.get("filled_at") else None,
            filled_avg_price=float(data["filled_avg_price"]) if data.get("filled_avg_price") else None
        )
    
    def get_order(self, order_id: str) -> Order:
        """Get order by ID."""
        data = self._request("GET", f"/v2/orders/{order_id}")
        return Order(
            order_id=data["id"],
            symbol=data["symbol"],
            side=data["side"],
            type=data["type"],
            quantity=float(data["qty"]),
            filled_quantity=float(data.get("filled_qty", 0)),
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            filled_at=datetime.fromisoformat(data["filled_at"].replace("Z", "+00:00")) if data.get("filled_at") else None,
            filled_avg_price=float(data["filled_avg_price"]) if data.get("filled_avg_price") else None
        )
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self._request("DELETE", f"/v2/orders/{order_id}")
            logger.info(f"Cancelled order: {order_id}")
            return True
        except AlpacaError as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        try:
            self._request("DELETE", "/v2/orders")
            logger.warning("Cancelled all open orders")
            return True
        except AlpacaError as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return False
    
    def get_orders(
        self,
        status: str = "all",
        limit: int = 50,
        after: Optional[datetime] = None
    ) -> List[Order]:
        """Get orders with optional filters."""
        params = {
            "status": status,
            "limit": limit,
            "direction": "desc"
        }
        if after:
            params["after"] = after.isoformat()
        
        data = self._request("GET", "/v2/orders", params=params)
        return [
            Order(
                order_id=o["id"],
                symbol=o["symbol"],
                side=o["side"],
                type=o["type"],
                quantity=float(o["qty"]),
                filled_quantity=float(o.get("filled_qty", 0)),
                status=o["status"],
                created_at=datetime.fromisoformat(o["created_at"].replace("Z", "+00:00")),
                filled_at=datetime.fromisoformat(o["filled_at"].replace("Z", "+00:00")) if o.get("filled_at") else None,
                filled_avg_price=float(o["filled_avg_price"]) if o.get("filled_avg_price") else None
            )
            for o in data
        ]


# Global clients
_paper_client: Optional[AlpacaClient] = None
_live_client: Optional[AlpacaClient] = None


def get_paper_client() -> AlpacaClient:
    """Get paper trading client."""
    global _paper_client
    if _paper_client is None:
        _paper_client = AlpacaClient(TradingMode.PAPER)
    return _paper_client


def get_live_client() -> AlpacaClient:
    """Get live trading client."""
    global _live_client
    if _live_client is None:
        _live_client = AlpacaClient(TradingMode.LIVE)
    return _live_client


def close_clients():
    """Close all clients."""
    global _paper_client, _live_client
    if _paper_client:
        _paper_client.close()
        _paper_client = None
    if _live_client:
        _live_client.close()
        _live_client = None
