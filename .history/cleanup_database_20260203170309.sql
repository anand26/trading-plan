-- ============================================
-- Database Cleanup Script
-- ============================================
-- Purpose: 
--   1. Keep all backtest data
--   2. Delete incomplete OptimizationRuns and references
--   3. Delete paper/live trading data
--   4. Prepare for fresh paper trading
-- ============================================

USE [TradingDB]
GO

-- Start transaction for safety
BEGIN TRANSACTION;

PRINT '============================================'
PRINT 'Starting Database Cleanup'
PRINT '============================================'

-- ============================================
-- STEP 1: Delete incomplete OptimizationRuns
-- ============================================
PRINT ''
PRINT 'STEP 1: Deleting incomplete OptimizationRuns...'

DECLARE @DeletedOptRuns INT;

-- Delete incomplete optimization runs (Status != 'completed')
DELETE FROM OptimizationRuns
WHERE Status != 'completed' 
   OR EndTime IS NULL
   OR CompletedCombinations < TotalCombinations;

SET @DeletedOptRuns = @@ROWCOUNT;
PRINT 'Deleted ' + CAST(@DeletedOptRuns AS VARCHAR) + ' incomplete optimization runs'

-- ============================================
-- STEP 2: Delete Paper/Live Trading Data
-- ============================================
PRINT ''
PRINT 'STEP 2: Cleaning up paper/live trading data...'

-- Store session IDs to delete (paper and live sessions only)
DECLARE @NonBacktestSessions TABLE (SessionId VARCHAR(50));

INSERT INTO @NonBacktestSessions (SessionId)
SELECT SessionId 
FROM Sessions 
WHERE SessionType IN ('Paper', 'Live', 'paper', 'live');

DECLARE @SessionCount INT = (SELECT COUNT(*) FROM @NonBacktestSessions);
PRINT 'Found ' + CAST(@SessionCount AS VARCHAR) + ' paper/live sessions to clean'

-- Delete trades from paper/live sessions
IF COL_LENGTH('Trades', 'SessionId') IS NOT NULL
BEGIN
    DELETE FROM Trades 
    WHERE SessionId IN (SELECT SessionId FROM @NonBacktestSessions);
    PRINT '  - Deleted Trades: ' + CAST(@@ROWCOUNT AS VARCHAR)
END

-- Delete webhook events from paper/live sessions (if table and column exist)
IF OBJECT_ID('WebhookEvents', 'U') IS NOT NULL AND COL_LENGTH('WebhookEvents', 'SessionId') IS NOT NULL
BEGIN
    DELETE FROM WebhookEvents
    WHERE SessionId IN (SELECT SessionId FROM @NonBacktestSessions);
    PRINT '  - Deleted WebhookEvents: ' + CAST(@@ROWCOUNT AS VARCHAR)
END

-- Delete orders from paper/live sessions (if table exists)
IF OBJECT_ID('Orders', 'U') IS NOT NULL AND COL_LENGTH('Orders', 'SessionId') IS NOT NULL
BEGIN
    DELETE FROM Orders
    WHERE SessionId IN (SELECT SessionId FROM @NonBacktestSessions);
    PRINT '  - Deleted Orders: ' + CAST(@@ROWCOUNT AS VARCHAR)
END

-- Delete daily performance from paper/live sessions (if column exists)
IF COL_LENGTH('DailyPerformance', 'SessionId') IS NOT NULL
BEGIN
    DELETE FROM DailyPerformance
    WHERE SessionId IN (SELECT SessionId FROM @NonBacktestSessions);
    PRINT '  - Deleted DailyPerformance: ' + CAST(@@ROWCOUNT AS VARCHAR)
END
ELSE
BEGIN
    PRINT '  - DailyPerformance.SessionId column not found, skipping'
END

-- Delete account snapshots from paper/live sessions (if column exists)
IF COL_LENGTH('AccountSnapshots', 'SessionId') IS NOT NULL
BEGIN
    DELETE FROM AccountSnapshots
    WHERE SessionId IN (SELECT SessionId FROM @NonBacktestSessions);
    PRINT '  - Deleted AccountSnapshots: ' + CAST(@@ROWCOUNT AS VARCHAR)
END
ELSE
BEGIN
    PRINT '  - AccountSnapshots.SessionId column not found, skipping'
END

-- Delete the paper/live sessions themselves
DELETE FROM Sessions
WHERE SessionId IN (SELECT SessionId FROM @NonBacktestSessions);
PRINT '  - Deleted Sessions: ' + CAST(@@ROWCOUNT AS VARCHAR)

-- ============================================
-- STEP 3: Clean up orphaned data
-- ============================================
PRINT ''
PRINT 'STEP 3: Cleaning up orphaned data...'

-- Delete trades with no session (if SessionId column exists)
IF COL_LENGTH('Trades', 'SessionId') IS NOT NULL
BEGIN
    DELETE FROM Trades WHERE SessionId NOT IN (SELECT SessionId FROM Sessions);
    PRINT '  - Deleted orphaned Trades: ' + CAST(@@ROWCOUNT AS VARCHAR)
END

-- Delete webhook events with no session (if table and column exist)
IF OBJECT_ID('WebhookEvents', 'U') IS NOT NULL AND COL_LENGTH('WebhookEvents', 'SessionId') IS NOT NULL
BEGIN
    DELETE FROM WebhookEvents WHERE SessionId NOT IN (SELECT SessionId FROM Sessions);
    PRINT '  - Deleted orphaned WebhookEvents: ' + CAST(@@ROWCOUNT AS VARCHAR)
END

-- Delete orders with no session (if table and column exist)
IF OBJECT_ID('Orders', 'U') IS NOT NULL AND COL_LENGTH('Orders', 'SessionId') IS NOT NULL
BEGIN
    DELETE FROM Orders WHERE SessionId NOT IN (SELECT SessionId FROM Sessions);
    PRINT '  - Deleted orphaned Orders: ' + CAST(@@ROWCOUNT AS VARCHAR)
END

-- Delete daily performance with no session (if column exists)
IF COL_LENGTH('DailyPerformance', 'SessionId') IS NOT NULL
BEGIN
    DELETE FROM DailyPerformance WHERE SessionId NOT IN (SELECT SessionId FROM Sessions);
    PRINT '  - Deleted orphaned DailyPerformance: ' + CAST(@@ROWCOUNT AS VARCHAR)
END

-- Delete account snapshots with no session (if column exists)
IF COL_LENGTH('AccountSnapshots', 'SessionId') IS NOT NULL
BEGIN
    DELETE FROM AccountSnapshots WHERE SessionId NOT IN (SELECT SessionId FROM Sessions);
    PRINT '  - Deleted orphaned AccountSnapshots: ' + CAST(@@ROWCOUNT AS VARCHAR)
END

-- ============================================
-- STEP 4: Clean up webhook/agent related data
-- ============================================
PRINT ''
PRINT 'STEP 4: Cleaning up webhook and agent data...'

-- Clean old webhook events (keep last 100) - if table exists
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'WebhookEvents')
BEGIN
    DELETE FROM WebhookEvents 
    WHERE EventId NOT IN (
        SELECT TOP 100 EventId 
        FROM WebhookEvents 
        ORDER BY Timestamp DESC
    );
    PRINT '  - Cleaned WebhookEvents: ' + CAST(@@ROWCOUNT AS VARCHAR)
END
ELSE
BEGIN
    PRINT '  - WebhookEvents table not found, skipping'
END

-- Clean old agent decisions (keep last 500)
DELETE FROM AgentDecisions
WHERE Id NOT IN (
    SELECT TOP 500 Id
    FROM AgentDecisions
    ORDER BY CreatedAt DESC
);
PRINT '  - Cleaned AgentDecisions: ' + CAST(@@ROWCOUNT AS VARCHAR)

-- Clean old agent actions (keep last 500)
DELETE FROM AgentActions
WHERE Id NOT IN (
    SELECT TOP 500 Id
    FROM AgentActions
    ORDER BY CreatedAt DESC
);
PRINT '  - Cleaned AgentActions: ' + CAST(@@ROWCOUNT AS VARCHAR)

-- Clean old agent alerts (keep last 200)
DELETE FROM AgentAlerts
WHERE Id NOT IN (
    SELECT TOP 200 Id
    FROM AgentAlerts
    ORDER BY CreatedAt DESC
);
PRINT '  - Cleaned AgentAlerts: ' + CAST(@@ROWCOUNT AS VARCHAR)

-- Reset agent state (prepare for fresh run)
DELETE FROM AgentState;
PRINT '  - Reset AgentState: ' + CAST(@@ROWCOUNT AS VARCHAR)

-- ============================================
-- STEP 5: Verify backtest data integrity
-- ============================================
PRINT ''
PRINT 'STEP 5: Verifying backtest data...'

DECLARE @BacktestSessions INT = (SELECT COUNT(*) FROM Sessions WHERE SessionType = 'Backtest');
DECLARE @BacktestTrades INT = (SELECT COUNT(*) FROM Trades WHERE SessionId IN (SELECT SessionId FROM Sessions WHERE SessionType = 'Backtest'));
DECLARE @BacktestRuns INT = (SELECT COUNT(*) FROM BacktestRuns);
DECLARE @BacktestMetrics INT = (SELECT COUNT(*) FROM BacktestMetrics);

PRINT '  Remaining Backtest Data:'
PRINT '    - Sessions: ' + CAST(@BacktestSessions AS VARCHAR)
PRINT '    - Trades: ' + CAST(@BacktestTrades AS VARCHAR)
PRINT '    - BacktestRuns: ' + CAST(@BacktestRuns AS VARCHAR)
PRINT '    - BacktestMetrics: ' + CAST(@BacktestMetrics AS VARCHAR)

-- ============================================
-- STEP 6: Clean up ParameterHistory and old recommendations
-- ============================================
PRINT ''
PRINT 'STEP 6: Cleaning up parameter history and recommendations...'

-- Keep last 1000 parameter history entries
DELETE FROM ParameterHistory
WHERE HistoryId NOT IN (
    SELECT TOP 1000 HistoryId
    FROM ParameterHistory
    ORDER BY ChangedAt DESC
);
PRINT '  - Cleaned ParameterHistory: ' + CAST(@@ROWCOUNT AS VARCHAR)

-- Clean old recommendations (keep last 100)
DELETE FROM Recommendations
WHERE RecommendationID NOT IN (
    SELECT TOP 100 RecommendationID
    FROM Recommendations
    ORDER BY CreatedAt DESC
);
PRINT '  - Cleaned Recommendations: ' + CAST(@@ROWCOUNT AS VARCHAR)

-- Clean old patterns (keep last 200)
DELETE FROM Patterns
WHERE PatternID NOT IN (
    SELECT TOP 200 PatternID
    FROM Patterns
    ORDER BY UpdatedAt DESC
);
PRINT '  - Cleaned Patterns: ' + CAST(@@ROWCOUNT AS VARCHAR)

-- ============================================
-- STEP 7: Final Summary
-- ============================================
PRINT ''
PRINT '============================================'
PRINT 'Cleanup Summary:'
PRINT '============================================'
PRINT 'Database is ready for paper trading!'
PRINT ''

-- Get final counts
DECLARE @FinalOptRuns INT = (SELECT COUNT(*) FROM OptimizationRuns);

PRINT 'Remaining data:'
PRINT '  - Backtest Sessions: ' + CAST(@BacktestSessions AS VARCHAR)
PRINT '  - Backtest Trades: ' + CAST(@BacktestTrades AS VARCHAR)
PRINT '  - Completed OptimizationRuns: ' + CAST(@FinalOptRuns AS VARCHAR)
PRINT ''
PRINT 'Paper/Live sessions removed: ' + CAST(@SessionCount AS VARCHAR)
PRINT 'Incomplete OptimizationRuns removed: ' + CAST(@DeletedOptRuns AS VARCHAR)
PRINT '============================================'

-- Commit the transaction
COMMIT TRANSACTION;

PRINT ''
PRINT 'Cleanup completed successfully!'
PRINT ''
PRINT 'Next step: Start webhook stack and test paper trading'
GO
