"""
Pattern Recognition Engine for the Learning Store.

Detects trading patterns from historical data and market conditions.
"""

from dataclasses import dataclass
from typing import Optional
from collections import defaultdict
import numpy as np

from .models import (
    Pattern, PatternType, MarketRegime, TradeFeatures, MarketConditions
)
from .database import get_trade_features, save_pattern, update_pattern, get_patterns


@dataclass
class PatternMatch:
    """A pattern match result."""
    pattern: Pattern
    match_score: float
    matching_conditions: list[str]


class PatternRecognizer:
    """
    Recognizes trading patterns from historical trade data.
    
    This engine analyzes trades to identify recurring patterns that
    lead to profitable outcomes.
    """
    
    def __init__(self):
        self._pattern_cache: dict[int, Pattern] = {}
        self._reload_patterns()
    
    def _reload_patterns(self):
        """Reload patterns from database."""
        patterns = get_patterns(active_only=True)
        self._pattern_cache = {p.pattern_id: p for p in patterns if p.pattern_id}
    
    def analyze_trades(self, days: int = 30) -> list[Pattern]:
        """
        Analyze recent trades to discover or update patterns.
        
        Returns list of new or updated patterns.
        """
        features = get_trade_features(days=days)
        if not features:
            return []
        
        discovered = []
        
        # Analyze entry timing patterns
        entry_patterns = self._analyze_entry_timing(features)
        discovered.extend(entry_patterns)
        
        # Analyze exit timing patterns
        exit_patterns = self._analyze_exit_timing(features)
        discovered.extend(exit_patterns)
        
        # Analyze regime-specific patterns
        regime_patterns = self._analyze_regime_patterns(features)
        discovered.extend(regime_patterns)
        
        # Analyze holding period patterns
        holding_patterns = self._analyze_holding_patterns(features)
        discovered.extend(holding_patterns)
        
        return discovered
    
    def _analyze_entry_timing(self, features: list[TradeFeatures]) -> list[Pattern]:
        """Analyze entry timing patterns by hour."""
        patterns = []
        
        # Group by entry hour
        by_hour = defaultdict(list)
        for f in features:
            by_hour[f.entry_hour].append(f)
        
        for hour, trades in by_hour.items():
            if len(trades) < 5:  # Need minimum sample size
                continue
            
            winners = [t for t in trades if t.is_winner]
            win_rate = len(winners) / len(trades)
            avg_pnl = np.mean([t.pnl for t in trades])
            
            # Check if this hour is significantly better than average
            if win_rate >= 0.55 and avg_pnl > 0:
                pattern = Pattern(
                    pattern_type=PatternType.ENTRY_TIMING,
                    name=f"Profitable Entry Hour {hour}",
                    description=f"Entries at hour {hour} show {win_rate:.1%} win rate",
                    conditions={"entry_hour": hour},
                    expected_outcome="PROFITABLE",
                    confidence=min(0.9, 0.5 + (len(trades) / 100)),
                    sample_size=len(trades),
                    win_rate=win_rate,
                    avg_pnl=float(avg_pnl)
                )
                
                # Save or update pattern
                existing = self._find_similar_pattern(pattern)
                if existing:
                    existing.sample_size = len(trades)
                    existing.win_rate = win_rate
                    existing.avg_pnl = float(avg_pnl)
                    existing.confidence = pattern.confidence
                    update_pattern(existing)
                    patterns.append(existing)
                else:
                    pattern.pattern_id = save_pattern(pattern)
                    patterns.append(pattern)
        
        return patterns
    
    def _analyze_exit_timing(self, features: list[TradeFeatures]) -> list[Pattern]:
        """Analyze exit timing patterns."""
        patterns = []
        
        # Group by exit hour
        by_hour = defaultdict(list)
        for f in features:
            by_hour[f.exit_hour].append(f)
        
        for hour, trades in by_hour.items():
            if len(trades) < 5:
                continue
            
            winners = [t for t in trades if t.is_winner]
            win_rate = len(winners) / len(trades)
            avg_pnl = np.mean([t.pnl for t in trades])
            
            if win_rate >= 0.55 and avg_pnl > 0:
                pattern = Pattern(
                    pattern_type=PatternType.EXIT_TIMING,
                    name=f"Profitable Exit Hour {hour}",
                    description=f"Exits at hour {hour} show {win_rate:.1%} win rate",
                    conditions={"exit_hour": hour},
                    expected_outcome="PROFITABLE",
                    confidence=min(0.9, 0.5 + (len(trades) / 100)),
                    sample_size=len(trades),
                    win_rate=win_rate,
                    avg_pnl=float(avg_pnl)
                )
                
                existing = self._find_similar_pattern(pattern)
                if existing:
                    existing.sample_size = len(trades)
                    existing.win_rate = win_rate
                    existing.avg_pnl = float(avg_pnl)
                    update_pattern(existing)
                    patterns.append(existing)
                else:
                    pattern.pattern_id = save_pattern(pattern)
                    patterns.append(pattern)
        
        return patterns
    
    def _analyze_regime_patterns(self, features: list[TradeFeatures]) -> list[Pattern]:
        """Analyze patterns specific to market regimes."""
        patterns = []
        
        # Group by regime
        by_regime = defaultdict(list)
        for f in features:
            if f.regime_at_entry:
                by_regime[f.regime_at_entry].append(f)
        
        for regime, trades in by_regime.items():
            if len(trades) < 10:
                continue
            
            # Analyze by symbol within regime
            by_symbol = defaultdict(list)
            for t in trades:
                by_symbol[t.symbol].append(t)
            
            for symbol, symbol_trades in by_symbol.items():
                if len(symbol_trades) < 5:
                    continue
                
                winners = [t for t in symbol_trades if t.is_winner]
                win_rate = len(winners) / len(symbol_trades)
                avg_pnl = np.mean([t.pnl for t in symbol_trades])
                
                if win_rate >= 0.5:
                    pattern = Pattern(
                        pattern_type=PatternType.REGIME_DETECTION,
                        name=f"{symbol} in {regime.value} Regime",
                        description=f"{symbol} shows {win_rate:.1%} win rate in {regime.value} regime",
                        conditions={"symbol": symbol, "regime": regime.value},
                        expected_outcome="PROFITABLE" if avg_pnl > 0 else "UNPROFITABLE",
                        confidence=min(0.9, 0.5 + (len(symbol_trades) / 100)),
                        sample_size=len(symbol_trades),
                        win_rate=win_rate,
                        avg_pnl=float(avg_pnl),
                        regime=regime
                    )
                    
                    existing = self._find_similar_pattern(pattern)
                    if existing:
                        existing.sample_size = len(symbol_trades)
                        existing.win_rate = win_rate
                        existing.avg_pnl = float(avg_pnl)
                        update_pattern(existing)
                        patterns.append(existing)
                    else:
                        pattern.pattern_id = save_pattern(pattern)
                        patterns.append(pattern)
        
        return patterns
    
    def _analyze_holding_patterns(self, features: list[TradeFeatures]) -> list[Pattern]:
        """Analyze optimal holding period patterns."""
        patterns = []
        
        # Bucket by holding time
        buckets = {
            "quick": (0, 5),      # 0-5 minutes
            "short": (5, 15),     # 5-15 minutes
            "medium": (15, 30),   # 15-30 minutes
            "long": (30, 60),     # 30-60 minutes
            "extended": (60, 240) # 1-4 hours
        }
        
        for bucket_name, (min_mins, max_mins) in buckets.items():
            bucket_trades = [
                f for f in features
                if min_mins <= f.holding_minutes < max_mins
            ]
            
            if len(bucket_trades) < 10:
                continue
            
            winners = [t for t in bucket_trades if t.is_winner]
            win_rate = len(winners) / len(bucket_trades)
            avg_pnl = np.mean([t.pnl for t in bucket_trades])
            
            pattern = Pattern(
                pattern_type=PatternType.POSITION_SIZING,
                name=f"Holding Period: {bucket_name.title()}",
                description=f"Trades held {min_mins}-{max_mins} min: {win_rate:.1%} win rate, ${avg_pnl:.2f} avg",
                conditions={
                    "holding_min_minutes": min_mins,
                    "holding_max_minutes": max_mins
                },
                expected_outcome="PROFITABLE" if avg_pnl > 0 else "UNPROFITABLE",
                confidence=min(0.9, 0.5 + (len(bucket_trades) / 100)),
                sample_size=len(bucket_trades),
                win_rate=win_rate,
                avg_pnl=float(avg_pnl)
            )
            
            existing = self._find_similar_pattern(pattern)
            if existing:
                existing.sample_size = len(bucket_trades)
                existing.win_rate = win_rate
                existing.avg_pnl = float(avg_pnl)
                update_pattern(existing)
                patterns.append(existing)
            else:
                pattern.pattern_id = save_pattern(pattern)
                patterns.append(pattern)
        
        return patterns
    
    def _find_similar_pattern(self, pattern: Pattern) -> Optional[Pattern]:
        """Find an existing similar pattern."""
        for existing in self._pattern_cache.values():
            if (existing.pattern_type == pattern.pattern_type and
                existing.name == pattern.name):
                return existing
        return None
    
    def match_conditions(
        self,
        conditions: MarketConditions
    ) -> list[PatternMatch]:
        """
        Find patterns that match current market conditions.
        
        Returns list of matching patterns sorted by match score.
        """
        self._reload_patterns()
        matches = []
        
        for pattern in self._pattern_cache.values():
            match_score, matching = self._calculate_match(pattern, conditions)
            if match_score > 0.5:
                matches.append(PatternMatch(
                    pattern=pattern,
                    match_score=match_score,
                    matching_conditions=matching
                ))
        
        # Sort by match score * confidence
        matches.sort(
            key=lambda m: m.match_score * m.pattern.confidence,
            reverse=True
        )
        
        return matches
    
    def _calculate_match(
        self,
        pattern: Pattern,
        conditions: MarketConditions
    ) -> tuple[float, list[str]]:
        """Calculate how well conditions match a pattern."""
        matching = []
        total_conditions = len(pattern.conditions)
        
        if total_conditions == 0:
            return 0.0, []
        
        matched_count = 0
        
        for key, value in pattern.conditions.items():
            if key == "entry_hour" and value == conditions.hour_of_day:
                matching.append(f"entry_hour={value}")
                matched_count += 1
            elif key == "regime" and value == conditions.regime.value:
                matching.append(f"regime={value}")
                matched_count += 1
            elif key == "rsi_oversold" and conditions.rsi < 30:
                matching.append(f"rsi_oversold (RSI={conditions.rsi:.1f})")
                matched_count += 1
            elif key == "rsi_overbought" and conditions.rsi > 70:
                matching.append(f"rsi_overbought (RSI={conditions.rsi:.1f})")
                matched_count += 1
            elif key == "high_volatility" and conditions.volatility > value:
                matching.append(f"high_volatility={conditions.volatility:.3f}")
                matched_count += 1
            elif key == "positive_momentum" and conditions.momentum > 0:
                matching.append(f"positive_momentum={conditions.momentum:.4f}")
                matched_count += 1
            elif key == "negative_momentum" and conditions.momentum < 0:
                matching.append(f"negative_momentum={conditions.momentum:.4f}")
                matched_count += 1
        
        # Check regime match (patterns can be regime-specific)
        if pattern.regime and pattern.regime == conditions.regime:
            matched_count += 0.5  # Bonus for regime match
        
        score = matched_count / total_conditions if total_conditions > 0 else 0
        return min(1.0, score), matching
    
    def get_top_patterns(
        self,
        pattern_type: Optional[PatternType] = None,
        regime: Optional[MarketRegime] = None,
        limit: int = 10
    ) -> list[Pattern]:
        """Get top performing patterns."""
        patterns = get_patterns(
            pattern_type=pattern_type,
            regime=regime,
            min_confidence=0.3
        )
        
        # Sort by win_rate * confidence * sample_size factor
        patterns.sort(
            key=lambda p: p.win_rate * p.confidence * min(1.0, p.sample_size / 50),
            reverse=True
        )
        
        return patterns[:limit]
