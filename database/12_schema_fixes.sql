-- ================================================
-- Schema Fixes for TQQQScalpingAlgorithm
-- Run after initial schema creation
-- ================================================

USE TradingDB;
GO

-- ================================================
-- FIX 1: MarketRegimes table
-- Algorithm expects: Symbol, EndTime, StartTime, RegimeType, TrendDirection, Volatility, VixLevel
-- Current schema has different columns
-- ================================================

-- Add missing columns to MarketRegimes
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('MarketRegimes') AND name = 'Symbol')
BEGIN
    ALTER TABLE MarketRegimes ADD Symbol VARCHAR(20) NULL;
    PRINT 'Added column: MarketRegimes.Symbol';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('MarketRegimes') AND name = 'EndTime')
BEGIN
    ALTER TABLE MarketRegimes ADD EndTime DATETIME2 NULL;
    PRINT 'Added column: MarketRegimes.EndTime';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('MarketRegimes') AND name = 'StartTime')
BEGIN
    ALTER TABLE MarketRegimes ADD StartTime DATETIME2 NULL DEFAULT GETUTCDATE();
    PRINT 'Added column: MarketRegimes.StartTime';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('MarketRegimes') AND name = 'RegimeType')
BEGIN
    ALTER TABLE MarketRegimes ADD RegimeType VARCHAR(30) NULL;
    PRINT 'Added column: MarketRegimes.RegimeType';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('MarketRegimes') AND name = 'TrendDirection')
BEGIN
    ALTER TABLE MarketRegimes ADD TrendDirection VARCHAR(10) NULL;
    PRINT 'Added column: MarketRegimes.TrendDirection';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('MarketRegimes') AND name = 'Volatility')
BEGIN
    ALTER TABLE MarketRegimes ADD Volatility DECIMAL(10, 6) NULL;
    PRINT 'Added column: MarketRegimes.Volatility';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('MarketRegimes') AND name = 'VixLevel')
BEGIN
    ALTER TABLE MarketRegimes ADD VixLevel DECIMAL(10, 4) NULL;
    PRINT 'Added column: MarketRegimes.VixLevel';
END
GO

-- Create index on Symbol if not exists
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE object_id = OBJECT_ID('MarketRegimes') AND name = 'IX_MarketRegimes_Symbol')
BEGIN
    CREATE INDEX IX_MarketRegimes_Symbol ON MarketRegimes(Symbol);
    PRINT 'Created index: IX_MarketRegimes_Symbol';
END
GO

-- ================================================
-- FIX 2: DailyPerformance table
-- Algorithm expects: TradingDate, OpeningBalance, ClosingBalance, etc.
-- Current schema has: Date, StartingEquity, EndingEquity
-- ================================================

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'TradingDate')
BEGIN
    ALTER TABLE DailyPerformance ADD TradingDate DATE NULL;
    PRINT 'Added column: DailyPerformance.TradingDate';
    
    -- Copy existing Date values to TradingDate
    UPDATE DailyPerformance SET TradingDate = Date WHERE TradingDate IS NULL;
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'OpeningBalance')
BEGIN
    ALTER TABLE DailyPerformance ADD OpeningBalance DECIMAL(18, 4) NULL;
    PRINT 'Added column: DailyPerformance.OpeningBalance';
    
    -- Copy existing StartingEquity values
    UPDATE DailyPerformance SET OpeningBalance = StartingEquity WHERE OpeningBalance IS NULL;
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'ClosingBalance')
BEGIN
    ALTER TABLE DailyPerformance ADD ClosingBalance DECIMAL(18, 4) NULL;
    PRINT 'Added column: DailyPerformance.ClosingBalance';
    
    -- Copy existing EndingEquity values
    UPDATE DailyPerformance SET ClosingBalance = EndingEquity WHERE ClosingBalance IS NULL;
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'RealizedPnL')
BEGIN
    ALTER TABLE DailyPerformance ADD RealizedPnL DECIMAL(18, 4) NULL DEFAULT 0;
    PRINT 'Added column: DailyPerformance.RealizedPnL';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'UnrealizedPnL')
BEGIN
    ALTER TABLE DailyPerformance ADD UnrealizedPnL DECIMAL(18, 4) NULL DEFAULT 0;
    PRINT 'Added column: DailyPerformance.UnrealizedPnL';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'TotalPnL')
BEGIN
    ALTER TABLE DailyPerformance ADD TotalPnL DECIMAL(18, 4) NULL DEFAULT 0;
    PRINT 'Added column: DailyPerformance.TotalPnL';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'TotalPnLPct')
BEGIN
    ALTER TABLE DailyPerformance ADD TotalPnLPct DECIMAL(10, 6) NULL DEFAULT 0;
    PRINT 'Added column: DailyPerformance.TotalPnLPct';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'TradeCount')
BEGIN
    ALTER TABLE DailyPerformance ADD TradeCount INT NULL DEFAULT 0;
    PRINT 'Added column: DailyPerformance.TradeCount';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'WinCount')
BEGIN
    ALTER TABLE DailyPerformance ADD WinCount INT NULL DEFAULT 0;
    PRINT 'Added column: DailyPerformance.WinCount';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'LossCount')
BEGIN
    ALTER TABLE DailyPerformance ADD LossCount INT NULL DEFAULT 0;
    PRINT 'Added column: DailyPerformance.LossCount';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'VolumeTraded')
BEGIN
    ALTER TABLE DailyPerformance ADD VolumeTraded DECIMAL(18, 4) NULL DEFAULT 0;
    PRINT 'Added column: DailyPerformance.VolumeTraded';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'Commission')
BEGIN
    ALTER TABLE DailyPerformance ADD Commission DECIMAL(18, 4) NULL DEFAULT 0;
    PRINT 'Added column: DailyPerformance.Commission';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'MaxDrawdownDay')
BEGIN
    ALTER TABLE DailyPerformance ADD MaxDrawdownDay DECIMAL(10, 6) NULL DEFAULT 0;
    PRINT 'Added column: DailyPerformance.MaxDrawdownDay';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'LastUpdated')
BEGIN
    ALTER TABLE DailyPerformance ADD LastUpdated DATETIME2 NULL DEFAULT GETUTCDATE();
    PRINT 'Added column: DailyPerformance.LastUpdated';
END
GO

-- Drop the unique constraint on Date since we now use SessionId + TradingDate
IF EXISTS (SELECT * FROM sys.indexes WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'UQ__DailyPer__77387D071E5CE6E2')
BEGIN
    ALTER TABLE DailyPerformance DROP CONSTRAINT UQ__DailyPer__77387D071E5CE6E2;
    PRINT 'Dropped unique constraint on Date';
END
GO

-- Create composite index on SessionId + TradingDate
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE object_id = OBJECT_ID('DailyPerformance') AND name = 'IX_DailyPerformance_SessionDate')
BEGIN
    CREATE UNIQUE INDEX IX_DailyPerformance_SessionDate ON DailyPerformance(SessionId, TradingDate) WHERE SessionId IS NOT NULL AND TradingDate IS NOT NULL;
    PRINT 'Created index: IX_DailyPerformance_SessionDate';
END
GO

PRINT '';
PRINT '============================================';
PRINT 'Schema fixes applied successfully!';
PRINT '============================================';
GO
