-- ============================================================================
-- BACKTEST MONITORING QUERIES
-- ============================================================================
-- Run this script to monitor latest backtest results comprehensively
-- Usage: Execute in SSMS or Azure Data Studio
-- ============================================================================

USE TradingDB;
GO

-- Variables for backtest comparison (set both to compare, or just @backtestid for single)
DECLARE @backtestid VARCHAR(100);
DECLARE @outcomeid BIGINT;
DECLARE @strategyid VARCHAR(50);

-- Backtest A (Databento data)
DECLARE @outcomeid_a BIGINT = 13266;
DECLARE @backtestid_a VARCHAR(100) = 'POSTREND_20260209_114147_2a63546f';

-- Backtest B (Alpha Vantage data)
DECLARE @outcomeid_b BIGINT = 13269;
DECLARE @backtestid_b VARCHAR(100) = 'POSTREND_20260209_214904_8a35fde5';

-- Default to Backtest B for single-backtest sections
SET @outcomeid = @outcomeid_b;
SET @backtestid = @backtestid_b;
SET @strategyid = 'POSITION_TREND';
		
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
PRINT '>>> 19. HEAD-TO-HEAD COMPARISON: Databento vs Alpha Vantage';
PRINT '============================================================================';

-- 19a. Summary side-by-side
SELECT 
    a.BacktestId AS [Backtest_A (Databento)],
    b.BacktestId AS [Backtest_B (AlphaVantage)],
    a.StartDate AS A_Start, b.StartDate AS B_Start,
    a.EndDate AS A_End, b.EndDate AS B_End,
    a.TradingDays AS A_Days, b.TradingDays AS B_Days,
    CAST(a.TotalReturn * 100 AS DECIMAL(10,2)) AS A_ReturnPct,
    CAST(b.TotalReturn * 100 AS DECIMAL(10,2)) AS B_ReturnPct,
    CAST((b.TotalReturn - a.TotalReturn) * 100 AS DECIMAL(10,2)) AS Delta_ReturnPct,
    CAST(a.SharpeRatio AS DECIMAL(10,3)) AS A_Sharpe,
    CAST(b.SharpeRatio AS DECIMAL(10,3)) AS B_Sharpe,
    CAST(a.SortinoRatio AS DECIMAL(10,3)) AS A_Sortino,
    CAST(b.SortinoRatio AS DECIMAL(10,3)) AS B_Sortino,
    CAST(a.MaxDrawdown * 100 AS DECIMAL(10,2)) AS A_MaxDDPct,
    CAST(b.MaxDrawdown * 100 AS DECIMAL(10,2)) AS B_MaxDDPct,
    a.TotalTrades AS A_Trades, b.TotalTrades AS B_Trades,
    a.WinningTrades AS A_Wins, b.WinningTrades AS B_Wins,
    CAST(a.WinRate * 100 AS DECIMAL(10,2)) AS A_WinRatePct,
    CAST(b.WinRate * 100 AS DECIMAL(10,2)) AS B_WinRatePct,
    CAST(a.ProfitFactor AS DECIMAL(10,2)) AS A_ProfitFactor,
    CAST(b.ProfitFactor AS DECIMAL(10,2)) AS B_ProfitFactor,
    CAST(a.TotalProfit AS DECIMAL(18,2)) AS A_TotalProfit,
    CAST(b.TotalProfit AS DECIMAL(18,2)) AS B_TotalProfit,
    CAST(a.TotalLoss AS DECIMAL(18,2)) AS A_TotalLoss,
    CAST(b.TotalLoss AS DECIMAL(18,2)) AS B_TotalLoss,
    a.PerformanceGrade AS A_Grade, b.PerformanceGrade AS B_Grade
FROM BacktestOutcomes a
CROSS JOIN BacktestOutcomes b
WHERE a.OutcomeId = @outcomeid_a AND b.OutcomeId = @outcomeid_b;

-- 19b. Trade count by symbol comparison
PRINT '';
PRINT '>>> 19b. TRADES BY SYMBOL COMPARISON';
SELECT 
    COALESCE(a.Symbol, b.Symbol) AS Symbol,
    ISNULL(a.A_Trades, 0) AS A_Trades,
    ISNULL(b.B_Trades, 0) AS B_Trades,
    ISNULL(a.A_Trades, 0) - ISNULL(b.B_Trades, 0) AS Delta_Trades,
    ISNULL(a.A_PnL, 0) AS A_PnL,
    ISNULL(b.B_PnL, 0) AS B_PnL,
    CAST(ISNULL(b.B_PnL, 0) - ISNULL(a.A_PnL, 0) AS DECIMAL(18,2)) AS Delta_PnL,
    ISNULL(a.A_WinRate, 0) AS A_WinRatePct,
    ISNULL(b.B_WinRate, 0) AS B_WinRatePct
FROM (
    SELECT Symbol,
        COUNT(*) AS A_Trades,
        CAST(SUM(GrossPnL) AS DECIMAL(18,2)) AS A_PnL,
        CAST(SUM(CASE WHEN GrossPnL > 0 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*),0) * 100 AS DECIMAL(10,2)) AS A_WinRate
    FROM Trades WHERE SessionId = @backtestid_a GROUP BY Symbol
) a
FULL OUTER JOIN (
    SELECT Symbol,
        COUNT(*) AS B_Trades,
        CAST(SUM(GrossPnL) AS DECIMAL(18,2)) AS B_PnL,
        CAST(SUM(CASE WHEN GrossPnL > 0 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*),0) * 100 AS DECIMAL(10,2)) AS B_WinRate
    FROM Trades WHERE SessionId = @backtestid_b GROUP BY Symbol
) b ON a.Symbol = b.Symbol;

-- 19c. Trade count by exit reason comparison
PRINT '';
PRINT '>>> 19c. EXIT REASON COMPARISON';
SELECT 
    COALESCE(a.ExitReason, b.ExitReason) AS ExitReason,
    ISNULL(a.A_Trades, 0) AS A_Trades,
    ISNULL(b.B_Trades, 0) AS B_Trades,
    CAST(ISNULL(a.A_PnL, 0) AS DECIMAL(18,2)) AS A_PnL,
    CAST(ISNULL(b.B_PnL, 0) AS DECIMAL(18,2)) AS B_PnL
FROM (
    SELECT ExitReason, COUNT(*) AS A_Trades, SUM(GrossPnL) AS A_PnL
    FROM Trades WHERE SessionId = @backtestid_a GROUP BY ExitReason
) a
FULL OUTER JOIN (
    SELECT ExitReason, COUNT(*) AS B_Trades, SUM(GrossPnL) AS B_PnL
    FROM Trades WHERE SessionId = @backtestid_b GROUP BY ExitReason
) b ON a.ExitReason = b.ExitReason
ORDER BY ISNULL(a.A_Trades, 0) + ISNULL(b.B_Trades, 0) DESC;

-- 19d. Monthly P&L comparison
PRINT '';
PRINT '>>> 19d. MONTHLY P&L COMPARISON';
SELECT 
    COALESCE(a.Month, b.Month) AS YearMonth,
    ISNULL(a.A_PnL, 0) AS A_MonthlyPnL,
    ISNULL(b.B_PnL, 0) AS B_MonthlyPnL,
    CAST(ISNULL(b.B_PnL, 0) - ISNULL(a.A_PnL, 0) AS DECIMAL(18,2)) AS Delta_PnL,
    ISNULL(a.A_Trades, 0) AS A_Trades,
    ISNULL(b.B_Trades, 0) AS B_Trades
FROM (
    SELECT FORMAT(Date, 'yyyy-MM') AS Month,
        CAST(SUM(DailyPnL) AS DECIMAL(18,2)) AS A_PnL,
        SUM(NumTrades) AS A_Trades
    FROM DailyPerformance WHERE SessionId = @backtestid_a GROUP BY FORMAT(Date, 'yyyy-MM')
) a
FULL OUTER JOIN (
    SELECT FORMAT(Date, 'yyyy-MM') AS Month,
        CAST(SUM(DailyPnL) AS DECIMAL(18,2)) AS B_PnL,
        SUM(NumTrades) AS B_Trades
    FROM DailyPerformance WHERE SessionId = @backtestid_b GROUP BY FORMAT(Date, 'yyyy-MM')
) b ON a.Month = b.Month
ORDER BY COALESCE(a.Month, b.Month);

-- 19e. Parameters comparison
PRINT '';
PRINT '>>> 19e. PARAMETERS COMPARISON';
SELECT 
    a.BacktestId AS [Backtest_A],
    a.ParametersJson AS A_Parameters,
    b.BacktestId AS [Backtest_B],
    b.ParametersJson AS B_Parameters
FROM BacktestOutcomes a
CROSS JOIN BacktestOutcomes b
WHERE a.OutcomeId = @outcomeid_a AND b.OutcomeId = @outcomeid_b;

-- 19f. Cumulative equity curve comparison (aligned by date)
PRINT '';
PRINT '>>> 19f. EQUITY CURVE COMPARISON (Daily Cumulative P&L)';
SELECT 
    COALESCE(a.Date, b.Date) AS Date,
    ISNULL(a.A_DailyPnL, 0) AS A_DailyPnL,
    ISNULL(a.A_CumPnL, 0) AS A_CumPnL,
    ISNULL(b.B_DailyPnL, 0) AS B_DailyPnL,
    ISNULL(b.B_CumPnL, 0) AS B_CumPnL,
    CAST(ISNULL(b.B_CumPnL, 0) - ISNULL(a.A_CumPnL, 0) AS DECIMAL(18,2)) AS CumPnL_Delta
FROM (
    SELECT Date,
        CAST(DailyPnL AS DECIMAL(18,2)) AS A_DailyPnL,
        CAST(SUM(DailyPnL) OVER (ORDER BY Date) AS DECIMAL(18,2)) AS A_CumPnL
    FROM DailyPerformance WHERE SessionId = @backtestid_a
) a
FULL OUTER JOIN (
    SELECT Date,
        CAST(DailyPnL AS DECIMAL(18,2)) AS B_DailyPnL,
        CAST(SUM(DailyPnL) OVER (ORDER BY Date) AS DECIMAL(18,2)) AS B_CumPnL
    FROM DailyPerformance WHERE SessionId = @backtestid_b
) b ON a.Date = b.Date
ORDER BY COALESCE(a.Date, b.Date);

PRINT '';
PRINT '============================================================================';
PRINT 'END OF BACKTEST MONITORING REPORT';
PRINT '============================================================================';
GO
