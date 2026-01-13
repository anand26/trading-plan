"""
Configuration management for the Adaptive Agent.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


# Load environment variables
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    server: str = "localhost"
    database: str = "TradingDB"
    driver: str = "ODBC Driver 17 for SQL Server"
    username: Optional[str] = None
    password: Optional[str] = None
    
    @property
    def connection_string(self) -> str:
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
class ThresholdConfig:
    """Decision threshold configuration."""
    min_confidence_to_act: float = 0.7
    max_daily_parameter_changes: int = 5
    emergency_drawdown_pct: float = 0.15
    min_trades_for_analysis: int = 10
    pattern_match_threshold: float = 0.5


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_position_size_pct: float = 0.20
    max_daily_loss_pct: float = 0.05
    max_consecutive_losses: int = 5
    cooldown_after_losses_minutes: int = 30


@dataclass
class AlpacaConfig:
    """Alpaca API configuration."""
    api_key: str = ""
    secret_key: str = ""
    base_url: str = "https://paper-api.alpaca.markets"


@dataclass
class NotificationConfig:
    """Notification configuration."""
    enabled: bool = False
    on_parameter_change: bool = True
    on_emergency_stop: bool = True
    on_regime_change: bool = True
    slack_webhook_url: Optional[str] = None
    email_smtp_server: Optional[str] = None


@dataclass
class AgentConfig:
    """Main agent configuration."""
    mode: str = "paper"  # paper | live
    cycle_interval_seconds: int = 60
    learning_enabled: bool = True
    auto_apply_recommendations: bool = False
    dry_run: bool = False
    debug: bool = False
    log_level: str = "INFO"
    
    # Sub-configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    alpaca: AlpacaConfig = field(default_factory=AlpacaConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        return cls(
            mode=os.getenv("AGENT_MODE", "paper"),
            cycle_interval_seconds=int(os.getenv("CYCLE_INTERVAL_SECONDS", "60")),
            learning_enabled=os.getenv("LEARNING_ENABLED", "true").lower() == "true",
            auto_apply_recommendations=os.getenv("AUTO_APPLY_RECOMMENDATIONS", "false").lower() == "true",
            dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database=DatabaseConfig(
                server=os.getenv("DB_SERVER", "localhost"),
                database=os.getenv("DB_NAME", "TradingDB"),
                driver=os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server"),
                username=os.getenv("DB_USERNAME"),
                password=os.getenv("DB_PASSWORD"),
            ),
            thresholds=ThresholdConfig(
                min_confidence_to_act=float(os.getenv("MIN_CONFIDENCE_TO_ACT", "0.7")),
                max_daily_parameter_changes=int(os.getenv("MAX_DAILY_PARAMETER_CHANGES", "5")),
                emergency_drawdown_pct=float(os.getenv("EMERGENCY_DRAWDOWN_PCT", "0.15")),
            ),
            risk=RiskConfig(
                max_position_size_pct=float(os.getenv("MAX_POSITION_SIZE_PCT", "0.20")),
                max_daily_loss_pct=float(os.getenv("MAX_DAILY_LOSS_PCT", "0.05")),
            ),
            alpaca=AlpacaConfig(
                api_key=os.getenv("ALPACA_API_KEY", ""),
                secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
                base_url=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
            ),
            notifications=NotificationConfig(
                enabled=os.getenv("NOTIFICATIONS_ENABLED", "false").lower() == "true",
                slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
                email_smtp_server=os.getenv("EMAIL_SMTP_SERVER"),
            ),
        )


# Global config instance
_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = AgentConfig.from_env()
    return _config


def set_config(config: AgentConfig):
    """Set the global configuration instance."""
    global _config
    _config = config
