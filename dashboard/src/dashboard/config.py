"""
Configuration management for the trading dashboard.
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
class DashboardConfig:
    """Dashboard configuration."""
    title: str
    refresh_interval: int
    debug: bool


def get_database_config() -> DatabaseConfig:
    """Get database configuration from environment."""
    return DatabaseConfig(
        server=os.getenv("DB_SERVER", "localhost"),
        database=os.getenv("DB_NAME", "TradingDB"),
        driver=os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server"),
        username=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"),
    )


def get_dashboard_config() -> DashboardConfig:
    """Get dashboard configuration from environment."""
    return DashboardConfig(
        title=os.getenv("DASHBOARD_TITLE", "TQQQ/SQQQ Trading Dashboard"),
        refresh_interval=int(os.getenv("REFRESH_INTERVAL_SECONDS", "30")),
        debug=os.getenv("DEBUG", "false").lower() == "true",
    )


# Global config instances
db_config = get_database_config()
dashboard_config = get_dashboard_config()
