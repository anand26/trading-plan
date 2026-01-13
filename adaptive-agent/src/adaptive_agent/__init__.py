"""
Adaptive Trading Agent - Orchestration Layer

Coordinates all trading system components with learning-based decisions.
"""

__version__ = "0.1.0"

from .agent import AdaptiveAgent
from .config import AgentConfig
from .models import (
    Decision,
    DecisionType,
    AgentState,
    MarketSnapshot,
    PerformanceSnapshot,
)
from .observer import Observer
from .analyzer import Analyzer
from .executor import Executor
from .decision_engine import DecisionEngine

__all__ = [
    "AdaptiveAgent",
    "AgentConfig",
    "Decision",
    "DecisionType",
    "AgentState",
    "MarketSnapshot",
    "PerformanceSnapshot",
    "Observer",
    "Analyzer",
    "Executor",
    "DecisionEngine",
]
