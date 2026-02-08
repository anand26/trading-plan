-- ============================================================
-- Backfill NULL columns in BacktestOutcomes
-- Run this ONCE to populate missing data for existing rows
-- ============================================================

USE TradingDB;
GO

-- 1. Backfill Expectancy and ExpectancyRatio
UPDATE BacktestOutcomes
SET 
    Expectancy = CASE 
        WHEN TotalTrades > 0 AND AverageLoss != 0 
        THEN (WinRate * AverageWin) - ((1.0 - WinRate) * ABS(AverageLoss))
        ELSE 0 
    END,
    ExpectancyRatio = CASE 
        WHEN ABS(AverageLoss) > 0 AND TotalTrades > 0
        THEN ((WinRate * AverageWin) - ((1.0 - WinRate) * ABS(AverageLoss))) / ABS(AverageLoss)
        ELSE 0 
    END
WHERE Expectancy IS NULL;

PRINT 'Backfilled Expectancy and ExpectancyRatio';

-- 2. Backfill PerformanceGrade
UPDATE BacktestOutcomes
SET PerformanceGrade = CASE 
    WHEN SharpeRatio >= 2.0 THEN 'A'
    WHEN SharpeRatio >= 1.5 THEN 'B+'
    WHEN SharpeRatio >= 1.0 THEN 'B'
    WHEN SharpeRatio >= 0.5 THEN 'C+'
    WHEN SharpeRatio >= 0   THEN 'C'
    ELSE 'D'
END
WHERE PerformanceGrade IS NULL;

PRINT 'Backfilled PerformanceGrade';

-- 3. Backfill IsSuccessful
UPDATE BacktestOutcomes
SET IsSuccessful = CASE 
    WHEN SharpeRatio >= 1.0 AND WinRate >= 0.4 AND ABS(MaxDrawdown) <= 0.20 
    THEN 1 
    ELSE 0 
END
WHERE IsSuccessful IS NULL;

PRINT 'Backfilled IsSuccessful';

-- 4. Backfill Notes
UPDATE BacktestOutcomes
SET Notes = CASE
    WHEN TotalReturn > 0 THEN 'Profitable (' + CAST(CAST(TotalReturn * 100 AS DECIMAL(10,1)) AS VARCHAR) + '%) | Grade:' + ISNULL(PerformanceGrade, '?')
    ELSE 'Loss (' + CAST(CAST(TotalReturn * 100 AS DECIMAL(10,1)) AS VARCHAR) + '%) | Grade:' + ISNULL(PerformanceGrade, '?')
END + CASE WHEN TotalTrades = 0 THEN ' | NO TRADES' ELSE '' END
WHERE Notes IS NULL;

PRINT 'Backfilled Notes';

-- 5. Backfill LargestWin/LargestLoss from Trades table (if available)
UPDATE bo
SET 
    bo.LargestWin = ISNULL(t.MaxWin, 0),
    bo.LargestLoss = ISNULL(t.MaxLoss, 0)
FROM BacktestOutcomes bo
OUTER APPLY (
    SELECT 
        MAX(CASE WHEN GrossPnL > 0 THEN GrossPnL ELSE 0 END) AS MaxWin,
        MAX(CASE WHEN GrossPnL < 0 THEN ABS(GrossPnL) ELSE 0 END) AS MaxLoss
    FROM Trades 
    WHERE Trades.SessionId = bo.BacktestId
) t
WHERE bo.LargestWin IS NULL OR bo.LargestLoss IS NULL;

PRINT 'Backfilled LargestWin/LargestLoss from Trades table';

-- 6. Verify the results
SELECT 
    StrategyId,
    COUNT(*) AS TotalRows,
    SUM(CASE WHEN Expectancy IS NOT NULL THEN 1 ELSE 0 END) AS HasExpectancy,
    SUM(CASE WHEN PerformanceGrade IS NOT NULL THEN 1 ELSE 0 END) AS HasGrade,
    SUM(CASE WHEN IsSuccessful IS NOT NULL THEN 1 ELSE 0 END) AS HasSuccess,
    SUM(CASE WHEN LargestWin IS NOT NULL THEN 1 ELSE 0 END) AS HasLargestWin,
    SUM(CASE WHEN Notes IS NOT NULL THEN 1 ELSE 0 END) AS HasNotes
FROM BacktestOutcomes
GROUP BY StrategyId;

PRINT 'Backfill complete!';
GO
