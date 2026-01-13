-- ================================================
-- LEAN-Ops MCP Database Schema
-- Additional tables for algorithm operations
-- ================================================

USE TradingDB;
GO

-- ================================================
-- AUDIT LOG TABLE FOR MCP OPERATIONS
-- Tracks all MCP operations for compliance/debugging
-- (Separate from core AuditLog to avoid schema conflicts)
-- ================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'MCPAuditLog') AND type in (N'U'))
BEGIN
    CREATE TABLE MCPAuditLog (
        AuditId INT IDENTITY(1,1) PRIMARY KEY,
        Operation NVARCHAR(100) NOT NULL,           -- RUN_BACKTEST, DEPLOY_PAPER, etc.
        SessionId NVARCHAR(100) NULL,               -- Related session if applicable
        Details NVARCHAR(MAX) NULL,                 -- JSON details
        Success BIT NOT NULL DEFAULT 1,
        ErrorMessage NVARCHAR(MAX) NULL,
        Timestamp DATETIME2 NOT NULL DEFAULT GETDATE(),
        
        -- Indexes
        INDEX IX_MCPAuditLog_Operation (Operation),
        INDEX IX_MCPAuditLog_SessionId (SessionId),
        INDEX IX_MCPAuditLog_Timestamp (Timestamp)
    );
    
    PRINT 'Created table: MCPAuditLog';
END
GO

-- ================================================
-- ALGORITHM PARAMETERS TABLE
-- Stores configurable parameters per algorithm
-- ================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'Parameters') AND type in (N'U'))
BEGIN
    CREATE TABLE Parameters (
        ParameterId INT IDENTITY(1,1) PRIMARY KEY,
        AlgorithmName NVARCHAR(100) NOT NULL,
        ParamName NVARCHAR(100) NOT NULL,
        ParamValue NVARCHAR(500) NOT NULL,
        ParamType NVARCHAR(50) NOT NULL DEFAULT 'string',  -- string, int, float, bool
        IsActive BIT NOT NULL DEFAULT 1,
        CreatedAt DATETIME2 NOT NULL DEFAULT GETDATE(),
        UpdatedAt DATETIME2 NULL,
        
        -- Constraints
        CONSTRAINT UQ_Parameters_AlgoParam UNIQUE (AlgorithmName, ParamName, IsActive),
        
        -- Indexes
        INDEX IX_Parameters_Algorithm (AlgorithmName),
        INDEX IX_Parameters_Active (IsActive)
    );
    
    PRINT 'Created table: Parameters';
END
GO

-- ================================================
-- INSERT DEFAULT PARAMETERS
-- ================================================

-- Clear existing defaults
DELETE FROM Parameters WHERE AlgorithmName = 'TQQQScalpingAlgorithm' AND IsActive = 1;

-- Insert TQQQ strategy defaults
INSERT INTO Parameters (AlgorithmName, ParamName, ParamValue, ParamType) VALUES
    -- RSI Parameters
    ('TQQQScalpingAlgorithm', 'rsi_period', '14', 'int'),
    ('TQQQScalpingAlgorithm', 'rsi_oversold', '30', 'float'),
    ('TQQQScalpingAlgorithm', 'rsi_overbought', '70', 'float'),
    
    -- Bollinger Bands
    ('TQQQScalpingAlgorithm', 'bb_period', '20', 'int'),
    ('TQQQScalpingAlgorithm', 'bb_std_dev', '2.0', 'float'),
    
    -- Risk Management
    ('TQQQScalpingAlgorithm', 'stop_loss_pct', '0.02', 'float'),
    ('TQQQScalpingAlgorithm', 'take_profit_pct', '0.015', 'float'),
    ('TQQQScalpingAlgorithm', 'trailing_stop_pct', '0.01', 'float'),
    
    -- Position Sizing (Pyramiding levels)
    ('TQQQScalpingAlgorithm', 'position_size_level1', '0.50', 'float'),
    ('TQQQScalpingAlgorithm', 'position_size_level2', '0.30', 'float'),
    ('TQQQScalpingAlgorithm', 'position_size_level3', '0.20', 'float'),
    ('TQQQScalpingAlgorithm', 'max_pyramid_levels', '3', 'int'),
    
    -- Trading Hours
    ('TQQQScalpingAlgorithm', 'trading_start_hour', '10', 'int'),
    ('TQQQScalpingAlgorithm', 'trading_end_hour', '15', 'int'),
    ('TQQQScalpingAlgorithm', 'eod_close_minute', '50', 'int'),
    
    -- Trend Filter
    ('TQQQScalpingAlgorithm', 'ema_fast_period', '9', 'int'),
    ('TQQQScalpingAlgorithm', 'ema_slow_period', '21', 'int'),
    
    -- Safety
    ('TQQQScalpingAlgorithm', 'max_daily_trades', '10', 'int'),
    ('TQQQScalpingAlgorithm', 'max_daily_loss_pct', '0.05', 'float');

PRINT 'Inserted default parameters for TQQQScalpingAlgorithm';
GO

-- ================================================
-- STORED PROCEDURES
-- ================================================

-- Get active parameters for algorithm
CREATE OR ALTER PROCEDURE sp_GetParameters
    @AlgorithmName NVARCHAR(100)
AS
BEGIN
    SELECT 
        ParamName,
        ParamValue,
        ParamType
    FROM Parameters
    WHERE AlgorithmName = @AlgorithmName
      AND IsActive = 1
    ORDER BY ParamName;
END
GO

-- Update a parameter
CREATE OR ALTER PROCEDURE sp_UpdateParameter
    @AlgorithmName NVARCHAR(100),
    @ParamName NVARCHAR(100),
    @ParamValue NVARCHAR(500),
    @ParamType NVARCHAR(50) = NULL
AS
BEGIN
    IF EXISTS (SELECT 1 FROM Parameters WHERE AlgorithmName = @AlgorithmName AND ParamName = @ParamName AND IsActive = 1)
    BEGIN
        UPDATE Parameters
        SET ParamValue = @ParamValue,
            ParamType = ISNULL(@ParamType, ParamType),
            UpdatedAt = GETDATE()
        WHERE AlgorithmName = @AlgorithmName
          AND ParamName = @ParamName
          AND IsActive = 1;
    END
    ELSE
    BEGIN
        INSERT INTO Parameters (AlgorithmName, ParamName, ParamValue, ParamType, IsActive)
        VALUES (@AlgorithmName, @ParamName, @ParamValue, ISNULL(@ParamType, 'string'), 1);
    END
END
GO

-- Get recent MCP audit log
CREATE OR ALTER PROCEDURE sp_GetMCPAuditLog
    @Operation NVARCHAR(100) = NULL,
    @Limit INT = 100
AS
BEGIN
    SELECT TOP (@Limit)
        AuditId,
        Operation,
        SessionId,
        Details,
        Success,
        ErrorMessage,
        Timestamp
    FROM MCPAuditLog
    WHERE (@Operation IS NULL OR Operation = @Operation)
    ORDER BY Timestamp DESC;
END
GO

-- Log an MCP operation
CREATE OR ALTER PROCEDURE sp_LogMCPOperation
    @Operation NVARCHAR(100),
    @SessionId NVARCHAR(100) = NULL,
    @Details NVARCHAR(MAX) = NULL,
    @Success BIT = 1,
    @ErrorMessage NVARCHAR(MAX) = NULL
AS
BEGIN
    INSERT INTO MCPAuditLog (Operation, SessionId, Details, Success, ErrorMessage)
    VALUES (@Operation, @SessionId, @Details, @Success, @ErrorMessage);
    
    SELECT SCOPE_IDENTITY() AS AuditId;
END
GO

PRINT 'LEAN-Ops MCP schema setup complete';
