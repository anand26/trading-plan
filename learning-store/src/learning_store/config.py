"""
Configuration management for the Learning Store.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


# Load environment variables
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    server: str
    database: str
    driver: str
    username: str | None = None
    password: str | None = None
    
    @property
    def connection_string(self) -> str:
        """Build the pyodbc connection string."""
        if self.username and self.password:
            return (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"UID={self.username};"
                f"PWD={self.password}"
            )
        else:
            return (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"Trusted_Connection=yes"
            )


@dataclass
class LearningConfig:
    """Learning store configuration."""
    min_confidence_threshold: float
    max_learning_age_days: int
    pattern_decay_rate: float
    recommendation_min_samples: int
    debug: bool


@dataclass
class LearningStoreConfig:
    """Main configuration class for Learning Store (used by tests)."""
    db_server: str
    db_name: str
    min_pattern_confidence: float
    pattern_decay_days: int
    driver: str = "ODBC Driver 17 for SQL Server"
    username: str | None = None
    password: str | None = None
    
    @property
    def connection_string(self) -> str:
        """Build the pyodbc connection string."""
        if self.username and self.password:
            return (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={self.db_server};"
                f"DATABASE={self.db_name};"
                f"UID={self.username};"
                f"PWD={self.password}"
            )
        else:
            return (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={self.db_server};"
                f"DATABASE={self.db_name};"
                f"Trusted_Connection=yes"
            )


def get_database_config() -> DatabaseConfig:
    """Get database configuration from environment."""
    return DatabaseConfig(
        server=os.getenv("DB_SERVER", "localhost"),
        database=os.getenv("DB_NAME", "TradingDB"),
        driver=os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server"),
        username=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"),
    )


def get_learning_config() -> LearningConfig:
    """Get learning configuration from environment."""
    return LearningConfig(
        min_confidence_threshold=float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.3")),
        max_learning_age_days=int(os.getenv("MAX_LEARNING_AGE_DAYS", "90")),
        pattern_decay_rate=float(os.getenv("PATTERN_DECAY_RATE", "0.95")),
        recommendation_min_samples=int(os.getenv("RECOMMENDATION_MIN_SAMPLES", "10")),
        debug=os.getenv("DEBUG", "false").lower() == "true",
    )


# Global config instances
db_config = get_database_config()
learning_config = get_learning_config()
