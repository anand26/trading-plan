-- ============================================
-- TQQQ/SQQQ Trading System - Stored Procedures
-- ============================================
-- Common queries for MCP servers and analytics
-- Execute with: sqlcmd -S localhost -E -d TradingDB -i 05_stored_procedures.sql
-- ============================================

USE TradingDB;
GO

-- ============================================
-- 1. GET LAST TRADES (Trade-Mind MCP Tool)
-- ============================================
CREATE OR ALTER PROCEDURE sp_GetLastTrades
    @Symbol VARCHAR(10) = NULL,
    @Count INT = 10,
    @SessionId VARCHAR(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT TOP (@Count)
        t.TradeId,
        t.SessionId,
        t.Symbol,
        t.Direction,
        t.EntryQuantity AS Quantity,
        t.EntryPrice,
        t.ExitPrice,
        t.NetPnL,
        t.PnLPercent,
        t.EntryTime,
        t.ExitTime,
        t.DurationMinutes,
        t.ExitReason,
        t.NumEntries,
        t.Commission
    FROM Trades t
    WHERE (@Symbol IS NULL OR t.Symbol = @Symbol)
      AND (@SessionId IS NULL OR t.SessionId = @SessionId)
    ORDER BY t.ExitTime DESC;
END;
GO

-- ============================================
-- 2. CALCULATE WIN RATE (Trade-Mind MCP Tool)
-- ============================================
CREATE OR ALTER PROCEDURE sp_CalculateWinRate
    @Symbol VARCHAR(10) = NULL,
    @SessionId VARCHAR(50) = NULL,
    @StartDate DATE = NULL,
    @EndDate DATE = NULL,
    @MinTrades INT = 5
AS
BEGIN
    SET NOCOUNT ON;
    
    WITH TradeStats AS (
        SELECT 
            Symbol,
            COUNT(*) AS TotalTrades,
            SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) AS WinningTrades,
            SUM(CASE WHEN NetPnL < 0 THEN 1 ELSE 0 END) AS LosingTrades,
            SUM(CASE WHEN NetPnL = 0 THEN 1 ELSE 0 END) AS BreakEvenTrades,
            SUM(NetPnL) AS TotalPnL,
            AVG(NetPnL) AS AvgPnL,
            AVG(CASE WHEN NetPnL > 0 THEN NetPnL END) AS AvgWin,
            AVG(CASE WHEN NetPnL < 0 THEN NetPnL END) AS AvgLoss,
            MAX(NetPnL) AS MaxWin,
            MIN(NetPnL) AS MaxLoss,
            AVG(DurationMinutes) AS AvgDurationMinutes
        FROM Trades
        WHERE (@Symbol IS NULL OR Symbol = @Symbol)
          AND (@SessionId IS NULL OR SessionId = @SessionId)
          AND (@StartDate IS NULL OR CAST(ExitTime AS DATE) >= @StartDate)
          AND (@EndDate IS NULL OR CAST(ExitTime AS DATE) <= @EndDate)
        GROUP BY Symbol
    )
    SELECT 
        Symbol,
        TotalTrades,
        WinningTrades,
        LosingTrades,
        BreakEvenTrades,
        CASE 
            WHEN TotalTrades > 0 
            THEN CAST(WinningTrades AS DECIMAL(10,4)) / TotalTrades 
            ELSE 0 
        END AS WinRate,
        TotalPnL,
        AvgPnL,
        AvgWin,
        AvgLoss,
        CASE 
            WHEN ABS(AvgLoss) > 0 
            THEN ABS(AvgWin / AvgLoss) 
            ELSE NULL 
        END AS ProfitFactor,
        MaxWin,
        MaxLoss,
        AvgDurationMinutes,
        CASE 
            WHEN TotalTrades >= @MinTrades 
            THEN 'STATISTICALLY_VALID'
            ELSE 'INSUFFICIENT_DATA'
        END AS DataQuality
    FROM TradeStats
    WHERE TotalTrades > 0
    ORDER BY TotalPnL DESC;
END;
GO

-- ============================================
-- 3. RECORD TRADE
-- ============================================
CREATE OR ALTER PROCEDURE sp_RecordTrade
    @SessionId VARCHAR(50),
    @Symbol VARCHAR(10),
    @Direction VARCHAR(10),
    @EntryQuantity DECIMAL(18,8),
    @EntryPrice DECIMAL(18,4),
    @ExitPrice DECIMAL(18,4),
    @EntryTime DATETIME2,
    @ExitTime DATETIME2,
    @ExitReason VARCHAR(50) = NULL,
    @Commission DECIMAL(18,4) = 0,
    @NumEntries INT = 1
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @GrossPnL DECIMAL(18,4);
    DECLARE @NetPnL DECIMAL(18,4);
    DECLARE @PnLPercent DECIMAL(10,4);
    DECLARE @DurationMinutes INT;
    
    -- Calculate PnL
    SET @GrossPnL = CASE 
        WHEN @Direction = 'LONG' THEN (@ExitPrice - @EntryPrice) * @EntryQuantity
        ELSE (@EntryPrice - @ExitPrice) * @EntryQuantity
    END;
    
    SET @NetPnL = @GrossPnL - @Commission;
    SET @PnLPercent = @NetPnL / (@EntryPrice * @EntryQuantity) * 100;
    SET @DurationMinutes = DATEDIFF(MINUTE, @EntryTime, @ExitTime);
    
    INSERT INTO Trades (
        Symbol, Direction, EntryTime, EntryPrice, EntryQuantity,
        ExitTime, ExitPrice, ExitQuantity, ExitReason,
        GrossPnL, Commission, NetPnL, PnLPercent,
        NumEntries, DurationMinutes, SessionId
    )
    VALUES (
        @Symbol, @Direction, @EntryTime, @EntryPrice, @EntryQuantity,
        @ExitTime, @ExitPrice, @EntryQuantity, @ExitReason,
        @GrossPnL, @Commission, @NetPnL, @PnLPercent,
        @NumEntries, @DurationMinutes, @SessionId
    );
    
    SELECT SCOPE_IDENTITY() AS TradeId, @NetPnL AS NetPnL;
END;
GO

-- ============================================
-- 4. GET PARAMETER VALUE
-- ============================================
CREATE OR ALTER PROCEDURE sp_GetParameter
    @ParamName VARCHAR(50),
    @StrategyId VARCHAR(50) = 'TQQQ_SCALPING'
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        ParamName,
        ParamValue,
        ParamType,
        Description,
        Category,
        MinValue,
        MaxValue,
        DefaultValue
    FROM StrategyParameters
    WHERE ParamName = @ParamName
      AND StrategyId = @StrategyId
      AND IsActive = 1;
END;
GO

-- ============================================
-- 5. UPDATE PARAMETER
-- ============================================
CREATE OR ALTER PROCEDURE sp_UpdateStrategyParameter
    @ParamName VARCHAR(50),
    @NewValue VARCHAR(100),
    @ChangedBy VARCHAR(50) = 'USER',
    @ChangeReason NVARCHAR(500) = NULL,
    @StrategyId VARCHAR(50) = 'TQQQ_SCALPING'
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @ParamId BIGINT;
    DECLARE @OldValue VARCHAR(100);
    
    -- Get current value
    SELECT @ParamId = ParamId, @OldValue = ParamValue
    FROM StrategyParameters
    WHERE ParamName = @ParamName
      AND StrategyId = @StrategyId;
    
    IF @ParamId IS NULL
    BEGIN
        RAISERROR('Parameter not found: %s', 16, 1, @ParamName);
        RETURN;
    END
    
    -- Update parameter
    UPDATE StrategyParameters
    SET ParamValue = @NewValue,
        LastUpdated = GETUTCDATE(),
        UpdatedBy = @ChangedBy
    WHERE ParamId = @ParamId;
    
    -- Record history
    INSERT INTO ParameterHistory (ParamId, OldValue, NewValue, ChangeReason, ChangedBy)
    VALUES (@ParamId, @OldValue, @NewValue, @ChangeReason, @ChangedBy);
    
    SELECT 'SUCCESS' AS Result, @ParamName AS ParamName, @OldValue AS OldValue, @NewValue AS NewValue;
END;
GO

-- ============================================
-- 6. GET ALL PARAMETERS (For Algorithm Init)
-- ============================================
CREATE OR ALTER PROCEDURE sp_GetAllParameters
    @StrategyId VARCHAR(50) = 'TQQQ_SCALPING'
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        ParamName,
        ParamValue,
        ParamType,
        Category
    FROM StrategyParameters
    WHERE StrategyId = @StrategyId
      AND IsActive = 1
    ORDER BY Category, ParamName;
END;
GO

-- ============================================
-- 7. GET SESSION INFO
-- ============================================
CREATE OR ALTER PROCEDURE sp_GetSessionInfo
    @SessionId VARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        SessionId,
        SessionType,
        StrategyId,
        StartTime,
        EndTime,
        Status,
        TotalReturn,
        SharpeRatio,
        MaxDrawdown,
        TotalTrades,
        WinRate,
        AlgorithmVersion,
        Notes
    FROM Sessions
    WHERE SessionId = @SessionId;
END;
GO

-- ============================================
-- 8. CREATE SESSION
-- ============================================
CREATE OR ALTER PROCEDURE sp_CreateSession
    @SessionId VARCHAR(50),
    @SessionType VARCHAR(20),
    @StrategyId VARCHAR(50) = 'TQQQ_SCALPING',
    @ParametersJson NVARCHAR(MAX) = NULL,
    @AlgorithmVersion VARCHAR(20) = NULL,
    @Notes NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    INSERT INTO Sessions (
        SessionId, SessionType, StrategyId, StartTime, 
        ParametersJson, Status, AlgorithmVersion, Notes
    )
    VALUES (
        @SessionId, @SessionType, @StrategyId, GETUTCDATE(),
        @ParametersJson, 'RUNNING', @AlgorithmVersion, @Notes
    );
    
    SELECT @SessionId AS SessionId, 'CREATED' AS Status;
END;
GO

-- ============================================
-- 9. UPDATE SESSION STATUS
-- ============================================
CREATE OR ALTER PROCEDURE sp_UpdateSessionStatus
    @SessionId VARCHAR(50),
    @Status VARCHAR(20),
    @TotalReturn DECIMAL(10,4) = NULL,
    @SharpeRatio DECIMAL(10,4) = NULL,
    @MaxDrawdown DECIMAL(10,4) = NULL,
    @TotalTrades INT = NULL,
    @WinRate DECIMAL(10,4) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE Sessions
    SET Status = @Status,
        EndTime = CASE WHEN @Status IN ('COMPLETED', 'FAILED', 'STOPPED') THEN GETUTCDATE() ELSE EndTime END,
        TotalReturn = COALESCE(@TotalReturn, TotalReturn),
        SharpeRatio = COALESCE(@SharpeRatio, SharpeRatio),
        MaxDrawdown = COALESCE(@MaxDrawdown, MaxDrawdown),
        TotalTrades = COALESCE(@TotalTrades, TotalTrades),
        WinRate = COALESCE(@WinRate, WinRate)
    WHERE SessionId = @SessionId;
    
    SELECT @SessionId AS SessionId, @Status AS Status;
END;
GO

-- ============================================
-- 10. GET BACKTEST OUTCOMES
-- ============================================
CREATE OR ALTER PROCEDURE sp_GetBacktestOutcomes
    @StrategyId VARCHAR(50) = NULL,
    @MinSharpe DECIMAL(10,4) = NULL,
    @TopN INT = 20
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT TOP (@TopN)
        OutcomeId,
        BacktestId,
        StrategyId,
        StartDate,
        EndDate,
        TotalReturn,
        SharpeRatio,
        SortinoRatio,
        MaxDrawdown,
        TotalTrades,
        WinRate,
        ProfitFactor,
        Expectancy,
        PerformanceGrade,
        IsSuccessful,
        CreatedAt
    FROM BacktestOutcomes
    WHERE (@StrategyId IS NULL OR StrategyId = @StrategyId)
      AND (@MinSharpe IS NULL OR SharpeRatio >= @MinSharpe)
    ORDER BY SharpeRatio DESC, WinRate DESC;
END;
GO

-- ============================================
-- 11. GET PARAMETER PERFORMANCE
-- ============================================
CREATE OR ALTER PROCEDURE sp_GetParameterPerformance
    @ParamName VARCHAR(50) = NULL,
    @MarketRegime VARCHAR(20) = NULL,
    @MinSampleCount INT = 5
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        ParamPerfId,
        StrategyId,
        ParamName,
        ParamValue,
        MarketRegime,
        SampleCount,
        AvgSharpeRatio,
        AvgWinRate,
        AvgReturn,
        AvgMaxDrawdown,
        BestSharpe AS BestSharpeRatio,
        WorstSharpe AS WorstSharpeRatio,
        ConfidenceScore AS Confidence,
        LastUpdated
    FROM ParameterPerformance
    WHERE (@ParamName IS NULL OR ParamName = @ParamName)
      AND (@MarketRegime IS NULL OR MarketRegime = @MarketRegime)
      AND SampleCount >= @MinSampleCount
    ORDER BY AvgSharpeRatio DESC;
END;
GO

-- ============================================
-- 12. RECORD BACKTEST OUTCOME
-- ============================================
CREATE OR ALTER PROCEDURE sp_RecordBacktestOutcome
    @BacktestId VARCHAR(50),
    @StrategyId VARCHAR(50),
    @StartDate DATE,
    @EndDate DATE,
    @ParametersJson NVARCHAR(MAX),
    @TotalReturn DECIMAL(10,4),
    @SharpeRatio DECIMAL(10,4),
    @SortinoRatio DECIMAL(10,4) = NULL,
    @MaxDrawdown DECIMAL(10,4),
    @TotalTrades INT,
    @WinRate DECIMAL(10,4),
    @ProfitFactor DECIMAL(10,4) = NULL,
    @Expectancy DECIMAL(10,4) = NULL,
    @ExecutionTimeSeconds INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Determine grade based on Sharpe ratio
    DECLARE @Grade CHAR(2);
    SET @Grade = CASE 
        WHEN @SharpeRatio >= 2.0 THEN 'A'
        WHEN @SharpeRatio >= 1.5 THEN 'B+'
        WHEN @SharpeRatio >= 1.0 THEN 'B'
        WHEN @SharpeRatio >= 0.5 THEN 'C+'
        WHEN @SharpeRatio >= 0 THEN 'C'
        ELSE 'D'
    END;
    
    DECLARE @IsSuccessful BIT;
    SET @IsSuccessful = CASE WHEN @SharpeRatio >= 1.0 AND @WinRate >= 0.4 AND @MaxDrawdown <= 0.20 THEN 1 ELSE 0 END;
    
    INSERT INTO BacktestOutcomes (
        BacktestId, StrategyId, StartDate, EndDate, ParametersJson,
        TotalReturn, SharpeRatio, SortinoRatio, MaxDrawdown,
        TotalTrades, WinRate, ProfitFactor, Expectancy,
        PerformanceGrade, IsSuccessful, ExecutionTimeSeconds
    )
    VALUES (
        @BacktestId, @StrategyId, @StartDate, @EndDate, @ParametersJson,
        @TotalReturn, @SharpeRatio, @SortinoRatio, @MaxDrawdown,
        @TotalTrades, @WinRate, @ProfitFactor, @Expectancy,
        @Grade, @IsSuccessful, @ExecutionTimeSeconds
    );
    
    SELECT SCOPE_IDENTITY() AS OutcomeId, @Grade AS PerformanceGrade;
END;
GO

PRINT 'All stored procedures created successfully.';
GO
