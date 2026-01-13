"""
Unit tests for configuration management.
"""

import os
import pytest
from unittest.mock import patch


class TestAgentConfig:
    """Tests for AgentConfig."""
    
    def test_default_config(self):
        """Should create config with defaults."""
        from adaptive_agent.config import AgentConfig
        
        config = AgentConfig()
        
        assert config.mode == "paper"
        assert config.dry_run == False
        assert config.thresholds.min_confidence_to_act == 0.7
    
    def test_config_from_env(self):
        """Should load config from environment."""
        from adaptive_agent.config import AgentConfig
        
        with patch.dict(os.environ, {
            "AGENT_MODE": "live",
            "DRY_RUN": "true",
            "MIN_CONFIDENCE_TO_ACT": "0.8",
        }):
            config = AgentConfig.from_env()
            
            assert config.mode == "live"
            assert config.dry_run == True
            assert config.thresholds.min_confidence_to_act == 0.8
    
    def test_database_connection_string(self):
        """Should generate correct connection string."""
        from adaptive_agent.config import DatabaseConfig
        
        db_config = DatabaseConfig(
            server="testserver",
            database="TestDB",
            driver="ODBC Driver 17 for SQL Server",
        )
        
        conn_str = db_config.connection_string
        
        assert "testserver" in conn_str
        assert "TestDB" in conn_str
        assert "Trusted_Connection=yes" in conn_str
    
    def test_database_connection_string_with_credentials(self):
        """Should generate connection string with credentials."""
        from adaptive_agent.config import DatabaseConfig
        
        db_config = DatabaseConfig(
            server="testserver",
            database="TestDB",
            username="testuser",
            password="testpass",
        )
        
        conn_str = db_config.connection_string
        
        assert "UID=testuser" in conn_str
        assert "PWD=testpass" in conn_str
        assert "Trusted_Connection" not in conn_str


class TestThresholdConfig:
    """Tests for ThresholdConfig."""
    
    def test_default_thresholds(self):
        """Should have sensible defaults."""
        from adaptive_agent.config import ThresholdConfig
        
        thresholds = ThresholdConfig()
        
        assert 0 < thresholds.min_confidence_to_act <= 1
        assert thresholds.max_daily_parameter_changes > 0
        assert 0 < thresholds.emergency_drawdown_pct < 1


class TestRiskConfig:
    """Tests for RiskConfig."""
    
    def test_default_risk_settings(self):
        """Should have sensible risk defaults."""
        from adaptive_agent.config import RiskConfig
        
        risk = RiskConfig()
        
        assert 0 < risk.max_position_size_pct <= 1
        assert 0 < risk.max_daily_loss_pct <= 1
        assert risk.max_consecutive_losses > 0


class TestGlobalConfig:
    """Tests for global config functions."""
    
    def test_get_config_singleton(self):
        """Should return same config instance."""
        from adaptive_agent.config import get_config, set_config, AgentConfig
        
        # Reset global
        set_config(None)
        
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2
    
    def test_set_config(self):
        """Should allow setting custom config."""
        from adaptive_agent.config import get_config, set_config, AgentConfig
        
        custom = AgentConfig(mode="live", dry_run=True)
        set_config(custom)
        
        config = get_config()
        
        assert config.mode == "live"
        assert config.dry_run == True
        
        # Reset
        set_config(None)
