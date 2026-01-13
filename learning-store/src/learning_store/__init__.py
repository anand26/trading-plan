"""
Learning Store - Intelligence Persistence Layer

The core intelligence module for the TQQQ/SQQQ adaptive trading system.
"""

__version__ = "0.1.0"

from .store import LearningStore
from .models import (
    Pattern,
    PatternType,
    Learning,
    LearningType,
    Recommendation,
    MarketConditions,
)
from .patterns import PatternRecognizer
from .learner import AdaptiveLearner
from .recommender import RecommendationEngine

__all__ = [
    "LearningStore",
    "Pattern",
    "PatternType",
    "Learning",
    "LearningType",
    "Recommendation",
    "MarketConditions",
    "PatternRecognizer",
    "AdaptiveLearner",
    "RecommendationEngine",
]
