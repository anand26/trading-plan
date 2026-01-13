"""
Test fixtures - Trade data generators.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4
import random


def generate_trade(
    symbol: str = "TQQQ",
    side: str = "BUY",
    quantity: int = 100,
    entry_price: Optional[float] = None,
    pnl_pct: Optional[float] = None,
    trade_time: Optional[datetime] = None,
) -> dict:
    """Generate a single trade record."""
    if entry_price is None:
        entry_price = 45.0 + random.uniform(-2, 2)
    
    if pnl_pct is None:
        # Realistic PnL distribution: slight edge positive
        pnl_pct = random.gauss(0.002, 0.015)
    
    exit_price = entry_price * (1 + pnl_pct)
    pnl = (exit_price - entry_price) * quantity
    
    if trade_time is None:
        trade_time = datetime.now() - timedelta(hours=random.randint(1, 48))
    
    duration_minutes = random.randint(5, 120)
    
    return {
        "trade_id": f"T{uuid4().hex[:8].upper()}",
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "entry_price": round(entry_price, 2),
        "exit_price": round(exit_price, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct * 100, 2),
        "entry_time": trade_time,
        "exit_time": trade_time + timedelta(minutes=duration_minutes),
        "duration_minutes": duration_minutes,
        "status": "CLOSED",
    }


def generate_trade_history(
    num_trades: int = 50,
    win_rate: float = 0.55,
    avg_win_pct: float = 0.02,
    avg_loss_pct: float = -0.015,
) -> list[dict]:
    """Generate a trade history with specified characteristics."""
    trades = []
    current_time = datetime.now()
    
    for i in range(num_trades):
        is_winner = random.random() < win_rate
        
        if is_winner:
            pnl_pct = abs(random.gauss(avg_win_pct, 0.008))
        else:
            pnl_pct = -abs(random.gauss(abs(avg_loss_pct), 0.006))
        
        trade_time = current_time - timedelta(hours=i * 2 + random.randint(0, 4))
        
        trade = generate_trade(
            symbol=random.choice(["TQQQ", "SQQQ"]),
            quantity=random.choice([50, 100, 150, 200]),
            pnl_pct=pnl_pct,
            trade_time=trade_time,
        )
        trades.append(trade)
    
    return sorted(trades, key=lambda t: t["entry_time"], reverse=True)


def calculate_trade_stats(trades: list[dict]) -> dict:
    """Calculate statistics from trade history."""
    if not trades:
        return {
            "total_trades": 0,
            "total_pnl": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
        }
    
    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] <= 0]
    
    total_pnl = sum(t["pnl"] for t in trades)
    win_rate = len(winners) / len(trades) if trades else 0
    
    gross_profit = sum(t["pnl"] for t in winners) if winners else 0
    gross_loss = abs(sum(t["pnl"] for t in losers)) if losers else 0
    
    avg_win = gross_profit / len(winners) if winners else 0
    avg_loss = gross_loss / len(losers) if losers else 0
    
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Calculate max drawdown
    cumulative = 0
    peak = 0
    max_dd = 0
    
    for trade in sorted(trades, key=lambda t: t["entry_time"]):
        cumulative += trade["pnl"]
        peak = max(peak, cumulative)
        drawdown = (peak - cumulative) / peak if peak > 0 else 0
        max_dd = max(max_dd, drawdown)
    
    return {
        "total_trades": len(trades),
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_dd, 4),
        "winners": len(winners),
        "losers": len(losers),
    }


def generate_losing_streak(streak_length: int = 5) -> list[dict]:
    """Generate a sequence of losing trades."""
    trades = []
    current_time = datetime.now()
    
    for i in range(streak_length):
        trade = generate_trade(
            pnl_pct=-abs(random.gauss(0.012, 0.005)),
            trade_time=current_time - timedelta(hours=i),
        )
        trades.append(trade)
    
    return trades


def generate_winning_streak(streak_length: int = 5) -> list[dict]:
    """Generate a sequence of winning trades."""
    trades = []
    current_time = datetime.now()
    
    for i in range(streak_length):
        trade = generate_trade(
            pnl_pct=abs(random.gauss(0.015, 0.006)),
            trade_time=current_time - timedelta(hours=i),
        )
        trades.append(trade)
    
    return trades


def sample_performance_scenarios():
    """Generate various performance scenarios for testing."""
    return {
        "strong_performance": {
            "daily_pnl": 350.00,
            "weekly_pnl": 1200.00,
            "win_rate": 0.65,
            "current_drawdown": 0.02,
            "current_streak": 4,
        },
        "weak_performance": {
            "daily_pnl": -150.00,
            "weekly_pnl": -400.00,
            "win_rate": 0.40,
            "current_drawdown": 0.08,
            "current_streak": -3,
        },
        "emergency_drawdown": {
            "daily_pnl": -800.00,
            "weekly_pnl": -2000.00,
            "win_rate": 0.30,
            "current_drawdown": 0.18,
            "current_streak": -6,
        },
        "recovery_phase": {
            "daily_pnl": 100.00,
            "weekly_pnl": -200.00,
            "win_rate": 0.55,
            "current_drawdown": 0.05,
            "current_streak": 2,
        },
        "neutral_flat": {
            "daily_pnl": 25.00,
            "weekly_pnl": 50.00,
            "win_rate": 0.50,
            "current_drawdown": 0.01,
            "current_streak": 0,
        },
    }
