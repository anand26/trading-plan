"""
Test fixtures - Market data generators.
"""

from datetime import datetime, timedelta
from typing import Optional
import random


def generate_price_series(
    start_price: float,
    num_points: int,
    volatility: float = 0.02,
    trend: float = 0.0,
) -> list[float]:
    """Generate a realistic price series."""
    prices = [start_price]
    for _ in range(num_points - 1):
        change = random.gauss(trend, volatility)
        new_price = prices[-1] * (1 + change)
        prices.append(max(0.01, new_price))
    return prices


def generate_market_data(
    symbol: str = "TQQQ",
    start_time: Optional[datetime] = None,
    num_bars: int = 100,
    interval_minutes: int = 1,
) -> list[dict]:
    """Generate sample market data bars."""
    if start_time is None:
        start_time = datetime.now() - timedelta(minutes=num_bars * interval_minutes)
    
    base_price = 45.0 if symbol == "TQQQ" else 12.0 if symbol == "SQQQ" else 380.0
    prices = generate_price_series(base_price, num_bars, volatility=0.005)
    
    data = []
    current_time = start_time
    
    for i, close in enumerate(prices):
        high = close * (1 + random.uniform(0, 0.005))
        low = close * (1 - random.uniform(0, 0.005))
        open_price = prices[i - 1] if i > 0 else close
        volume = random.randint(100000, 500000)
        
        data.append({
            "symbol": symbol,
            "timestamp": current_time,
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": volume,
        })
        
        current_time += timedelta(minutes=interval_minutes)
    
    return data


def calculate_indicators(prices: list[float]) -> dict:
    """Calculate technical indicators from price series."""
    if len(prices) < 14:
        return {"rsi": 50.0, "momentum": 0.0, "volatility": 0.0}
    
    # RSI calculation (simplified)
    gains = []
    losses = []
    for i in range(1, min(15, len(prices))):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    
    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    # Momentum (price change over 10 periods)
    if len(prices) >= 10:
        momentum = (prices[-1] - prices[-10]) / prices[-10]
    else:
        momentum = 0.0
    
    # Volatility (standard deviation of returns)
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
    if returns:
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5
    else:
        volatility = 0.0
    
    return {
        "rsi": round(rsi, 2),
        "momentum": round(momentum, 4),
        "volatility": round(volatility, 4),
    }


def sample_market_conditions():
    """Generate various market condition scenarios."""
    return {
        "bullish_trending": {
            "rsi": 65.0,
            "momentum": 0.05,
            "volatility": 0.015,
            "regime": "BULLISH",
            "regime_confidence": 0.8,
        },
        "bearish_trending": {
            "rsi": 35.0,
            "momentum": -0.05,
            "volatility": 0.02,
            "regime": "BEARISH",
            "regime_confidence": 0.75,
        },
        "oversold_reversal": {
            "rsi": 22.0,
            "momentum": -0.08,
            "volatility": 0.035,
            "regime": "VOLATILE",
            "regime_confidence": 0.6,
        },
        "overbought_reversal": {
            "rsi": 78.0,
            "momentum": 0.06,
            "volatility": 0.025,
            "regime": "BULLISH",
            "regime_confidence": 0.7,
        },
        "neutral_consolidation": {
            "rsi": 50.0,
            "momentum": 0.001,
            "volatility": 0.01,
            "regime": "NEUTRAL",
            "regime_confidence": 0.65,
        },
        "high_volatility_crash": {
            "rsi": 18.0,
            "momentum": -0.15,
            "volatility": 0.06,
            "regime": "BEARISH",
            "regime_confidence": 0.9,
        },
    }
