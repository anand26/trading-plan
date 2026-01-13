"""
Configuration Module
====================
Manages environment variables and settings for LEAN-Ops MCP.
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
class LeanConfig:
    """QuantConnect LEAN engine configuration."""
    lean_path: Path = field(
        default_factory=lambda: Path(os.getenv("LEAN_PATH", "../quantconnect-lean")).resolve()
    )
    data_path: Path = field(
        default_factory=lambda: Path(os.getenv("LEAN_DATA_PATH", "../quantconnect-lean/Data")).resolve()
    )
    results_path: Path = field(
        default_factory=lambda: Path(os.getenv("LEAN_RESULTS_PATH", "./results")).resolve()
    )
    algorithm_path: Path | None = field(default=None)
    
    def __post_init__(self):
        if self.algorithm_path is None:
            self.algorithm_path = self.lean_path / "Algorithm.Python"
        # Ensure results directory exists
        self.results_path.mkdir(parents=True, exist_ok=True)


@dataclass
class AlpacaConfig:
    """Alpaca brokerage configuration."""
    # Paper trading
    paper_key: str = field(default_factory=lambda: os.getenv("ALPACA_PAPER_KEY", ""))
    paper_secret: str = field(default_factory=lambda: os.getenv("ALPACA_PAPER_SECRET", ""))
    paper_url: str = field(
        default_factory=lambda: os.getenv("ALPACA_PAPER_URL", "https://paper-api.alpaca.markets")
    )
    
    # Live trading
    live_key: str = field(default_factory=lambda: os.getenv("ALPACA_LIVE_KEY", ""))
    live_secret: str = field(default_factory=lambda: os.getenv("ALPACA_LIVE_SECRET", ""))
    live_url: str = field(
        default_factory=lambda: os.getenv("ALPACA_LIVE_URL", "https://api.alpaca.markets")
    )
    
    @property
    def paper_configured(self) -> bool:
        """Check if paper trading is configured."""
        return bool(self.paper_key and self.paper_secret)
    
    @property
    def live_configured(self) -> bool:
        """Check if live trading is configured."""
        return bool(self.live_key and self.live_secret)


@dataclass
class SafetyConfig:
    """Safety and risk management settings."""
    live_deploy_enabled: bool = field(
        default_factory=lambda: os.getenv("LIVE_DEPLOY_ENABLED", "false").lower() == "true"
    )
    live_confirm_code: str = field(
        default_factory=lambda: os.getenv("LIVE_CONFIRM_CODE", "DEPLOY_LIVE_2026")
    )
    max_position_size: float = field(
        default_factory=lambda: float(os.getenv("MAX_POSITION_SIZE", "10000"))
    )
    daily_loss_limit: float = field(
        default_factory=lambda: float(os.getenv("DAILY_LOSS_LIMIT", "500"))
    )


@dataclass
class Config:
    """Master configuration container."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    lean: LeanConfig = field(default_factory=lambda: LeanConfig())
    alpaca: AlpacaConfig = field(default_factory=AlpacaConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)


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
