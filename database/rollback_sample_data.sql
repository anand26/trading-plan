-- ============================================
-- Rollback Sample Data
-- ============================================
-- Removes all test data inserted by sample data scripts
-- Execute with: sqlcmd -S localhost -E -d TradingDB -i rollback_sample_data.sql
-- ============================================

USE TradingDB;
GO

PRINT 'Rolling back sample data...';

-- Delete in reverse dependency order

-- Delete trades referencing test sessions
DELETE FROM Trades WHERE SessionId LIKE 'TEST_%' OR SessionId LIKE 'BACKTEST_%' OR SessionId LIKE 'PAPER_%' OR SessionId LIKE 'LIVE_%';
PRINT '  - Trades deleted';

-- Delete daily performance for test sessions
DELETE FROM DailyPerformance WHERE SessionId LIKE 'TEST_%' OR SessionId LIKE 'BACKTEST_%' OR SessionId LIKE 'PAPER_%' OR SessionId LIKE 'LIVE_%';
PRINT '  - DailyPerformance deleted';

-- Delete market regimes for test sessions
DELETE FROM MarketRegimes WHERE SessionId LIKE 'TEST_%' OR SessionId LIKE 'BACKTEST_%' OR SessionId LIKE 'PAPER_%' OR SessionId LIKE 'LIVE_%';
PRINT '  - MarketRegimes deleted';

-- Delete learning store entries for test sessions
DELETE FROM LearningStore WHERE Source LIKE 'TEST_%' OR Source LIKE 'BACKTEST_%' OR Source LIKE 'PAPER_%' OR Source LIKE 'LIVE_%';
PRINT '  - LearningStore deleted';

-- Delete optimal parameters for test sessions
DELETE FROM OptimalParameters WHERE MarketRegime LIKE 'TEST_%' OR ParameterName LIKE 'TEST_%';
PRINT '  - OptimalParameters deleted';

-- Delete parameter performance data
DELETE FROM ParameterPerformance WHERE MarketRegime IS NOT NULL;
PRINT '  - ParameterPerformance deleted';

-- Delete backtest runs
DELETE FROM BacktestMetrics WHERE RunID LIKE 'TEST_%' OR RunID LIKE 'RUN_%';
DELETE FROM BacktestRuns WHERE RunID LIKE 'TEST_%' OR RunID LIKE 'RUN_%';
PRINT '  - BacktestRuns/Metrics deleted';

-- Delete audit log entries
DELETE FROM AuditLog WHERE Details LIKE '%TEST%' OR Details LIKE '%Sample%';
PRINT '  - AuditLog cleaned';

-- Finally delete test sessions
DELETE FROM Sessions WHERE SessionId LIKE 'TEST_%' OR SessionId LIKE 'BACKTEST_%' OR SessionId LIKE 'PAPER_%' OR SessionId LIKE 'LIVE_%';
PRINT '  - Sessions deleted';

PRINT '';
PRINT '✓ Sample data rollback complete!';
GO
