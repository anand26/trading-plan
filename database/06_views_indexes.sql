-- ============================================
-- TQQQ/SQQQ Trading System - Views and Indexes
-- ============================================
-- Optimized views and indexes for analytics
-- Execute with: sqlcmd -S localhost -E -d TradingDB -i 06_views_indexes.sql
-- ============================================

USE TradingDB;
GO

-- ============================================
-- PERFORMANCE INDEXES
-- ============================================

-- Trades table indexes for common queries
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Trades_SessionSymbol' AND object_id = OBJECT_ID('Trades'))
    CREATE NONCLUSTERED INDEX IX_Trades_SessionSymbol 
    ON Trades (SessionId, Symbol) 
    INCLUDE (Direction, NetPnL, EntryTime, ExitTime);
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Trades_ExitTimeSymbol' AND object_id = OBJECT_ID('Trades'))
    CREATE NONCLUSTERED INDEX IX_Trades_ExitTimeSymbol 
    ON Trades (ExitTime DESC, Symbol) 
    INCLUDE (NetPnL, PnLPercent, ExitReason);
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Trades_PnLAnalysis' AND object_id = OBJECT_ID('Trades'))
    CREATE NONCLUSTERED INDEX IX_Trades_PnLAnalysis 
    ON Trades (Symbol, NetPnL) 
    INCLUDE (Direction, EntryQuantity, EntryPrice, ExitPrice, DurationMinutes);
GO

-- Orders table indexes
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Orders_StatusTime' AND object_id = OBJECT_ID('Orders'))
    CREATE NONCLUSTERED INDEX IX_Orders_StatusTime 
    ON Orders (Status, SubmittedAt DESC) 
    INCLUDE (Symbol, Direction, Quantity, FillPrice);
GO

-- Learning tables indexes
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_BacktestOutcomes_Performance' AND object_id = OBJECT_ID('BacktestOutcomes'))
    CREATE NONCLUSTERED INDEX IX_BacktestOutcomes_Performance 
    ON BacktestOutcomes (SharpeRatio DESC, WinRate DESC) 
    INCLUDE (TotalReturn, MaxDrawdown, TotalTrades);
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_ParamPerf_Analysis' AND object_id = OBJECT_ID('ParameterPerformance'))
    CREATE NONCLUSTERED INDEX IX_ParamPerf_Analysis 
    ON ParameterPerformance (ParamName, ParamValue) 
    INCLUDE (SampleCount, AvgWinRate, AvgSharpeRatio);
GO

-- Sessions table indexes
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Sessions_Status' AND object_id = OBJECT_ID('Sessions'))
    CREATE NONCLUSTERED INDEX IX_Sessions_Status 
    ON Sessions (Status, StartTime DESC) 
    INCLUDE (SessionType, StrategyId, TotalReturn, SharpeRatio);
GO

PRINT 'Indexes created successfully.';
GO

-- ============================================
-- VIEW: v_RecentTrades
-- ============================================
-- Quick view of recent trades with key metrics
CREATE OR ALTER VIEW v_RecentTrades
AS
SELECT 
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
    t.MAE,
    t.MFE,
    CASE 
        WHEN t.NetPnL > 0 THEN 'WIN'
        WHEN t.NetPnL < 0 THEN 'LOSS'
        ELSE 'BREAKEVEN'
    END AS Outcome
FROM Trades t;
GO

-- ============================================
-- VIEW: v_SymbolPerformance
-- ============================================
-- Performance by symbol
CREATE OR ALTER VIEW v_SymbolPerformance
AS
SELECT 
    Symbol,
    COUNT(*) AS TotalTrades,
    SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) AS Wins,
    SUM(CASE WHEN NetPnL < 0 THEN 1 ELSE 0 END) AS Losses,
    CAST(SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) AS DECIMAL(10,4)) / 
        NULLIF(COUNT(*), 0) * 100 AS WinRatePercent,
    SUM(NetPnL) AS TotalPnL,
    AVG(NetPnL) AS AvgPnL,
    AVG(CASE WHEN NetPnL > 0 THEN NetPnL END) AS AvgWin,
    AVG(CASE WHEN NetPnL < 0 THEN NetPnL END) AS AvgLoss,
    MAX(NetPnL) AS LargestWin,
    MIN(NetPnL) AS LargestLoss,
    AVG(DurationMinutes) AS AvgHoldingMinutes,
    MIN(EntryTime) AS FirstTrade,
    MAX(ExitTime) AS LastTrade
FROM Trades
GROUP BY Symbol;
GO

-- ============================================
-- VIEW: v_SessionSummary
-- ============================================
-- Session overview with performance
CREATE OR ALTER VIEW v_SessionSummary
AS
SELECT 
    s.SessionId,
    s.SessionType,
    s.StrategyId,
    s.StartTime,
    s.EndTime,
    s.Status,
    s.TotalReturn * 100 AS ReturnPercent,
    s.SharpeRatio,
    s.MaxDrawdown * 100 AS MaxDrawdownPercent,
    s.TotalTrades,
    s.WinRate * 100 AS WinRatePercent,
    s.AlgorithmVersion,
    DATEDIFF(MINUTE, s.StartTime, COALESCE(s.EndTime, GETUTCDATE())) AS DurationMinutes
FROM Sessions s;
GO

-- ============================================
-- VIEW: v_ActiveSession
-- ============================================
-- Current active trading session
CREATE OR ALTER VIEW v_ActiveSession
AS
SELECT 
    SessionId,
    SessionType,
    StrategyId,
    StartTime,
    Status,
    TotalTrades,
    WinRate * 100 AS WinRatePercent,
    TotalReturn * 100 AS ReturnPercent,
    MaxDrawdown * 100 AS MaxDrawdownPercent,
    SharpeRatio,
    AlgorithmVersion,
    Notes
FROM Sessions
WHERE Status = 'RUNNING';
GO

-- ============================================
-- VIEW: v_BacktestComparison
-- ============================================
-- Compare backtest results
CREATE OR ALTER VIEW v_BacktestComparison
AS
SELECT 
    OutcomeId,
    BacktestId,
    StrategyId,
    StartDate,
    EndDate,
    DATEDIFF(DAY, StartDate, EndDate) AS DurationDays,
    TotalReturn * 100 AS ReturnPercent,
    SharpeRatio,
    SortinoRatio,
    MaxDrawdown * 100 AS MaxDrawdownPercent,
    TotalTrades,
    WinRate * 100 AS WinRatePercent,
    ProfitFactor,
    Expectancy,
    PerformanceGrade,
    IsSuccessful,
    CreatedAt
FROM BacktestOutcomes;
GO

-- ============================================
-- VIEW: v_ParameterEffectiveness
-- ============================================
-- Track which parameters work best
CREATE OR ALTER VIEW v_ParameterEffectiveness
AS
SELECT 
    pp.ParamPerfId,
    pp.StrategyId,
    pp.ParamName,
    pp.ParamValue,
    pp.MarketRegime,
    pp.SampleCount,
    pp.AvgWinRate * 100 AS WinRatePercent,
    pp.AvgSharpeRatio,
    pp.AvgReturn * 100 AS AvgReturnPercent,
    pp.AvgMaxDrawdown * 100 AS AvgMaxDrawdownPercent,
    pp.ConfidenceScore AS ConfidencePercent,
    sp.ParamValue AS CurrentValue,
    CASE 
        WHEN pp.ParamValue = sp.ParamValue THEN 'CURRENT'
        ELSE 'ALTERNATIVE'
    END AS Status
FROM ParameterPerformance pp
LEFT JOIN StrategyParameters sp 
    ON pp.ParamName = sp.ParamName 
    AND pp.StrategyId = sp.StrategyId
    AND sp.IsActive = 1;
GO

-- ============================================
-- VIEW: v_DailyTradeStats
-- ============================================
-- Daily trading statistics computed from trades
CREATE OR ALTER VIEW v_DailyTradeStats
AS
SELECT 
    CAST(ExitTime AS DATE) AS TradingDate,
    SessionId,
    COUNT(*) AS TradeCount,
    SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) AS WinCount,
    SUM(CASE WHEN NetPnL < 0 THEN 1 ELSE 0 END) AS LossCount,
    CAST(SUM(CASE WHEN NetPnL > 0 THEN 1 ELSE 0 END) AS DECIMAL(10,4)) / 
        NULLIF(COUNT(*), 0) * 100 AS WinRatePercent,
    SUM(NetPnL) AS DailyPnL,
    AVG(NetPnL) AS AvgPnL,
    MAX(NetPnL) AS BestTrade,
    MIN(NetPnL) AS WorstTrade,
    SUM(Commission) AS TotalCommission,
    AVG(DurationMinutes) AS AvgDurationMinutes
FROM Trades
WHERE ExitTime IS NOT NULL
GROUP BY CAST(ExitTime AS DATE), SessionId;
GO

-- ============================================
-- VIEW: v_OrderBook
-- ============================================
-- Recent orders view
CREATE OR ALTER VIEW v_OrderBook
AS
SELECT 
    OrderId,
    ExternalOrderId,
    Symbol,
    Direction,
    OrderType,
    Quantity,
    FilledQuantity,
    Price AS LimitPrice,
    FillPrice,
    Status,
    TimeInForce,
    SubmittedAt,
    FilledAt,
    Commission,
    Tag
FROM Orders;
GO

-- ============================================
-- VIEW: v_StrategyConfig
-- ============================================
-- Current strategy configuration
CREATE OR ALTER VIEW v_StrategyConfig
AS
SELECT 
    StrategyId,
    Category,
    ParamName,
    ParamValue,
    ParamType,
    Description,
    MinValue,
    MaxValue,
    DefaultValue,
    LastUpdated,
    UpdatedBy
FROM StrategyParameters
WHERE IsActive = 1;
GO

PRINT 'All views created successfully.';
GO
