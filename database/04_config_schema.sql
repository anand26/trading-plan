-- ============================================
-- TQQQ/SQQQ Trading System - Configuration Schema
-- ============================================
-- Strategy parameters and configuration tables
-- Execute with: sqlcmd -S localhost -E -d TradingDB -i 04_config_schema.sql
-- ============================================

USE TradingDB;
GO

-- ============================================
-- 1. STRATEGY PARAMETERS TABLE
-- ============================================
-- Hot-reloadable parameters for the algorithm
CREATE TABLE StrategyParameters (
    ParamId             BIGINT IDENTITY(1,1) PRIMARY KEY,
    StrategyId          VARCHAR(50) NOT NULL DEFAULT 'TQQQ_SCALPING',
    
    ParamName           VARCHAR(50) NOT NULL,
    ParamValue          VARCHAR(100) NOT NULL,
    ParamType           VARCHAR(20) NOT NULL,           -- INT, FLOAT, STRING, BOOL
    
    -- Metadata
    Description         NVARCHAR(500),
    Category            VARCHAR(50),                    -- RSI, BB, RISK, POSITION, etc.
    
    -- Constraints
    MinValue            VARCHAR(50),
    MaxValue            VARCHAR(50),
    DefaultValue        VARCHAR(100),
    
    -- Audit
    IsActive            BIT DEFAULT 1,
    LastUpdated         DATETIME2 DEFAULT GETUTCDATE(),
    UpdatedBy           VARCHAR(50),
    
    INDEX IX_StrategyParams_Name (ParamName),
    INDEX IX_StrategyParams_Category (Category),
    
    CONSTRAINT UQ_StrategyParams_Name 
        UNIQUE (StrategyId, ParamName)
);
GO

-- ============================================
-- 2. PARAMETER HISTORY TABLE
-- ============================================
-- Track all parameter changes
CREATE TABLE ParameterHistory (
    HistoryId           BIGINT IDENTITY(1,1) PRIMARY KEY,
    ParamId             BIGINT NOT NULL,
    
    OldValue            VARCHAR(100),
    NewValue            VARCHAR(100) NOT NULL,
    
    ChangeReason        NVARCHAR(500),
    ChangedBy           VARCHAR(50),                    -- USER, AGENT, SYSTEM
    
    ChangedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_ParamHistory_Params 
        FOREIGN KEY (ParamId) REFERENCES StrategyParameters(ParamId),
    
    INDEX IX_ParamHistory_ParamId (ParamId),
    INDEX IX_ParamHistory_ChangedAt (ChangedAt DESC)
);
GO

-- ============================================
-- 3. SESSIONS TABLE
-- ============================================
-- Track backtest and live trading sessions
CREATE TABLE Sessions (
    SessionId           VARCHAR(50) PRIMARY KEY,
    
    SessionType         VARCHAR(20) NOT NULL,           -- BACKTEST, PAPER, LIVE
    StrategyId          VARCHAR(50) NOT NULL,
    
    -- Time range
    StartTime           DATETIME2 NOT NULL,
    EndTime             DATETIME2,
    
    -- Configuration snapshot
    ParametersJson      NVARCHAR(MAX),
    ConfigJson          NVARCHAR(MAX),
    
    -- Status
    Status              VARCHAR(20) NOT NULL,           -- RUNNING, COMPLETED, FAILED, STOPPED
    
    -- Results summary
    TotalReturn         DECIMAL(10, 4),
    SharpeRatio         DECIMAL(10, 4),
    MaxDrawdown         DECIMAL(10, 4),
    TotalTrades         INT,
    WinRate             DECIMAL(10, 4),
    
    -- Metadata
    AlgorithmVersion    VARCHAR(20),
    LeanVersion         VARCHAR(20),
    Notes               NVARCHAR(MAX),
    
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    INDEX IX_Sessions_SessionType (SessionType),
    INDEX IX_Sessions_Status (Status),
    INDEX IX_Sessions_StartTime (StartTime DESC)
);
GO

-- ============================================
-- 4. SYSTEM CONFIG TABLE
-- ============================================
-- Global system configuration
CREATE TABLE SystemConfig (
    ConfigId            BIGINT IDENTITY(1,1) PRIMARY KEY,
    ConfigKey           VARCHAR(100) NOT NULL UNIQUE,
    ConfigValue         NVARCHAR(MAX) NOT NULL,
    ConfigType          VARCHAR(20) NOT NULL,           -- STRING, INT, FLOAT, BOOL, JSON
    
    Description         NVARCHAR(500),
    IsEncrypted         BIT DEFAULT 0,
    
    LastUpdated         DATETIME2 DEFAULT GETUTCDATE(),
    UpdatedBy           VARCHAR(50)
);
GO

-- ============================================
-- INSERT DEFAULT STRATEGY PARAMETERS
-- ============================================

-- RSI Parameters
INSERT INTO StrategyParameters (ParamName, ParamValue, ParamType, Description, Category, MinValue, MaxValue, DefaultValue)
VALUES 
    ('rsi_period', '14', 'INT', 'RSI calculation period', 'RSI', '5', '30', '14'),
    ('rsi_oversold', '30', 'FLOAT', 'RSI oversold threshold for entry', 'RSI', '15', '40', '30'),
    ('rsi_overbought', '70', 'FLOAT', 'RSI overbought threshold for exit', 'RSI', '60', '85', '70'),
    ('rsi_extreme_oversold', '20', 'FLOAT', 'RSI extreme oversold for Level 3 entry', 'RSI', '10', '30', '20'),
    ('rsi_extreme_overbought', '80', 'FLOAT', 'RSI extreme overbought', 'RSI', '70', '90', '80');

-- Bollinger Bands Parameters
INSERT INTO StrategyParameters (ParamName, ParamValue, ParamType, Description, Category, MinValue, MaxValue, DefaultValue)
VALUES 
    ('bb_period', '20', 'INT', 'Bollinger Bands period', 'BB', '10', '50', '20'),
    ('bb_std_dev', '2.0', 'FLOAT', 'Bollinger Bands standard deviation', 'BB', '1.0', '3.0', '2.0');

-- EMA Parameters (QQQ Trend Filter)
INSERT INTO StrategyParameters (ParamName, ParamValue, ParamType, Description, Category, MinValue, MaxValue, DefaultValue)
VALUES 
    ('ema_fast_period', '9', 'INT', 'Fast EMA period for QQQ trend', 'EMA', '5', '20', '9'),
    ('ema_slow_period', '21', 'INT', 'Slow EMA period for QQQ trend', 'EMA', '15', '50', '21');

-- Risk Management Parameters
INSERT INTO StrategyParameters (ParamName, ParamValue, ParamType, Description, Category, MinValue, MaxValue, DefaultValue)
VALUES 
    ('stop_loss_pct', '0.02', 'FLOAT', 'Stop loss percentage', 'RISK', '0.005', '0.05', '0.02'),
    ('take_profit_rsi', '0.01', 'FLOAT', 'Take profit threshold above VWAP', 'RISK', '0.005', '0.03', '0.01'),
    ('max_daily_trades', '10', 'INT', 'Maximum trades per day', 'RISK', '1', '50', '10'),
    ('max_daily_loss_pct', '0.05', 'FLOAT', 'Maximum daily loss before stopping', 'RISK', '0.01', '0.10', '0.05');

-- Position Sizing Parameters
INSERT INTO StrategyParameters (ParamName, ParamValue, ParamType, Description, Category, MinValue, MaxValue, DefaultValue)
VALUES 
    ('position_size_level1', '0.50', 'FLOAT', 'Level 1 entry position size (50%)', 'POSITION', '0.20', '0.80', '0.50'),
    ('position_size_level2', '0.30', 'FLOAT', 'Level 2 entry position size (30%)', 'POSITION', '0.10', '0.50', '0.30'),
    ('position_size_level3', '0.20', 'FLOAT', 'Level 3 entry position size (20%)', 'POSITION', '0.05', '0.30', '0.20'),
    ('pyramid_level2_profit', '0.003', 'FLOAT', 'Profit threshold for Level 2 entry', 'POSITION', '0.001', '0.01', '0.003');

-- Volume Filter Parameters
INSERT INTO StrategyParameters (ParamName, ParamValue, ParamType, Description, Category, MinValue, MaxValue, DefaultValue)
VALUES 
    ('volume_spike_mult', '1.5', 'FLOAT', 'Volume spike multiplier threshold', 'VOLUME', '1.0', '3.0', '1.5'),
    ('volume_lookback', '20', 'INT', 'Volume average lookback period', 'VOLUME', '10', '50', '20');

-- Trading Hours Parameters
INSERT INTO StrategyParameters (ParamName, ParamValue, ParamType, Description, Category, DefaultValue)
VALUES 
    ('trading_start_time', '09:35', 'STRING', 'Trading window start time (EST)', 'HOURS', '09:35'),
    ('trading_end_time', '15:45', 'STRING', 'Trading window end time (EST)', 'HOURS', '15:45'),
    ('eod_close_time', '15:50', 'STRING', 'End of day position close time (EST)', 'HOURS', '15:50');

GO

-- ============================================
-- INSERT DEFAULT SYSTEM CONFIG
-- ============================================

INSERT INTO SystemConfig (ConfigKey, ConfigValue, ConfigType, Description)
VALUES 
    ('default_strategy_id', 'TQQQ_SCALPING', 'STRING', 'Default strategy identifier'),
    ('sql_log_level', 'INFO', 'STRING', 'Logging level for SQL operations'),
    ('enable_bar_storage', 'false', 'BOOL', 'Store 5-min bars in database'),
    ('enable_signal_storage', 'true', 'BOOL', 'Store all signals for analysis'),
    ('snapshot_interval_minutes', '15', 'INT', 'Account snapshot interval'),
    ('mcp_server_enabled', 'true', 'BOOL', 'Enable MCP server integration'),
    ('learning_enabled', 'true', 'BOOL', 'Enable adaptive learning features'),
    ('auto_correction_enabled', 'false', 'BOOL', 'Enable automatic parameter corrections');

GO

PRINT 'Configuration schema and default parameters created successfully.';
GO
