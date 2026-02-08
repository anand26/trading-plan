-- ============================================================================
-- BACKTEST MONITORING QUERIES
-- ============================================================================
-- Run this script to monitor latest backtest results comprehensively
-- Usage: Execute in SSMS or Azure Data Studio
-- ============================================================================

USE TradingDB;
GO

-- Variables for the latest backtest
DECLARE @backtestid VARCHAR(100);
DECLARE @outcomeid BIGINT;
DECLARE @strategyid VARCHAR(50);
		
-- Get latest backtest
SET @outcomeid = '12984'--(SELECT TOP 1 OutcomeId FROM BacktestOutcomes ORDER BY OutcomeId DESC);
SET @backtestid = 'POSTREND_20260207_184652_2d0df58a'--(SELECT TOP 1 BacktestId FROM BacktestOutcomes ORDER BY OutcomeId DESC);
SET @strategyid = 'POSITION_TREND'--(SELECT TOP 1 StrategyId FROM BacktestOutcomes ORDER BY OutcomeId DESC);
		
PRINT '============================================================================';
PRINT 'LATEST BACKTEST MONITORING REPORT';
PRINT '============================================================================';
PRINT 'BacktestId: ' + ISNULL(@backtestid, 'N/A');
PRINT 'OutcomeId: ' + CAST(ISNULL(@outcomeid, 0) AS VARCHAR(20));
PRINT 'StrategyId: ' + ISNULL(@strategyid, 'N/A');
PRINT '============================================================================';
PRINT '';

-- ============================================================================
-- 1. BACKTEST SUMMARY (BacktestOutcomes)
-- ============================================================================
PRINT '>>> 1. BACKTEST SUMMARY';
SELECT 
    'BacktestOutcomes' as TableName,
    BacktestId,
    StrategyId,
    StartDate,
    EndDate,
    TradingDays,
    CAST(TotalReturn * 100 AS DECIMAL(10,2)) AS ReturnPct,
    CAST(SharpeRatio AS DECIMAL(10,3)) AS Sharpe,
    CAST(SortinoRatio AS DECIMAL(10,3)) AS Sortino,
    CAST(MaxDrawdown * 100 AS DECIMAL(10,2)) AS MaxDDPct,
    TotalTrades,
    WinningTrades,
    LosingTrades,
    CAST(WinRate * 100 AS DECIMAL(10,2)) AS WinRatePct,
    CAST(ProfitFactor AS DECIMAL(10,2)) AS ProfitFactor,
    CAST(TotalProfit AS DECIMAL(18,2)) AS TotalProfit,
    CAST(TotalLoss AS DECIMAL(18,2)) AS TotalLoss,
    CAST(AverageWin AS DECIMAL(18,2)) AS AvgWin,
    CAST(AverageLoss AS DECIMAL(18,2)) AS AvgLoss,
    CAST(Expectancy AS DECIMAL(10,2)) AS Expectancy,
    PerformanceGrade,
    IsSuccessful,
    ExecutionTimeSeconds,
    CreatedAt
FROM BacktestOutcomes 
WHERE BacktestId = @backtestid;

-- ============================================================================
-- 2. SESSION INFO (Sessions)
-- ============================================================================
PRINT '';
PRINT '>>> 2. SESSION INFO';
SELECT 
    'Sessions' AS TableName,
    SessionId,
    SessionType,
    StrategyId,
    Status,
    StartTime,
    EndTime,
    CAST(TotalReturn * 100 AS DECIMAL(10,2)) AS ReturnPct,
    CAST(SharpeRatio AS DECIMAL(10,3)) AS Sharpe,
    CAST(MaxDrawdown * 100 AS DECIMAL(10,2)) AS MaxDDPct,
    TotalTrades,
    CAST(WinRate * 100 AS DECIMAL(10,2)) AS WinRatePct,
    AlgorithmVersion,
    Notes
FROM Sessions 
WHERE SessionId = @backtestid;

-- ============================================================================
-- 3. TOP 10 WINNING TRADES
-- ============================================================================
PRINT '';
PRINT '>>> 3. TOP 10 WINNING TRADES';
SELECT TOP 10
    'TopWins' AS Category,
    TradeId,
    Symbol,
    Direction,
    EntryTime,
    ExitTime,
    CAST(EntryPrice AS DECIMAL(18,4)) AS EntryPrice,
    CAST(ExitPrice AS DECIMAL(18,4)) AS ExitPrice,
    CAST(EntryQuantity AS DECIMAL(18,2)) AS Qty,
    CAST(GrossPnL AS DECIMAL(18,2)) AS GrossPnL,
    CAST(PnLPercent AS DECIMAL(10,2)) AS PnLPct,
    ExitReason,
    DurationMinutes
FROM Trades 
WHERE SessionId = @backtestid 
  AND GrossPnL > 0
ORDER BY GrossPnL DESC;

-- ============================================================================
-- 4. TOP 10 LOSING TRADES
-- ============================================================================
PRINT '';
PRINT '>>> 4. TOP 10 LOSING TRADES';
SELECT TOP 10
    'TopLosses' AS Category,
    TradeId,
    Symbol,
    Direction,
    EntryTime,
    ExitTime,
    CAST(EntryPrice AS DECIMAL(18,4)) AS EntryPrice,
    CAST(ExitPrice AS DECIMAL(18,4)) AS ExitPrice,
    CAST(EntryQuantity AS DECIMAL(18,2)) AS Qty,
    CAST(GrossPnL AS DECIMAL(18,2)) AS GrossPnL,
    CAST(PnLPercent AS DECIMAL(10,2)) AS PnLPct,
    ExitReason,
    DurationMinutes
FROM Trades 
WHERE SessionId = @backtestid 
  AND GrossPnL < 0
ORDER BY GrossPnL ASC;

-- ============================================================================
-- 5. TRADE SUMMARY BY SYMBOL
-- ============================================================================
PRINT '';
PRINT '>>> 5. TRADE SUMMARY BY SYMBOL';
SELECT 
    Symbol,
    COUNT(*) AS TotalTrades,
    SUM(CASE WHEN GrossPnL > 0 THEN 1 ELSE 0 END) AS Wins,
    SUM(CASE WHEN GrossPnL < 0 THEN 1 ELSE 0 END) AS Losses,
    CAST(SUM(CASE WHEN GrossPnL > 0 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*),0) * 100 AS DECIMAL(10,2)) AS WinRatePct,
    CAST(SUM(GrossPnL) AS DECIMAL(18,2)) AS TotalPnL,
    CAST(AVG(GrossPnL) AS DECIMAL(18,2)) AS AvgPnL,
    CAST(AVG(CASE WHEN GrossPnL > 0 THEN GrossPnL END) AS DECIMAL(18,2)) AS AvgWin,
    CAST(AVG(CASE WHEN GrossPnL < 0 THEN GrossPnL END) AS DECIMAL(18,2)) AS AvgLoss,
    CAST(MAX(GrossPnL) AS DECIMAL(18,2)) AS LargestWin,
    CAST(MIN(GrossPnL) AS DECIMAL(18,2)) AS LargestLoss,
    AVG(DurationMinutes) AS AvgHoldingMins
FROM Trades 
WHERE SessionId = @backtestid
GROUP BY Symbol;

-- ============================================================================
-- 6. TRADE SUMMARY BY EXIT REASON
-- ============================================================================
PRINT '';
PRINT '>>> 6. TRADE SUMMARY BY EXIT REASON';
SELECT 
    ExitReason,
    COUNT(*) AS TotalTrades,
    SUM(CASE WHEN GrossPnL > 0 THEN 1 ELSE 0 END) AS Wins,
    SUM(CASE WHEN GrossPnL < 0 THEN 1 ELSE 0 END) AS Losses,
    CAST(SUM(CASE WHEN GrossPnL > 0 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*),0) * 100 AS DECIMAL(10,2)) AS WinRatePct,
    CAST(SUM(GrossPnL) AS DECIMAL(18,2)) AS TotalPnL,
    CAST(AVG(GrossPnL) AS DECIMAL(18,2)) AS AvgPnL
FROM Trades 
WHERE SessionId = @backtestid
GROUP BY ExitReason
ORDER BY TotalPnL DESC;

-- ============================================================================
-- 7. TRADE SUMMARY BY DIRECTION
-- ============================================================================
PRINT '';
PRINT '>>> 7. TRADE SUMMARY BY DIRECTION';
SELECT 
    Direction,
    COUNT(*) AS TotalTrades,
    SUM(CASE WHEN GrossPnL > 0 THEN 1 ELSE 0 END) AS Wins,
    SUM(CASE WHEN GrossPnL < 0 THEN 1 ELSE 0 END) AS Losses,
    CAST(SUM(CASE WHEN GrossPnL > 0 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*),0) * 100 AS DECIMAL(10,2)) AS WinRatePct,
    CAST(SUM(GrossPnL) AS DECIMAL(18,2)) AS TotalPnL,
    CAST(AVG(GrossPnL) AS DECIMAL(18,2)) AS AvgPnL,
    CAST(SUM(CASE WHEN GrossPnL > 0 THEN GrossPnL ELSE 0 END) AS DECIMAL(18,2)) AS GrossProfit,
    CAST(SUM(CASE WHEN GrossPnL < 0 THEN ABS(GrossPnL) ELSE 0 END) AS DECIMAL(18,2)) AS GrossLoss
FROM Trades 
WHERE SessionId = @backtestid
GROUP BY Direction;

-- ============================================================================
-- 8. DAILY PERFORMANCE (sorted by P&L)
-- ============================================================================
PRINT '';
PRINT '>>> 8. DAILY PERFORMANCE (Best/Worst Days)';
SELECT TOP 20
    Date,
    CAST(DailyPnL AS DECIMAL(18,2)) AS DailyPnL,
    CAST(DailyPnLPercent AS DECIMAL(10,4)) AS DailyPnLPct,
    NumTrades,
    WinningTrades,
    LosingTrades,
    CAST(GrossProfit AS DECIMAL(18,2)) AS GrossProfit,
    CAST(GrossLoss AS DECIMAL(18,2)) AS GrossLoss,
    MarketRegime
FROM DailyPerformance 
WHERE SessionId = @backtestid
ORDER BY DailyPnL DESC;

-- ============================================================================
-- 9. TRADE DISTRIBUTION BY HOUR
-- ============================================================================
PRINT '';
PRINT '>>> 9. TRADE DISTRIBUTION BY HOUR';
SELECT 
    DATEPART(HOUR, EntryTime) AS EntryHour,
    COUNT(*) AS TotalTrades,
    SUM(CASE WHEN GrossPnL > 0 THEN 1 ELSE 0 END) AS Wins,
    SUM(CASE WHEN GrossPnL < 0 THEN 1 ELSE 0 END) AS Losses,
    CAST(SUM(CASE WHEN GrossPnL > 0 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*),0) * 100 AS DECIMAL(10,2)) AS WinRatePct,
    CAST(SUM(GrossPnL) AS DECIMAL(18,2)) AS TotalPnL,
    CAST(AVG(GrossPnL) AS DECIMAL(18,2)) AS AvgPnL
FROM Trades 
WHERE SessionId = @backtestid
GROUP BY DATEPART(HOUR, EntryTime)
ORDER BY EntryHour;

-- ============================================================================
-- 10. TRADE DISTRIBUTION BY DAY OF WEEK
-- ============================================================================
PRINT '';
PRINT '>>> 10. TRADE DISTRIBUTION BY DAY OF WEEK';
SELECT 
    DATENAME(WEEKDAY, EntryTime) AS DayOfWeek,
    DATEPART(WEEKDAY, EntryTime) AS DayNum,
    COUNT(*) AS TotalTrades,
    SUM(CASE WHEN GrossPnL > 0 THEN 1 ELSE 0 END) AS Wins,
    SUM(CASE WHEN GrossPnL < 0 THEN 1 ELSE 0 END) AS Losses,
    CAST(SUM(CASE WHEN GrossPnL > 0 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*),0) * 100 AS DECIMAL(10,2)) AS WinRatePct,
    CAST(SUM(GrossPnL) AS DECIMAL(18,2)) AS TotalPnL,
    CAST(AVG(GrossPnL) AS DECIMAL(18,2)) AS AvgPnL
FROM Trades 
WHERE SessionId = @backtestid
GROUP BY DATENAME(WEEKDAY, EntryTime), DATEPART(WEEKDAY, EntryTime)
ORDER BY DayNum;

-- ============================================================================
-- 11. ORDERS COUNT
-- ============================================================================
PRINT '';
PRINT '>>> 11. ORDERS SUMMARY';
SELECT 
    COUNT(*) AS TotalOrders,
    SUM(CASE WHEN Direction = 'buy' THEN 1 ELSE 0 END) AS BuyOrders,
    SUM(CASE WHEN Direction = 'sell' THEN 1 ELSE 0 END) AS SellOrders,
    SUM(CASE WHEN Status = 'filled' THEN 1 ELSE 0 END) AS FilledOrders,
    SUM(CASE WHEN Status = 'cancelled' THEN 1 ELSE 0 END) AS CancelledOrders
FROM Orders 
WHERE Tag LIKE '%' + @backtestid + '%';

-- ============================================================================
-- 12. MARKET REGIMES DURING BACKTEST
-- ============================================================================
PRINT '';
PRINT '>>> 12. MARKET REGIMES DURING BACKTEST';
SELECT 
    Regime,
    COUNT(*) AS DaysInRegime,
    MIN(Date) AS FirstDate,
    MAX(Date) AS LastDate,
    CAST(AVG(Confidence) AS DECIMAL(5,2)) AS AvgConfidence,
    CAST(AVG(VIX_Close) AS DECIMAL(10,2)) AS AvgVIX
FROM MarketRegimes
WHERE Date BETWEEN 
    (SELECT StartDate FROM BacktestOutcomes WHERE BacktestId = @backtestid) AND
    (SELECT EndDate FROM BacktestOutcomes WHERE BacktestId = @backtestid)
GROUP BY Regime
ORDER BY DaysInRegime DESC;

-- ============================================================================
-- 13. CONSECUTIVE WINS/LOSSES
-- ============================================================================
PRINT '';
PRINT '>>> 13. WIN/LOSS STREAKS';
WITH TradeSequence AS (
    SELECT 
        TradeId,
        GrossPnL,
        CASE WHEN GrossPnL > 0 THEN 'WIN' ELSE 'LOSS' END AS Outcome,
        ROW_NUMBER() OVER (ORDER BY ExitTime) - 
        ROW_NUMBER() OVER (PARTITION BY CASE WHEN GrossPnL > 0 THEN 1 ELSE 0 END ORDER BY ExitTime) AS Grp
    FROM Trades
    WHERE SessionId = @backtestid AND ExitTime IS NOT NULL
)
SELECT 
    Outcome,
    MAX(StreakLen) AS MaxConsecutive,
    AVG(StreakLen) AS AvgStreak
FROM (
    SELECT Outcome, Grp, COUNT(*) AS StreakLen
    FROM TradeSequence
    GROUP BY Outcome, Grp
) streaks
GROUP BY Outcome;

-- ============================================================================
-- 14. HOLDING TIME ANALYSIS
-- ============================================================================
PRINT '';
PRINT '>>> 14. HOLDING TIME ANALYSIS';
SELECT 
    CASE 
        WHEN DurationMinutes <= 5 THEN '0-5 min'
        WHEN DurationMinutes <= 15 THEN '5-15 min'
        WHEN DurationMinutes <= 30 THEN '15-30 min'
        WHEN DurationMinutes <= 60 THEN '30-60 min'
        WHEN DurationMinutes <= 120 THEN '1-2 hours'
        ELSE '2+ hours'
    END AS HoldingBucket,
    COUNT(*) AS Trades,
    CAST(SUM(CASE WHEN GrossPnL > 0 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*),0) * 100 AS DECIMAL(10,2)) AS WinRatePct,
    CAST(SUM(GrossPnL) AS DECIMAL(18,2)) AS TotalPnL,
    CAST(AVG(GrossPnL) AS DECIMAL(18,2)) AS AvgPnL
FROM Trades
WHERE SessionId = @backtestid AND DurationMinutes IS NOT NULL
GROUP BY 
    CASE 
        WHEN DurationMinutes <= 5 THEN '0-5 min'
        WHEN DurationMinutes <= 15 THEN '5-15 min'
        WHEN DurationMinutes <= 30 THEN '15-30 min'
        WHEN DurationMinutes <= 60 THEN '30-60 min'
        WHEN DurationMinutes <= 120 THEN '1-2 hours'
        ELSE '2+ hours'
    END
ORDER BY MIN(DurationMinutes);

-- ============================================================================
-- 15. RECENT BACKTEST COMPARISON (Last 10)
-- ============================================================================
PRINT '';
PRINT '>>> 15. RECENT BACKTEST COMPARISON (Last 10)';
SELECT TOP 10
    OutcomeId,
    BacktestId,
    StrategyId,
    StartDate,
    EndDate,
    CAST(TotalReturn * 100 AS DECIMAL(10,2)) AS ReturnPct,
    CAST(SharpeRatio AS DECIMAL(10,3)) AS Sharpe,
    CAST(MaxDrawdown * 100 AS DECIMAL(10,2)) AS MaxDDPct,
    TotalTrades,
    CAST(WinRate * 100 AS DECIMAL(10,2)) AS WinRatePct,
    CAST(ProfitFactor AS DECIMAL(10,2)) AS ProfitFactor,
    PerformanceGrade,
    IsSuccessful,
    CreatedAt
FROM BacktestOutcomes
ORDER BY OutcomeId DESC;

-- ============================================================================
-- 16. PARAMETERS USED (from JSON)
-- ============================================================================
PRINT '';
PRINT '>>> 16. PARAMETERS USED';
SELECT 
    BacktestId,
    ParametersJson
FROM BacktestOutcomes 
WHERE BacktestId = @backtestid;

-- ============================================================================
-- 17. EQUITY CURVE DATA (DailyPerformance cumulative)
-- ============================================================================
PRINT '';
PRINT '>>> 17. EQUITY CURVE (Cumulative P&L by Date)';
SELECT 
    Date,
    CAST(DailyPnL AS DECIMAL(18,2)) AS DailyPnL,
    CAST(SUM(DailyPnL) OVER (ORDER BY Date) AS DECIMAL(18,2)) AS CumulativePnL,
    NumTrades,
    MarketRegime
FROM DailyPerformance 
WHERE SessionId = @backtestid
ORDER BY Date;

-- ============================================================================
-- 18. WEBHOOK EVENTS (if any)
-- ============================================================================
PRINT '';
PRINT '>>> 18. WEBHOOK EVENTS';
SELECT TOP 20 * 
FROM WebhookEvents 
WHERE SessionId = @backtestid
ORDER BY EventId DESC;

PRINT '';
PRINT '============================================================================';
PRINT 'END OF BACKTEST MONITORING REPORT';
PRINT '============================================================================';
GO
