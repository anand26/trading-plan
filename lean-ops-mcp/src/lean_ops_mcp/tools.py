"""
MCP Tools Module
================
Tool implementations for LEAN-Ops MCP server.
"""

import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

from .config import get_config
from .database import get_db, Database
from .lean_engine import get_engine, BacktestResult
from .alpaca_client import (
    get_paper_client, get_live_client, 
    AlpacaClient, TradingMode, AlpacaError,
    Position, AccountInfo
)

logger = logging.getLogger(__name__)


# ============================================
# BACKTEST TOOLS
# ============================================

async def run_backtest(
    algorithm_name: str = "TQQQScalpingAlgorithm",
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
    initial_cash: float = 100000.0,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute a LEAN backtest with specified parameters.
    
    Args:
        algorithm_name: Algorithm class name (default: TQQQScalpingAlgorithm)
        start_date: Backtest start date (YYYY-MM-DD)
        end_date: Backtest end date (YYYY-MM-DD)
        initial_cash: Starting capital
        parameters: Strategy parameters to override
    
    Returns:
        Backtest results with performance metrics
    """
    engine = get_engine()
    db = get_db()
    
    # Validate algorithm exists
    if not engine.validate_algorithm(algorithm_name):
        return {
            "success": False,
            "error": f"Algorithm '{algorithm_name}' not found",
            "available_algorithms": engine.get_available_algorithms()
        }
    
    # Run backtest
    result = engine.run_backtest(
        algorithm_name=algorithm_name,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        parameters=parameters or {}
    )
    
    # Store in database
    if db.connected and result.success:
        db.create_session(
            session_id=result.session_id,
            session_type="BACKTEST",
            algorithm_name=algorithm_name,
            start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
            initial_cash=initial_cash,
            parameters=parameters or {}
        )
        
        db.complete_session(
            session_id=result.session_id,
            total_return=result.total_return,
            sharpe_ratio=result.sharpe_ratio,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            total_trades=result.total_trades
        )
        
        # Log operation
        db.log_operation(
            operation="RUN_BACKTEST",
            session_id=result.session_id,
            details={"algorithm": algorithm_name, "parameters": parameters},
            success=result.success
        )
    
    return result.to_dict()


async def get_backtest_results(session_id: str) -> Dict[str, Any]:
    """
    Retrieve detailed results from a completed backtest.
    
    Args:
        session_id: The backtest session ID
    
    Returns:
        Comprehensive backtest results including trades
    """
    db = get_db()
    
    if not db.connected:
        return {
            "success": False,
            "error": "Database not connected"
        }
    
    # Get session info
    session = db.get_session(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Session '{session_id}' not found"
        }
    
    # Get trades
    trades = db.get_backtest_trades(session_id)
    
    return {
        "success": True,
        "session": session,
        "trades": trades,
        "trade_count": len(trades),
        "summary": {
            "total_return": session.get("TotalReturn"),
            "sharpe_ratio": session.get("SharpeRatio"),
            "max_drawdown": session.get("MaxDrawdown"),
            "win_rate": session.get("WinRate"),
            "total_trades": session.get("TotalTrades")
        }
    }


async def list_backtests(
    limit: int = 20,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    List available backtest sessions.
    
    Args:
        limit: Maximum number of results
        status: Filter by status (COMPLETED, RUNNING, FAILED)
    
    Returns:
        List of backtest sessions
    """
    db = get_db()
    
    if not db.connected:
        return {
            "success": False,
            "error": "Database not connected"
        }
    
    sessions = db.list_sessions(
        session_type="BACKTEST",
        status=status,
        limit=limit
    )
    
    return {
        "success": True,
        "count": len(sessions),
        "sessions": sessions
    }


async def compare_backtests(session_ids: List[str]) -> Dict[str, Any]:
    """
    Compare multiple backtest results side by side.
    
    Args:
        session_ids: List of session IDs to compare
    
    Returns:
        Comparison table with key metrics
    """
    db = get_db()
    
    if not db.connected:
        return {
            "success": False,
            "error": "Database not connected"
        }
    
    comparisons = []
    for session_id in session_ids:
        session = db.get_session(session_id)
        if session:
            comparisons.append({
                "session_id": session_id,
                "start_date": str(session.get("StartDate", "")),
                "end_date": str(session.get("EndDate", "")),
                "total_return": session.get("TotalReturn"),
                "sharpe_ratio": session.get("SharpeRatio"),
                "max_drawdown": session.get("MaxDrawdown"),
                "win_rate": session.get("WinRate"),
                "total_trades": session.get("TotalTrades"),
                "status": session.get("Status")
            })
    
    if not comparisons:
        return {
            "success": False,
            "error": "No valid sessions found"
        }
    
    # Find best performer
    best_return = max(comparisons, key=lambda x: x.get("total_return") or -999)
    best_sharpe = max(comparisons, key=lambda x: x.get("sharpe_ratio") or -999)
    best_winrate = max(comparisons, key=lambda x: x.get("win_rate") or -999)
    
    return {
        "success": True,
        "count": len(comparisons),
        "comparisons": comparisons,
        "best_performers": {
            "highest_return": best_return["session_id"],
            "highest_sharpe": best_sharpe["session_id"],
            "highest_win_rate": best_winrate["session_id"]
        }
    }


# ============================================
# DEPLOYMENT TOOLS
# ============================================

async def deploy_paper(
    algorithm_name: str = "TQQQScalpingAlgorithm",
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Deploy algorithm to Alpaca paper trading.
    
    Args:
        algorithm_name: Algorithm to deploy
        parameters: Strategy parameters
    
    Returns:
        Deployment status and session info
    """
    db = get_db()
    client = get_paper_client()
    
    if not client.configured:
        return {
            "success": False,
            "error": "Alpaca paper trading not configured. Set ALPACA_PAPER_KEY and ALPACA_PAPER_SECRET."
        }
    
    try:
        # Get account info
        account = client.get_account()
        
        if account.trading_blocked:
            return {
                "success": False,
                "error": "Trading is blocked on this account"
            }
        
        # Generate session ID
        session_id = f"PAPER_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Store session in database
        if db.connected:
            db.create_session(
                session_id=session_id,
                session_type="PAPER",
                algorithm_name=algorithm_name,
                start_date=date.today(),
                end_date=date.today(),  # Will be updated
                initial_cash=account.cash,
                parameters=parameters or {}
            )
            
            db.update_session_status(session_id, "RUNNING")
            
            # Update parameters if provided
            if parameters:
                db.update_parameters_batch(algorithm_name, parameters)
            
            db.log_operation(
                operation="DEPLOY_PAPER",
                session_id=session_id,
                details={"algorithm": algorithm_name, "parameters": parameters},
                success=True
            )
        
        return {
            "success": True,
            "session_id": session_id,
            "mode": "PAPER",
            "algorithm": algorithm_name,
            "account": {
                "cash": account.cash,
                "portfolio_value": account.portfolio_value,
                "buying_power": account.buying_power
            },
            "message": f"Algorithm {algorithm_name} deployed to paper trading"
        }
        
    except AlpacaError as e:
        return {
            "success": False,
            "error": str(e)
        }


async def deploy_live(
    algorithm_name: str = "TQQQScalpingAlgorithm",
    confirm_code: str = "",
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Deploy algorithm to Alpaca live trading.
    REQUIRES: LIVE_DEPLOY_ENABLED=true and correct confirmation code.
    
    Args:
        algorithm_name: Algorithm to deploy
        confirm_code: Safety confirmation code
        parameters: Strategy parameters
    
    Returns:
        Deployment status (or rejection if safety checks fail)
    """
    config = get_config()
    db = get_db()
    
    # Safety checks
    if not config.safety.live_deploy_enabled:
        return {
            "success": False,
            "error": "Live deployment is DISABLED. Set LIVE_DEPLOY_ENABLED=true to enable.",
            "safety_status": "BLOCKED"
        }
    
    if confirm_code != config.safety.live_confirm_code:
        return {
            "success": False,
            "error": "Invalid confirmation code. Live deployment requires correct confirmation.",
            "safety_status": "BLOCKED"
        }
    
    client = get_live_client()
    
    if not client.configured:
        return {
            "success": False,
            "error": "Alpaca live trading not configured. Set ALPACA_LIVE_KEY and ALPACA_LIVE_SECRET."
        }
    
    try:
        # Get account info
        account = client.get_account()
        
        if account.trading_blocked:
            return {
                "success": False,
                "error": "Trading is blocked on this account"
            }
        
        # Generate session ID
        session_id = f"LIVE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Store session
        if db.connected:
            db.create_session(
                session_id=session_id,
                session_type="LIVE",
                algorithm_name=algorithm_name,
                start_date=date.today(),
                end_date=date.today(),
                initial_cash=account.cash,
                parameters=parameters or {}
            )
            
            db.update_session_status(session_id, "RUNNING")
            
            if parameters:
                db.update_parameters_batch(algorithm_name, parameters)
            
            db.log_operation(
                operation="DEPLOY_LIVE",
                session_id=session_id,
                details={"algorithm": algorithm_name, "parameters": parameters},
                success=True
            )
        
        logger.warning(f"LIVE DEPLOYMENT: {algorithm_name} deployed to live trading")
        
        return {
            "success": True,
            "session_id": session_id,
            "mode": "LIVE",
            "algorithm": algorithm_name,
            "account": {
                "cash": account.cash,
                "portfolio_value": account.portfolio_value,
                "buying_power": account.buying_power
            },
            "warning": "LIVE TRADING ACTIVE - Real money at risk",
            "message": f"Algorithm {algorithm_name} deployed to LIVE trading"
        }
        
    except AlpacaError as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================
# ALGORITHM CONTROL TOOLS
# ============================================

async def stop_algorithm(
    session_id: Optional[str] = None,
    mode: str = "paper",
    reason: str = "Manual stop requested"
) -> Dict[str, Any]:
    """
    Stop a running algorithm.
    
    Args:
        session_id: Session to stop (optional - stops current if not specified)
        mode: Trading mode (paper/live)
        reason: Reason for stopping
    
    Returns:
        Stop status and final positions
    """
    db = get_db()
    client = get_paper_client() if mode == "paper" else get_live_client()
    
    try:
        # Get final positions before stopping
        positions = client.get_positions()
        
        # Update session status
        if db.connected and session_id:
            db.update_session_status(session_id, "STOPPED", notes=reason)
            
            db.log_operation(
                operation="STOP_ALGORITHM",
                session_id=session_id,
                details={"reason": reason, "mode": mode},
                success=True
            )
        
        return {
            "success": True,
            "session_id": session_id,
            "mode": mode,
            "reason": reason,
            "final_positions": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "market_value": p.market_value,
                    "unrealized_pnl": p.unrealized_pnl
                }
                for p in positions
            ],
            "message": "Algorithm stopped successfully"
        }
        
    except AlpacaError as e:
        return {
            "success": False,
            "error": str(e)
        }


async def get_algorithm_status(
    session_id: Optional[str] = None,
    mode: str = "paper"
) -> Dict[str, Any]:
    """
    Get current algorithm status, positions, and P&L.
    
    Args:
        session_id: Session ID (optional)
        mode: Trading mode (paper/live)
    
    Returns:
        Current status with account and position details
    """
    db = get_db()
    client = get_paper_client() if mode == "paper" else get_live_client()
    
    if not client.configured:
        return {
            "success": False,
            "error": f"Alpaca {mode} trading not configured"
        }
    
    try:
        account = client.get_account()
        positions = client.get_positions()
        
        # Get session info from database
        session_info = None
        if db.connected and session_id:
            session_info = db.get_session(session_id)
        
        # Calculate total P&L
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        
        return {
            "success": True,
            "mode": mode,
            "session_id": session_id,
            "session_status": session_info.get("Status") if session_info else "UNKNOWN",
            "account": {
                "status": account.status,
                "cash": account.cash,
                "portfolio_value": account.portfolio_value,
                "buying_power": account.buying_power,
                "day_trade_count": account.day_trade_count,
                "pattern_day_trader": account.pattern_day_trader,
                "trading_blocked": account.trading_blocked
            },
            "positions": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "side": p.side,
                    "market_value": p.market_value,
                    "cost_basis": p.cost_basis,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl,
                    "unrealized_pnl_pct": p.unrealized_pnl_pct
                }
                for p in positions
            ],
            "summary": {
                "position_count": len(positions),
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_market_value": sum(p.market_value for p in positions)
            }
        }
        
    except AlpacaError as e:
        return {
            "success": False,
            "error": str(e)
        }


async def update_parameters(
    algorithm_name: str = "TQQQScalpingAlgorithm",
    parameters: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Update strategy parameters (hot reload).
    
    Args:
        algorithm_name: Algorithm to update
        parameters: New parameter values
    
    Returns:
        Update status with old and new values
    """
    db = get_db()
    
    if not parameters:
        return {
            "success": False,
            "error": "No parameters provided"
        }
    
    if not db.connected:
        return {
            "success": False,
            "error": "Database not connected"
        }
    
    # Get old values
    old_params = db.get_parameters(algorithm_name)
    
    # Update parameters
    success = db.update_parameters_batch(algorithm_name, parameters)
    
    # Get new values
    new_params = db.get_parameters(algorithm_name)
    
    # Log operation
    db.log_operation(
        operation="UPDATE_PARAMETERS",
        session_id=None,
        details={
            "algorithm": algorithm_name,
            "old_params": old_params,
            "new_params": parameters
        },
        success=success
    )
    
    return {
        "success": success,
        "algorithm": algorithm_name,
        "changes": {
            name: {
                "old": old_params.get(name),
                "new": value
            }
            for name, value in parameters.items()
        },
        "current_parameters": new_params,
        "message": "Parameters updated successfully" if success else "Some parameters failed to update"
    }


async def liquidate_positions(
    mode: str = "paper",
    symbols: Optional[List[str]] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Emergency position liquidation.
    
    Args:
        mode: Trading mode (paper/live)
        symbols: Specific symbols to liquidate (None = all)
        confirm: Must be True for live mode
    
    Returns:
        Liquidation results
    """
    db = get_db()
    client = get_paper_client() if mode == "paper" else get_live_client()
    
    # Extra safety for live mode
    if mode == "live" and not confirm:
        return {
            "success": False,
            "error": "Live liquidation requires confirm=true",
            "warning": "This will sell ALL positions at market price"
        }
    
    if not client.configured:
        return {
            "success": False,
            "error": f"Alpaca {mode} trading not configured"
        }
    
    try:
        # Get positions before liquidation
        positions_before = client.get_positions()
        
        if not positions_before:
            return {
                "success": True,
                "message": "No positions to liquidate"
            }
        
        # Liquidate
        if symbols:
            # Liquidate specific symbols
            results = []
            for symbol in symbols:
                success = client.close_position(symbol)
                results.append({"symbol": symbol, "closed": success})
        else:
            # Liquidate all
            success = client.close_all_positions()
            results = [{"all_positions": True, "closed": success}]
        
        # Log operation
        if db.connected:
            db.log_operation(
                operation="LIQUIDATE_POSITIONS",
                session_id=None,
                details={
                    "mode": mode,
                    "symbols": symbols or "ALL",
                    "positions_before": [
                        {"symbol": p.symbol, "quantity": p.quantity, "value": p.market_value}
                        for p in positions_before
                    ]
                },
                success=True
            )
        
        logger.warning(f"LIQUIDATION executed in {mode} mode: {symbols or 'ALL'}")
        
        return {
            "success": True,
            "mode": mode,
            "liquidated": results,
            "positions_closed": len(positions_before) if not symbols else len(symbols),
            "total_value_liquidated": sum(p.market_value for p in positions_before),
            "message": "Positions liquidated successfully"
        }
        
    except AlpacaError as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================
# UTILITY TOOLS
# ============================================

async def get_available_algorithms() -> Dict[str, Any]:
    """
    List available algorithms in the LEAN workspace.
    
    Returns:
        List of algorithm names
    """
    engine = get_engine()
    algorithms = engine.get_available_algorithms()
    
    return {
        "success": True,
        "count": len(algorithms),
        "algorithms": algorithms,
        "algorithm_path": str(engine.algorithm_path)
    }


async def health_check() -> Dict[str, Any]:
    """
    Check health of all connected services.
    
    Returns:
        Status of database, LEAN engine, and Alpaca connections
    """
    db = get_db()
    config = get_config()
    paper_client = get_paper_client()
    
    # Check database
    db_status = "connected" if db.connected else "disconnected"
    
    # Check LEAN engine
    engine = get_engine()
    lean_status = "available" if engine.lean_path.exists() else "not_found"
    
    # Check Alpaca paper
    alpaca_paper_status = "not_configured"
    if paper_client.configured:
        try:
            account = paper_client.get_account()
            alpaca_paper_status = f"connected (${account.portfolio_value:.2f})"
        except Exception:
            alpaca_paper_status = "error"
    
    # Check Alpaca live
    alpaca_live_status = "not_configured"
    if config.alpaca.live_configured:
        alpaca_live_status = "configured (disabled)" if not config.safety.live_deploy_enabled else "configured (enabled)"
    
    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": db_status,
            "lean_engine": lean_status,
            "alpaca_paper": alpaca_paper_status,
            "alpaca_live": alpaca_live_status
        },
        "configuration": {
            "lean_path": str(engine.lean_path),
            "results_path": str(engine.results_path),
            "live_trading_enabled": config.safety.live_deploy_enabled,
            "max_position_size": config.safety.max_position_size,
            "daily_loss_limit": config.safety.daily_loss_limit
        }
    }
