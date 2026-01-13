-- ================================================
-- Trade-Mind MCP Database Schema
-- Tables for analytics and adaptive learning
-- ================================================

USE TradingDB;
GO

-- ================================================
-- LEARNING STORE TABLE
-- Stores patterns and insights discovered by the system
-- ================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'LearningStore') AND type in (N'U'))
BEGIN
    CREATE TABLE LearningStore (
        LearningId INT IDENTITY(1,1) PRIMARY KEY,
        PatternType NVARCHAR(50) NOT NULL,          -- ENTRY_SIGNAL, EXIT_SIGNAL, REGIME_PATTERN, etc.
        Description NVARCHAR(500) NOT NULL,          -- Human-readable description
        PatternData NVARCHAR(MAX) NULL,              -- JSON structured data
        Confidence FLOAT NOT NULL DEFAULT 0.5,       -- 0.0 to 1.0
        UsageCount INT NOT NULL DEFAULT 0,           -- How many times this learning was applied
        SuccessRate FLOAT NULL,                      -- Success rate when applied
        CreatedAt DATETIME2 NOT NULL DEFAULT GETDATE(),
        LastUsedAt DATETIME2 NULL,
        IsActive BIT NOT NULL DEFAULT 1,
        
        -- Indexes
        INDEX IX_LearningStore_Type (PatternType),
        INDEX IX_LearningStore_Confidence (Confidence),
        INDEX IX_LearningStore_Active (IsActive)
    );
    
    PRINT 'Created table: LearningStore';
END
GO

-- ================================================
-- OPTIMAL PARAMETER VALUES TABLE
-- Best individual parameter values discovered for each regime
-- (Separate from OptimalParameters in 03_learning_schema which stores JSON)
-- ================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'OptimalParameterValues') AND type in (N'U'))
BEGIN
    CREATE TABLE OptimalParameterValues (
        OptimalId INT IDENTITY(1,1) PRIMARY KEY,
        StrategyId NVARCHAR(100) NOT NULL,           -- TQQQ_SCALPING
        ParamName NVARCHAR(100) NOT NULL,
        MarketRegime NVARCHAR(50) NOT NULL,
        OptimalValue NVARCHAR(100) NOT NULL,
        ConfidenceScore FLOAT NOT NULL DEFAULT 0.5,
        SampleSize INT NOT NULL DEFAULT 0,
        ExpectedSharpe FLOAT NULL,
        ExpectedReturn FLOAT NULL,
        ExpectedDrawdown FLOAT NULL,
        LastCalculated DATETIME2 NOT NULL DEFAULT GETDATE(),
        
        -- Constraints
        CONSTRAINT UQ_OptimalValues_StrategyParamRegime UNIQUE (StrategyId, ParamName, MarketRegime),
        
        -- Indexes
        INDEX IX_OptimalValues_Strategy (StrategyId),
        INDEX IX_OptimalValues_Regime (MarketRegime),
        INDEX IX_OptimalValues_Confidence (ConfidenceScore DESC)
    );
    
    PRINT 'Created table: OptimalParameterValues';
END
GO

-- ================================================
-- INSERT DEFAULT OPTIMAL PARAMETER VALUES
-- ================================================

-- Clear existing defaults (if any)
DELETE FROM OptimalParameterValues WHERE StrategyId = 'TQQQ_SCALPING';

-- Insert baseline optimal parameter values (will be updated by learning)
INSERT INTO OptimalParameterValues (StrategyId, ParamName, MarketRegime, OptimalValue, ConfidenceScore, SampleSize) VALUES
    -- Trending Up regime
    ('TQQQ_SCALPING', 'rsi_oversold', 'TRENDING_UP', '28', 0.7, 50),
    ('TQQQ_SCALPING', 'stop_loss_pct', 'TRENDING_UP', '0.02', 0.7, 50),
    ('TQQQ_SCALPING', 'take_profit_pct', 'TRENDING_UP', '0.02', 0.7, 50),
    
    -- Trending Down regime
    ('TQQQ_SCALPING', 'rsi_overbought', 'TRENDING_DOWN', '72', 0.7, 50),
    ('TQQQ_SCALPING', 'stop_loss_pct', 'TRENDING_DOWN', '0.015', 0.65, 40),
    ('TQQQ_SCALPING', 'take_profit_pct', 'TRENDING_DOWN', '0.012', 0.65, 40),
    
    -- Ranging regime (MEAN_REVERTING)
    ('TQQQ_SCALPING', 'rsi_oversold', 'MEAN_REVERTING', '32', 0.6, 30),
    ('TQQQ_SCALPING', 'rsi_overbought', 'MEAN_REVERTING', '68', 0.6, 30),
    ('TQQQ_SCALPING', 'take_profit_pct', 'MEAN_REVERTING', '0.01', 0.6, 30),
    
    -- High Volatility regime (VOLATILE)
    ('TQQQ_SCALPING', 'stop_loss_pct', 'VOLATILE', '0.025', 0.75, 60),
    ('TQQQ_SCALPING', 'position_size_level1', 'VOLATILE', '0.35', 0.75, 60),
    
    -- All regimes (defaults)
    ('TQQQ_SCALPING', 'rsi_oversold', 'ALL', '30', 0.5, 100),
    ('TQQQ_SCALPING', 'rsi_overbought', 'ALL', '70', 0.5, 100),
    ('TQQQ_SCALPING', 'stop_loss_pct', 'ALL', '0.02', 0.5, 100),
    ('TQQQ_SCALPING', 'take_profit_pct', 'ALL', '0.015', 0.5, 100);

PRINT 'Inserted default optimal parameters';
GO

-- ================================================
-- STORED PROCEDURES FOR TRADE-MIND MCP
-- ================================================

-- Get last N trades (uses correct column names from 02_core_schema.sql)
CREATE OR ALTER PROCEDURE sp_TM_GetLastTrades
    @Symbol NVARCHAR(10) = NULL,
    @Count INT = 20,
    @SessionId NVARCHAR(100) = NULL
AS
BEGIN
    SELECT TOP (@Count)
        TradeId, SessionId, Symbol, Direction,
        EntryQuantity AS Quantity,
        EntryPrice, ExitPrice, NetPnL, PnLPercent,
        EntryTime, ExitTime, ExitReason,
        DurationMinutes
    FROM Trades
    WHERE (@Symbol IS NULL OR Symbol = @Symbol)
      AND (@SessionId IS NULL OR SessionId = @SessionId)
      AND ExitTime IS NOT NULL
    ORDER BY ExitTime DESC;
END
GO

-- Calculate win rate statistics (uses correct column names)
CREATE OR ALTER PROCEDURE sp_TM_CalculateWinRate
    @Symbol NVARCHAR(10) = NULL,
    @SessionId NVARCHAR(100) = NULL,
    @DaysBack INT = NULL
AS
BEGIN
    SELECT 
        COUNT(*) as TotalTrades,
        SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) as WinningTrades,
        SUM(CASE WHEN NetPnL < 0 THEN 1 ELSE 0 END) as LosingTrades,
        SUM(CASE WHEN NetPnL = 0 THEN 1 ELSE 0 END) as BreakEvenTrades,
        SUM(NetPnL) as TotalPnL,
        AVG(NetPnL) as AvgPnL,
        AVG(CASE WHEN NetPnL > 0 THEN NetPnL END) as AvgWin,
        AVG(CASE WHEN NetPnL < 0 THEN NetPnL END) as AvgLoss,
        MAX(NetPnL) as MaxWin,
        MIN(NetPnL) as MaxLoss,
        AVG(DurationMinutes) as AvgDurationMinutes,
        CASE WHEN COUNT(*) >= 5 THEN 'STATISTICALLY_VALID' ELSE 'INSUFFICIENT_DATA' END as DataQuality
    FROM Trades
    WHERE ExitTime IS NOT NULL
      AND (@Symbol IS NULL OR Symbol = @Symbol)
      AND (@SessionId IS NULL OR SessionId = @SessionId)
      AND (@DaysBack IS NULL OR ExitTime >= DATEADD(day, -@DaysBack, GETDATE()));
END
GO

-- Get daily P&L (computed from Trades table since DailyPerformance doesn't exist)
CREATE OR ALTER PROCEDURE sp_TM_GetDailyPnL
    @DaysBack INT = 30,
    @SessionId NVARCHAR(100) = NULL
AS
BEGIN
    SELECT 
        CAST(ExitTime AS DATE) AS TradingDate,
        SessionId,
        COUNT(*) AS TradeCount,
        SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) AS WinCount,
        SUM(CASE WHEN NetPnL < 0 THEN 1 ELSE 0 END) AS LossCount,
        SUM(NetPnL) AS DailyPnL,
        AVG(NetPnL) AS AvgPnL,
        MAX(NetPnL) AS BestTrade,
        MIN(NetPnL) AS WorstTrade
    FROM Trades
    WHERE ExitTime IS NOT NULL
      AND ExitTime >= DATEADD(day, -@DaysBack, GETDATE())
      AND (@SessionId IS NULL OR SessionId = @SessionId)
    GROUP BY CAST(ExitTime AS DATE), SessionId
    ORDER BY TradingDate DESC;
END
GO

-- Suggest corrections based on optimal parameter values
CREATE OR ALTER PROCEDURE sp_TM_SuggestCorrections
    @MinConfidence FLOAT = 0.6,
    @MinSampleSize INT = 20
AS
BEGIN
    SELECT 
        op.ParamName,
        op.OptimalValue AS SuggestedValue,
        op.MarketRegime,
        op.ConfidenceScore,
        op.SampleSize,
        op.ExpectedSharpe,
        op.ExpectedReturn,
        op.ExpectedDrawdown,
        CASE 
            WHEN op.ConfidenceScore >= 0.8 THEN 'HIGH_CONFIDENCE'
            WHEN op.ConfidenceScore >= 0.6 THEN 'MEDIUM_CONFIDENCE'
            ELSE 'LOW_CONFIDENCE'
        END AS RecommendationStrength
    FROM OptimalParameterValues op
    WHERE op.ConfidenceScore >= @MinConfidence
      AND op.SampleSize >= @MinSampleSize
    ORDER BY op.ConfidenceScore DESC, op.ParamName;
END
GO

-- Detect current market regime (uses correct MarketRegimes schema from 03_learning_schema.sql)
CREATE OR ALTER PROCEDURE sp_TM_DetectMarketRegime
AS
BEGIN
    SELECT TOP 1
        RegimeId,
        Date,
        Regime AS RegimeType,
        Confidence,
        TrendStrength,
        TrendDuration,
        VIX_Close,
        QQQ_ATR AS Volatility
    FROM MarketRegimes
    ORDER BY Date DESC;
END
GO

-- Get parameter performance (uses ParameterPerformance from 03_learning_schema.sql)
CREATE OR ALTER PROCEDURE sp_TM_GetParameterPerformance
    @ParamName NVARCHAR(100),
    @MarketRegime NVARCHAR(50) = NULL
AS
BEGIN
    SELECT 
        ParamPerfId,
        StrategyId,
        ParamName,
        ParamValue,
        MarketRegime,
        SampleCount,
        AvgWinRate AS WinRate,
        AvgSharpeRatio AS SharpeRatio,
        AvgMaxDrawdown AS MaxDrawdown,
        AvgReturn,
        LastUpdated
    FROM ParameterPerformance
    WHERE ParamName = @ParamName
      AND (@MarketRegime IS NULL OR MarketRegime = @MarketRegime OR MarketRegime = 'ALL')
    ORDER BY AvgWinRate DESC, AvgSharpeRatio DESC;
END
GO

-- Record a learning
CREATE OR ALTER PROCEDURE sp_TM_RecordLearning
    @PatternType NVARCHAR(50),
    @Description NVARCHAR(500),
    @PatternData NVARCHAR(MAX),
    @Confidence FLOAT = 0.5
AS
BEGIN
    INSERT INTO LearningStore (PatternType, Description, PatternData, Confidence)
    VALUES (@PatternType, @Description, @PatternData, @Confidence);
    
    SELECT SCOPE_IDENTITY() AS LearningId;
END
GO

-- Get learnings
CREATE OR ALTER PROCEDURE sp_TM_GetLearnings
    @PatternType NVARCHAR(50) = NULL,
    @MinConfidence FLOAT = 0.0,
    @Limit INT = 50
AS
BEGIN
    SELECT TOP (@Limit)
        LearningId, PatternType, Description,
        PatternData, Confidence, UsageCount,
        SuccessRate, CreatedAt, LastUsedAt
    FROM LearningStore
    WHERE IsActive = 1
      AND Confidence >= @MinConfidence
      AND (@PatternType IS NULL OR PatternType = @PatternType)
    ORDER BY CreatedAt DESC;
END
GO

-- Update learning usage
CREATE OR ALTER PROCEDURE sp_TM_UpdateLearningUsage
    @LearningId INT,
    @WasSuccessful BIT
AS
BEGIN
    UPDATE LearningStore
    SET UsageCount = UsageCount + 1,
        LastUsedAt = GETDATE(),
        SuccessRate = CASE 
            WHEN UsageCount = 0 THEN CAST(@WasSuccessful AS FLOAT)
            ELSE (SuccessRate * UsageCount + CAST(@WasSuccessful AS FLOAT)) / (UsageCount + 1)
        END
    WHERE LearningId = @LearningId;
END
GO

-- Update optimal parameter value
CREATE OR ALTER PROCEDURE sp_TM_UpdateOptimalParameter
    @StrategyId NVARCHAR(100),
    @ParamName NVARCHAR(100),
    @MarketRegime NVARCHAR(50),
    @OptimalValue NVARCHAR(100),
    @ConfidenceScore FLOAT,
    @SampleSize INT,
    @ExpectedSharpe FLOAT = NULL,
    @ExpectedReturn FLOAT = NULL,
    @ExpectedDrawdown FLOAT = NULL
AS
BEGIN
    IF EXISTS (SELECT 1 FROM OptimalParameterValues WHERE StrategyId = @StrategyId AND ParamName = @ParamName AND MarketRegime = @MarketRegime)
    BEGIN
        UPDATE OptimalParameterValues
        SET OptimalValue = @OptimalValue,
            ConfidenceScore = @ConfidenceScore,
            SampleSize = @SampleSize,
            ExpectedSharpe = ISNULL(@ExpectedSharpe, ExpectedSharpe),
            ExpectedReturn = ISNULL(@ExpectedReturn, ExpectedReturn),
            ExpectedDrawdown = ISNULL(@ExpectedDrawdown, ExpectedDrawdown),
            LastCalculated = GETDATE()
        WHERE StrategyId = @StrategyId 
          AND ParamName = @ParamName 
          AND MarketRegime = @MarketRegime;
    END
    ELSE
    BEGIN
        INSERT INTO OptimalParameterValues (StrategyId, ParamName, MarketRegime, OptimalValue, ConfidenceScore, SampleSize, ExpectedSharpe, ExpectedReturn, ExpectedDrawdown)
        VALUES (@StrategyId, @ParamName, @MarketRegime, @OptimalValue, @ConfidenceScore, @SampleSize, @ExpectedSharpe, @ExpectedReturn, @ExpectedDrawdown);
    END
END
GO

PRINT 'Trade-Mind MCP schema setup complete';
GO
