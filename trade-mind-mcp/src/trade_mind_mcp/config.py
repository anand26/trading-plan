"""
Configuration Module
====================
Manages environment variables and settings for Trade-Mind MCP.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv


# Load .env file if present
load_dotenv()


@dataclass
class DatabaseConfig:
    """SQL Server database configuration."""
    server: str = field(default_factory=lambda: os.getenv("SQL_SERVER", "localhost"))
    database: str = field(default_factory=lambda: os.getenv("SQL_DATABASE", "TradingDB"))
    trusted_connection: bool = field(
        default_factory=lambda: os.getenv("SQL_TRUSTED_CONNECTION", "yes").lower() == "yes"
    )
    username: Optional[str] = field(default_factory=lambda: os.getenv("SQL_USERNAME"))
    password: Optional[str] = field(default_factory=lambda: os.getenv("SQL_PASSWORD"))
    
    def get_connection_string(self) -> str:
        """Build ODBC connection string."""
        if self.trusted_connection:
            return (
                f"Driver={{ODBC Driver 17 for SQL Server}};"
                f"Server={self.server};"
                f"Database={self.database};"
                "Trusted_Connection=yes;"
            )
        else:
            return (
                f"Driver={{ODBC Driver 17 for SQL Server}};"
                f"Server={self.server};"
                f"Database={self.database};"
                f"UID={self.username};"
                f"PWD={self.password};"
            )


@dataclass
class AnalysisConfig:
    """Analysis and statistics settings."""
    min_trades_for_stats: int = field(
        default_factory=lambda: int(os.getenv("MIN_TRADES_FOR_STATS", "5"))
    )
    min_confidence_threshold: float = field(
        default_factory=lambda: float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.6"))
    )
    lookback_days_default: int = field(
        default_factory=lambda: int(os.getenv("LOOKBACK_DAYS_DEFAULT", "30"))
    )


@dataclass
class LearningConfig:
    """Learning and adaptation settings."""
    learning_enabled: bool = field(
        default_factory=lambda: os.getenv("LEARNING_ENABLED", "true").lower() == "true"
    )
    auto_suggest_enabled: bool = field(
        default_factory=lambda: os.getenv("AUTO_SUGGEST_ENABLED", "true").lower() == "true"
    )


@dataclass
class Config:
    """Master configuration container."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    learning: LearningConfig = field(default_factory=LearningConfig)


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config


def reload_config() -> Config:
    """Reload configuration from environment."""
    global config
    load_dotenv(override=True)
    config = Config()
    return config
