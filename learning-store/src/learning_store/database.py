"""
Database connection and query utilities for the Learning Store.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Any
import json

try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

from .config import db_config, learning_config
from .models import (
    Pattern, PatternType, Learning, LearningType,
    Recommendation, MarketRegime, ParameterPerformance, TradeFeatures
)


class DatabaseConnection:
    """SQL Server database connection manager."""
    
    def __init__(self):
        self._connection: Optional["pyodbc.Connection"] = None
    
    def connect(self) -> bool:
        """Establish database connection."""
        if not PYODBC_AVAILABLE:
            return False
        try:
            import pyodbc
            self._connection = pyodbc.connect(db_config.connection_string)
            return True
        except Exception as e:
            print(f"Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to database."""
        return self._connection is not None
    
    def ensure_connected(self):
        """Ensure connection is established."""
        if not self.is_connected:
            self.connect()
    
    def query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        """Execute a query and return results as DataFrame."""
        self.ensure_connected()
        if not self.is_connected or self._connection is None:
            return pd.DataFrame()
        
        try:
            return pd.read_sql(sql, self._connection, params=params)  # type: ignore[arg-type]
        except Exception as e:
            print(f"Query failed: {e}")
            return pd.DataFrame()
    
    def execute(self, sql: str, params: tuple = ()) -> bool:
        """Execute a non-query SQL statement."""
        self.ensure_connected()
        if not self.is_connected or self._connection is None:
            return False
        
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, params)
            self._connection.commit()
            return True
        except Exception as e:
            print(f"Execution failed: {e}")
            return False
    
    def execute_scalar(self, sql: str, params: tuple = ()) -> Any:
        """Execute a query and return single value."""
        self.ensure_connected()
        if not self.is_connected or self._connection is None:
            return None
        
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"Scalar query failed: {e}")
            return None


# Global database instance
_db: Optional[DatabaseConnection] = None


def get_db() -> DatabaseConnection:
    """Get database connection singleton."""
    global _db
    if _db is None:
        _db = DatabaseConnection()
        _db.connect()
    return _db


# ==================== Pattern Operations ====================

def save_pattern(pattern: Pattern) -> Optional[int]:
    """Save a pattern to the database."""
    db = get_db()
    
    sql = """
        INSERT INTO dbo.Patterns (
            PatternType, Name, Description, Conditions, ExpectedOutcome,
            Confidence, SampleSize, WinRate, AvgPnL, Regime, IsActive
        )
        OUTPUT INSERTED.PatternID
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    conditions_json = json.dumps(pattern.conditions)
    regime_str = pattern.regime.value if pattern.regime else None
    
    if db._connection is None:
        print("Database connection is None")
        return 0
    
    try:
        cursor = db._connection.cursor()
        cursor.execute(sql, (
            pattern.pattern_type.value,
            pattern.name,
            pattern.description,
            conditions_json,
            pattern.expected_outcome,
            pattern.confidence,
            pattern.sample_size,
            pattern.win_rate,
            pattern.avg_pnl,
            regime_str,
            pattern.is_active
        ))
        result = cursor.fetchone()
        if result is not None:
            pattern_id = result[0]
        else:
            pattern_id = 0
        db._connection.commit()
        return pattern_id
    except Exception as e:
        print(f"Failed to save pattern: {e}")
        return None


def update_pattern(pattern: Pattern) -> bool:
    """Update an existing pattern."""
    db = get_db()
    
    sql = """
        UPDATE dbo.Patterns
        SET Confidence = ?,
            SampleSize = ?,
            WinRate = ?,
            AvgPnL = ?,
            UpdatedAt = GETDATE(),
            IsActive = ?
        WHERE PatternID = ?
    """
    
    return db.execute(sql, (
        pattern.confidence,
        pattern.sample_size,
        pattern.win_rate,
        pattern.avg_pnl,
        pattern.is_active,
        pattern.pattern_id
    ))


def get_patterns(
    pattern_type: Optional[PatternType] = None,
    regime: Optional[MarketRegime] = None,
    min_confidence: Optional[float] = None,
    active_only: bool = True
) -> list[Pattern]:
    """Get patterns matching criteria."""
    db = get_db()
    
    sql = """
        SELECT PatternID, PatternType, Name, Description, Conditions,
               ExpectedOutcome, Confidence, SampleSize, WinRate, AvgPnL,
               Regime, CreatedAt, UpdatedAt, IsActive
        FROM dbo.Patterns
        WHERE 1=1
    """
    params = []
    
    if active_only:
        sql += " AND IsActive = 1"
    
    if pattern_type:
        sql += " AND PatternType = ?"
        params.append(pattern_type.value)
    
    if regime:
        sql += " AND (Regime = ? OR Regime IS NULL)"
        params.append(regime.value)
    
    if min_confidence:
        sql += " AND Confidence >= ?"
        params.append(min_confidence)
    
    sql += " ORDER BY Confidence DESC"
    
    df = db.query(sql, tuple(params))
    
    patterns = []
    for _, row in df.iterrows():
        patterns.append(Pattern(
            pattern_id=row["PatternID"],
            pattern_type=PatternType(row["PatternType"]),
            name=row["Name"],
            description=row["Description"],
            conditions=json.loads(row["Conditions"]) if row["Conditions"] else {},
            expected_outcome=row["ExpectedOutcome"],
            confidence=row["Confidence"],
            sample_size=row["SampleSize"],
            win_rate=row["WinRate"],
            avg_pnl=row["AvgPnL"],
            regime=MarketRegime(row["Regime"]) if row["Regime"] else None,
            created_at=row["CreatedAt"],
            updated_at=row["UpdatedAt"],
            is_active=row["IsActive"]
        ))
    
    return patterns


# ==================== Learning Operations ====================

def save_learning(learning: Learning) -> Optional[int]:
    """Save a learning event to the database."""
    db = get_db()
    
    sql = """
        INSERT INTO dbo.LearningStore (
            LearningType, Description, OldValue, NewValue,
            ConfidenceScore, Source, RelatedPatternID, RelatedTradeID, Metadata
        )
        OUTPUT INSERTED.LearningID
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    metadata_json = json.dumps(learning.metadata)
    
    if db._connection is None:
        print("Database connection is None")
        return 0
    
    try:
        cursor = db._connection.cursor()
        cursor.execute(sql, (
            learning.learning_type.value,
            learning.description,
            learning.old_value,
            learning.new_value,
            learning.confidence_score,
            learning.source,
            learning.related_pattern_id,
            learning.related_trade_id,
            metadata_json
        ))
        result = cursor.fetchone()
        if result is not None:
            learning_id = result[0]
        else:
            learning_id = 0
        db._connection.commit()
        return learning_id
    except Exception as e:
        print(f"Failed to save learning: {e}")
        return None


def get_learnings(
    learning_type: Optional[LearningType] = None,
    days: int = 30,
    limit: int = 100
) -> list[Learning]:
    """Get recent learning events."""
    db = get_db()
    
    sql = f"""
        SELECT TOP {limit}
            LearningID, Timestamp, LearningType, Description,
            OldValue, NewValue, ConfidenceScore, Source,
            RelatedPatternID, RelatedTradeID, Metadata
        FROM dbo.LearningStore
        WHERE Timestamp >= DATEADD(day, -?, GETDATE())
    """
    params: list[int | str] = [days]
    
    if learning_type:
        sql += " AND LearningType = ?"
        params.append(learning_type.value)
    
    sql += " ORDER BY Timestamp DESC"
    
    df = db.query(sql, tuple(params))
    
    learnings = []
    for _, row in df.iterrows():
        learnings.append(Learning(
            learning_id=row["LearningID"],
            learning_type=LearningType(row["LearningType"]),
            description=row["Description"],
            old_value=row["OldValue"],
            new_value=row["NewValue"],
            confidence_score=row["ConfidenceScore"],
            source=row["Source"],
            related_pattern_id=row["RelatedPatternID"],
            related_trade_id=row["RelatedTradeID"],
            metadata=json.loads(row["Metadata"]) if row["Metadata"] else {},
            timestamp=row["Timestamp"]
        ))
    
    return learnings


# ==================== Recommendation Operations ====================

def save_recommendation(rec: Recommendation) -> Optional[int]:
    """Save a recommendation to the database."""
    db = get_db()
    
    sql = """
        INSERT INTO dbo.Recommendations (
            ParameterName, CurrentValue, RecommendedValue, Confidence,
            ExpectedImprovement, Reasoning, SupportingPatterns, Regime, ValidUntil
        )
        OUTPUT INSERTED.RecommendationID
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    patterns_json = json.dumps(rec.supporting_patterns)
    regime_str = rec.regime.value if rec.regime else None
    
    if db._connection is None:
        print("Database connection is None")
        return None
    
    try:
        cursor = db._connection.cursor()
        cursor.execute(sql, (
            rec.parameter_name,
            str(rec.current_value),
            str(rec.recommended_value),
            rec.confidence,
            rec.expected_improvement,
            rec.reasoning,
            patterns_json,
            regime_str,
            rec.valid_until
        ))
        result = cursor.fetchone()
        if result is not None:
            rec_id = result[0]
        else:
            rec_id = None
        db._connection.commit()
        return rec_id
    except Exception as e:
        print(f"Failed to save recommendation: {e}")
        return None


def get_active_recommendations(
    parameter_name: Optional[str] = None,
    regime: Optional[MarketRegime] = None,
    min_confidence: float = 0.5
) -> list[Recommendation]:
    """Get active recommendations."""
    db = get_db()
    
    sql = """
        SELECT RecommendationID, ParameterName, CurrentValue, RecommendedValue,
               Confidence, ExpectedImprovement, Reasoning, SupportingPatterns,
               Regime, ValidUntil, CreatedAt, Applied, Outcome
        FROM dbo.Recommendations
        WHERE Applied = 0
          AND (ValidUntil IS NULL OR ValidUntil > GETDATE())
          AND Confidence >= ?
    """
    params: list[float | str] = [min_confidence]
    
    if parameter_name:
        sql += " AND ParameterName = ?"
        params.append(parameter_name)
    
    if regime:
        sql += " AND Regime = ?"
        params.append(regime.value)
    
    if regime:
        sql += " AND (Regime = ? OR Regime IS NULL)"
        params.append(regime.value)
    
    sql += " ORDER BY Confidence DESC, ExpectedImprovement DESC"
    
    df = db.query(sql, tuple(params))
    
    recommendations = []
    for _, row in df.iterrows():
        recommendations.append(Recommendation(
            recommendation_id=row["RecommendationID"],
            parameter_name=row["ParameterName"],
            current_value=row["CurrentValue"],
            recommended_value=row["RecommendedValue"],
            confidence=row["Confidence"],
            expected_improvement=row["ExpectedImprovement"],
            reasoning=row["Reasoning"],
            supporting_patterns=json.loads(row["SupportingPatterns"]) if row["SupportingPatterns"] else [],
            regime=MarketRegime(row["Regime"]) if row["Regime"] else None,
            valid_until=row["ValidUntil"],
            created_at=row["CreatedAt"],
            applied=row["Applied"],
            outcome=row["Outcome"]
        ))
    
    return recommendations


def mark_recommendation_applied(rec_id: int, outcome: Optional[str] = None) -> bool:
    """Mark a recommendation as applied."""
    db = get_db()
    
    sql = """
        UPDATE dbo.Recommendations
        SET Applied = 1,
            AppliedAt = GETDATE(),
            Outcome = ?
        WHERE RecommendationID = ?
    """
    
    return db.execute(sql, (outcome, rec_id))


# ==================== Trade Feature Extraction ====================

def get_trade_features(days: int = 30, limit: int = 1000) -> list[TradeFeatures]:
    """Extract features from recent trades for pattern learning."""
    db = get_db()
    
    sql = f"""
        SELECT TOP {limit}
            t.TradeID, t.Symbol, t.Side,
            DATEPART(HOUR, t.EntryTime) as EntryHour,
            DATEPART(HOUR, t.ExitTime) as ExitHour,
            t.HoldingPeriodSeconds / 60.0 as HoldingMinutes,
            t.PnL, t.PnLPercent,
            t.EntryReason, t.ExitReason, t.MarketRegime,
            CASE WHEN t.PnL > 0 THEN 1 ELSE 0 END as IsWinner
        FROM dbo.Trades t
        WHERE t.EntryTime >= DATEADD(day, -?, GETDATE())
        ORDER BY t.EntryTime DESC
    """
    
    df = db.query(sql, (days,))
    
    features = []
    for _, row in df.iterrows():
        features.append(TradeFeatures(
            trade_id=row["TradeID"],
            symbol=row["Symbol"],
            side=row["Side"],
            entry_hour=row["EntryHour"],
            exit_hour=row["ExitHour"],
            holding_minutes=row["HoldingMinutes"] or 0,
            pnl=row["PnL"],
            pnl_percent=row["PnLPercent"],
            is_winner=bool(row["IsWinner"]),
            entry_reason=row["EntryReason"],
            exit_reason=row["ExitReason"],
            regime_at_entry=MarketRegime(row["MarketRegime"]) if row["MarketRegime"] else None
        ))
    
    return features


# ==================== Parameter Performance ====================

def get_parameter_performance(parameter_name: str) -> list[ParameterPerformance]:
    """Get performance data for a parameter across different values."""
    db = get_db()
    
    sql = """
        SELECT ParameterName, ParameterValue, MarketRegime,
               TradeCount, WinRate, AvgPnL, TotalPnL,
               SharpeRatio, MaxDrawdown, FirstUsed, LastUsed
        FROM dbo.ParameterPerformance
        WHERE ParameterName = ?
        ORDER BY TotalPnL DESC
    """
    
    df = db.query(sql, (parameter_name,))
    
    performances = []
    for _, row in df.iterrows():
        performances.append(ParameterPerformance(
            parameter_name=row["ParameterName"],
            parameter_value=row["ParameterValue"],
            regime=MarketRegime(row["MarketRegime"]) if row["MarketRegime"] else None,
            trade_count=row["TradeCount"],
            win_rate=row["WinRate"],
            avg_pnl=row["AvgPnL"],
            total_pnl=row["TotalPnL"],
            sharpe_ratio=row["SharpeRatio"],
            max_drawdown=row["MaxDrawdown"],
            first_used=row["FirstUsed"],
            last_used=row["LastUsed"]
        ))
    
    return performances


def update_parameter_performance(perf: ParameterPerformance) -> bool:
    """Update or insert parameter performance data."""
    db = get_db()
    
    # Try update first
    sql_update = """
        UPDATE dbo.ParameterPerformance
        SET TradeCount = ?,
            WinRate = ?,
            AvgPnL = ?,
            TotalPnL = ?,
            SharpeRatio = ?,
            MaxDrawdown = ?,
            LastUsed = GETDATE()
        WHERE ParameterName = ? AND ParameterValue = ?
          AND (MarketRegime = ? OR (MarketRegime IS NULL AND ? IS NULL))
    """
    
    regime_str = perf.regime.value if perf.regime else None
    
    if db._connection is None:
        print("Database connection is None")
        return False
    
    cursor = db._connection.cursor()
    cursor.execute(sql_update, (
        perf.trade_count, perf.win_rate, perf.avg_pnl, perf.total_pnl,
        perf.sharpe_ratio, perf.max_drawdown,
        perf.parameter_name, str(perf.parameter_value), regime_str, regime_str
    ))
    
    if cursor.rowcount == 0:
        # Insert new record
        sql_insert = """
            INSERT INTO dbo.ParameterPerformance (
                ParameterName, ParameterValue, MarketRegime,
                TradeCount, WinRate, AvgPnL, TotalPnL,
                SharpeRatio, MaxDrawdown
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(sql_insert, (
            perf.parameter_name, str(perf.parameter_value), regime_str,
            perf.trade_count, perf.win_rate, perf.avg_pnl, perf.total_pnl,
            perf.sharpe_ratio, perf.max_drawdown
        ))
    
    db._connection.commit()
    return True
