-- ============================================
-- MISSING BACKTEST TABLES
-- ============================================
-- Creates BacktestRuns and BacktestMetrics tables that were referenced 
-- but not defined in the schema
-- ============================================

USE TradingDB;
GO

-- ============================================
-- BACKTEST RUNS TABLE
-- ============================================
-- Stores metadata about each backtest execution
CREATE TABLE BacktestRuns (
    RunID               VARCHAR(50) PRIMARY KEY,        -- BT_20260123_142030_abc123
    StartTime           DATETIME2 NOT NULL,             -- When backtest execution started
    EndTime             DATETIME2,                      -- When backtest completed
    Status              VARCHAR(20) NOT NULL,           -- Completed, Running, Failed
    AlgorithmName       VARCHAR(100) NOT NULL,          -- TQQQScalpingAlgorithm
    BacktestStartDate   DATE NOT NULL,                  -- Data period start (2024-01-01)
    BacktestEndDate     DATE NOT NULL,                  -- Data period end (2026-01-01)
    InitialCapital      DECIMAL(18, 4) NOT NULL,        -- Starting capital
    ParametersJson      NVARCHAR(MAX),                  -- Full parameter configuration as JSON
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    INDEX IX_BacktestRuns_StartTime (StartTime DESC),
    INDEX IX_BacktestRuns_Status (Status),
    INDEX IX_BacktestRuns_Algorithm (AlgorithmName)
);
GO

-- ============================================
-- BACKTEST METRICS TABLE
-- ============================================
-- Stores individual performance metrics for each backtest run
CREATE TABLE BacktestMetrics (
    MetricId            BIGINT IDENTITY(1,1) PRIMARY KEY,
    RunID               VARCHAR(50) NOT NULL,           -- Foreign key to BacktestRuns
    MetricName          VARCHAR(50) NOT NULL,           -- TotalReturn, SharpeRatio, etc.
    MetricValue         DECIMAL(18, 4) NOT NULL,        -- Numeric value
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    FOREIGN KEY (RunID) REFERENCES BacktestRuns(RunID) ON DELETE CASCADE,
    INDEX IX_BacktestMetrics_RunID (RunID),
    INDEX IX_BacktestMetrics_Name (MetricName),
    UNIQUE (RunID, MetricName)                          -- Prevent duplicate metrics per run
);
GO

PRINT 'Created missing BacktestRuns and BacktestMetrics tables';
GO