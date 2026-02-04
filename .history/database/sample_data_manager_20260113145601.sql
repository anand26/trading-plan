-- ============================================================================
-- TRADING DASHBOARD SAMPLE DATA MANAGER
-- ============================================================================
-- This script manages sample/test data for the Trading Dashboard
-- 
-- Usage:
--   To ROLLBACK (delete all sample data):
--     sqlcmd -S localhost -E -d TradingDB -v Action=ROLLBACK -i sample_data_manager.sql
--
--   To INSERT (create sample data):
--     sqlcmd -S localhost -E -d TradingDB -v Action=INSERT -i sample_data_manager.sql
--
--   To RESET (rollback then insert):
--     sqlcmd -S localhost -E -d TradingDB -v Action=RESET -i sample_data_manager.sql
--
-- ============================================================================

SET NOCOUNT ON;

-- Default action if not specified
IF '$(Action)' = '$' + '(Action)'
BEGIN
    PRINT 'No action specified. Use -v Action=ROLLBACK|INSERT|RESET';
    PRINT 'Example: sqlcmd -S localhost -E -d TradingDB -v Action=RESET -i sample_data_manager.sql';
END
GO

-- ============================================================================
-- ROLLBACK SECTION - Delete all sample data
-- ============================================================================
IF '$(Action)' IN ('ROLLBACK', 'RESET')
BEGIN
    PRINT '============================================';
    PRINT 'ROLLING BACK SAMPLE DATA...';
    PRINT '============================================';
    
    -- Delete in order respecting foreign keys
    DELETE FROM dbo.BacktestMetrics;
    PRINT 'Cleared BacktestMetrics';
    
    DELETE FROM dbo.BacktestRuns;
    PRINT 'Cleared BacktestRuns';
    
    DELETE FROM dbo.Trades;
    PRINT 'Cleared Trades';
    
    DELETE FROM dbo.DailyPerformance;
    PRINT 'Cleared DailyPerformance';
    
    DELETE FROM dbo.Sessions;
    PRINT 'Cleared Sessions';
    
    DELETE FROM dbo.MarketRegimes;
    PRINT 'Cleared MarketRegimes';
    
    DELETE FROM dbo.LearningStore;
    PRINT 'Cleared LearningStore';
    
    DELETE FROM dbo.AuditLog;
    PRINT 'Cleared AuditLog';
    
    DELETE FROM dbo.OptimalParameters;
    PRINT 'Cleared OptimalParameters';
    
    DELETE FROM dbo.OptimalParameterValues;
    PRINT 'Cleared OptimalParameterValues';
    
    DELETE FROM dbo.ParameterPerformance;
    PRINT 'Cleared ParameterPerformance';
    
    DELETE FROM dbo.Parameters;
    PRINT 'Cleared Parameters';
    
    DELETE FROM dbo.StrategyParameters;
    PRINT 'Cleared StrategyParameters';
    
    DELETE FROM dbo.SystemConfig;
    PRINT 'Cleared SystemConfig';
    
    PRINT '';
    PRINT 'ROLLBACK COMPLETE';
    PRINT '';
END
GO

-- ============================================================================
-- INSERT SECTION - Create all sample data
-- ============================================================================
IF '$(Action)' IN ('INSERT', 'RESET')
BEGIN
    PRINT '============================================';
    PRINT 'INSERTING SAMPLE DATA...';
    PRINT '============================================';
    
    -- =========================================================================
    -- 1. SESSIONS - Create sessions for each type
    -- =========================================================================
    PRINT 'Creating Sessions...';
    
    INSERT INTO dbo.Sessions (SessionId, SessionType, StrategyId, StartTime, EndTime, Status, Notes, CreatedAt)
    VALUES 
    ('BACKTEST-2025-001', 'BACKTEST', 'TQQQScalpingAlgorithm', '2025-12-01 09:30:00', '2025-12-31 16:00:00', 'COMPLETED', 'December 2025 backtest run', GETDATE()),
    ('BACKTEST-2025-002', 'BACKTEST', 'TQQQScalpingAlgorithm', '2025-11-01 09:30:00', '2025-11-30 16:00:00', 'COMPLETED', 'November 2025 backtest run', GETDATE()),
    ('PAPER-2026-001', 'PAPER', 'TQQQScalpingAlgorithm', '2026-01-02 09:30:00', NULL, 'ACTIVE', 'January 2026 paper trading', GETDATE()),
    ('PAPER-2025-001', 'PAPER', 'TQQQScalpingAlgorithm', '2025-12-15 09:30:00', '2025-12-31 16:00:00', 'COMPLETED', 'December 2025 paper trading', GETDATE()),
    ('LIVE-2026-001', 'LIVE', 'TQQQScalpingAlgorithm', '2026-01-06 09:30:00', NULL, 'ACTIVE', 'January 2026 live trading', GETDATE()),
    ('LIVE-2025-001', 'LIVE', 'TQQQScalpingAlgorithm', '2025-12-20 09:30:00', '2025-12-31 16:00:00', 'COMPLETED', 'December 2025 live trading', GETDATE());
    
    PRINT '  Inserted 6 sessions';
    
    -- =========================================================================
    -- 2. TRADES - Sample trades for each session
    -- =========================================================================
    PRINT 'Creating Trades...';
    
    -- Backtest trades (BACKTEST-2025-001)
    INSERT INTO dbo.Trades (SessionId, Symbol, EntryTime, ExitTime, Direction, EntryPrice, ExitPrice, EntryQuantity, ExitQuantity, GrossPnL, Commission, NetPnL, PnLPercent, ExitReason, DurationMinutes)
    VALUES 
    ('BACKTEST-2025-001', 'TQQQ', '2025-12-15 10:30:00', '2025-12-15 11:45:00', 'LONG', 52.50, 53.25, 100, 100, 75.00, 2.00, 73.00, 1.43, 'TAKE_PROFIT', 75),
    ('BACKTEST-2025-001', 'TQQQ', '2025-12-16 09:45:00', '2025-12-16 10:30:00', 'LONG', 53.00, 52.20, 100, 100, -80.00, 2.00, -82.00, -1.51, 'STOP_LOSS', 45),
    ('BACKTEST-2025-001', 'TQQQ', '2025-12-17 14:00:00', '2025-12-17 15:30:00', 'LONG', 51.80, 53.50, 150, 150, 255.00, 3.00, 252.00, 3.28, 'TAKE_PROFIT', 90),
    ('BACKTEST-2025-001', 'SQQQ', '2025-12-18 10:00:00', '2025-12-18 11:00:00', 'LONG', 12.50, 12.80, 200, 200, 60.00, 2.00, 58.00, 2.40, 'TAKE_PROFIT', 60),
    ('BACKTEST-2025-001', 'TQQQ', '2025-12-19 13:30:00', '2025-12-19 14:15:00', 'LONG', 54.00, 53.50, 100, 100, -50.00, 2.00, -52.00, -0.93, 'STOP_LOSS', 45),
    ('BACKTEST-2025-001', 'TQQQ', '2025-12-20 09:35:00', '2025-12-20 11:00:00', 'LONG', 53.20, 54.80, 120, 120, 192.00, 2.40, 189.60, 3.01, 'TAKE_PROFIT', 85),
    ('BACKTEST-2025-001', 'TQQQ', '2025-12-22 10:15:00', '2025-12-22 12:30:00', 'LONG', 55.00, 55.75, 100, 100, 75.00, 2.00, 73.00, 1.36, 'TAKE_PROFIT', 135),
    ('BACKTEST-2025-001', 'SQQQ', '2025-12-23 11:00:00', '2025-12-23 13:00:00', 'LONG', 11.80, 11.50, 250, 250, -75.00, 2.50, -77.50, -2.54, 'STOP_LOSS', 120),
    ('BACKTEST-2025-001', 'TQQQ', '2025-12-26 09:45:00', '2025-12-26 11:30:00', 'LONG', 56.00, 57.20, 100, 100, 120.00, 2.00, 118.00, 2.14, 'TAKE_PROFIT', 105),
    ('BACKTEST-2025-001', 'TQQQ', '2025-12-27 14:00:00', '2025-12-27 15:45:00', 'LONG', 57.50, 56.80, 80, 80, -56.00, 1.60, -57.60, -1.22, 'STOP_LOSS', 105);
    
    -- Backtest trades (BACKTEST-2025-002)
    INSERT INTO dbo.Trades (SessionId, Symbol, EntryTime, ExitTime, Direction, EntryPrice, ExitPrice, EntryQuantity, ExitQuantity, GrossPnL, Commission, NetPnL, PnLPercent, ExitReason, DurationMinutes)
    VALUES 
    ('BACKTEST-2025-002', 'TQQQ', '2025-11-10 10:00:00', '2025-11-10 12:00:00', 'LONG', 48.00, 49.20, 100, 100, 120.00, 2.00, 118.00, 2.50, 'TAKE_PROFIT', 120),
    ('BACKTEST-2025-002', 'TQQQ', '2025-11-12 09:30:00', '2025-11-12 10:45:00', 'LONG', 49.50, 48.80, 100, 100, -70.00, 2.00, -72.00, -1.41, 'STOP_LOSS', 75),
    ('BACKTEST-2025-002', 'TQQQ', '2025-11-15 11:00:00', '2025-11-15 14:00:00', 'LONG', 50.00, 51.50, 120, 120, 180.00, 2.40, 177.60, 3.00, 'TAKE_PROFIT', 180),
    ('BACKTEST-2025-002', 'SQQQ', '2025-11-18 13:00:00', '2025-11-18 14:30:00', 'LONG', 13.20, 13.60, 200, 200, 80.00, 2.00, 78.00, 3.03, 'TAKE_PROFIT', 90),
    ('BACKTEST-2025-002', 'TQQQ', '2025-11-20 10:30:00', '2025-11-20 11:15:00', 'LONG', 51.00, 52.00, 100, 100, 100.00, 2.00, 98.00, 1.96, 'TAKE_PROFIT', 45),
    ('BACKTEST-2025-002', 'TQQQ', '2025-11-22 14:00:00', '2025-11-22 15:30:00', 'LONG', 52.50, 51.80, 100, 100, -70.00, 2.00, -72.00, -1.33, 'STOP_LOSS', 90);
    
    -- Paper trades (PAPER-2026-001)
    INSERT INTO dbo.Trades (SessionId, Symbol, EntryTime, ExitTime, Direction, EntryPrice, ExitPrice, EntryQuantity, ExitQuantity, GrossPnL, Commission, NetPnL, PnLPercent, ExitReason, DurationMinutes)
    VALUES 
    ('PAPER-2026-001', 'TQQQ', '2026-01-02 10:00:00', '2026-01-02 11:30:00', 'LONG', 58.00, 59.20, 80, 80, 96.00, 1.60, 94.40, 2.07, 'TAKE_PROFIT', 90),
    ('PAPER-2026-001', 'TQQQ', '2026-01-03 09:45:00', '2026-01-03 10:30:00', 'LONG', 59.50, 58.80, 80, 80, -56.00, 1.60, -57.60, -1.18, 'STOP_LOSS', 45),
    ('PAPER-2026-001', 'TQQQ', '2026-01-06 11:00:00', '2026-01-06 13:00:00', 'LONG', 59.00, 60.50, 100, 100, 150.00, 2.00, 148.00, 2.54, 'TAKE_PROFIT', 120),
    ('PAPER-2026-001', 'SQQQ', '2026-01-07 10:30:00', '2026-01-07 12:00:00', 'LONG', 11.00, 11.40, 150, 150, 60.00, 1.50, 58.50, 3.64, 'TAKE_PROFIT', 90),
    ('PAPER-2026-001', 'TQQQ', '2026-01-08 14:00:00', '2026-01-08 15:00:00', 'LONG', 60.00, 60.80, 80, 80, 64.00, 1.60, 62.40, 1.33, 'TAKE_PROFIT', 60),
    ('PAPER-2026-001', 'TQQQ', '2026-01-09 09:35:00', '2026-01-09 10:15:00', 'LONG', 61.00, 60.20, 80, 80, -64.00, 1.60, -65.60, -1.31, 'STOP_LOSS', 40),
    ('PAPER-2026-001', 'TQQQ', '2026-01-10 11:00:00', '2026-01-10 13:30:00', 'LONG', 60.50, 62.00, 100, 100, 150.00, 2.00, 148.00, 2.48, 'TAKE_PROFIT', 150);
    
    -- Paper trades (PAPER-2025-001)
    INSERT INTO dbo.Trades (SessionId, Symbol, EntryTime, ExitTime, Direction, EntryPrice, ExitPrice, EntryQuantity, ExitQuantity, GrossPnL, Commission, NetPnL, PnLPercent, ExitReason, DurationMinutes)
    VALUES 
    ('PAPER-2025-001', 'TQQQ', '2025-12-16 10:00:00', '2025-12-16 11:30:00', 'LONG', 53.50, 54.50, 80, 80, 80.00, 1.60, 78.40, 1.87, 'TAKE_PROFIT', 90),
    ('PAPER-2025-001', 'TQQQ', '2025-12-17 14:00:00', '2025-12-17 15:00:00', 'LONG', 54.00, 53.20, 80, 80, -64.00, 1.60, -65.60, -1.48, 'STOP_LOSS', 60),
    ('PAPER-2025-001', 'TQQQ', '2025-12-18 09:45:00', '2025-12-18 12:00:00', 'LONG', 53.00, 55.00, 100, 100, 200.00, 2.00, 198.00, 3.77, 'TAKE_PROFIT', 135),
    ('PAPER-2025-001', 'SQQQ', '2025-12-19 11:00:00', '2025-12-19 12:30:00', 'LONG', 12.00, 12.35, 150, 150, 52.50, 1.50, 51.00, 2.92, 'TAKE_PROFIT', 90);
    
    -- Live trades (LIVE-2026-001)
    INSERT INTO dbo.Trades (SessionId, Symbol, EntryTime, ExitTime, Direction, EntryPrice, ExitPrice, EntryQuantity, ExitQuantity, GrossPnL, Commission, NetPnL, PnLPercent, ExitReason, DurationMinutes)
    VALUES 
    ('LIVE-2026-001', 'TQQQ', '2026-01-06 10:30:00', '2026-01-06 12:00:00', 'LONG', 59.00, 60.20, 40, 40, 48.00, 0.80, 47.20, 2.03, 'TAKE_PROFIT', 90),
    ('LIVE-2026-001', 'TQQQ', '2026-01-07 09:45:00', '2026-01-07 10:30:00', 'LONG', 60.50, 59.80, 40, 40, -28.00, 0.80, -28.80, -1.16, 'STOP_LOSS', 45),
    ('LIVE-2026-001', 'TQQQ', '2026-01-08 11:00:00', '2026-01-08 13:00:00', 'LONG', 60.00, 61.50, 50, 50, 75.00, 1.00, 74.00, 2.50, 'TAKE_PROFIT', 120),
    ('LIVE-2026-001', 'TQQQ', '2026-01-09 14:00:00', '2026-01-09 15:00:00', 'LONG', 61.00, 61.80, 40, 40, 32.00, 0.80, 31.20, 1.31, 'TAKE_PROFIT', 60),
    ('LIVE-2026-001', 'TQQQ', '2026-01-10 10:00:00', '2026-01-10 11:30:00', 'LONG', 62.00, 61.20, 40, 40, -32.00, 0.80, -32.80, -1.29, 'STOP_LOSS', 90);
    
    -- Live trades (LIVE-2025-001)
    INSERT INTO dbo.Trades (SessionId, Symbol, EntryTime, ExitTime, Direction, EntryPrice, ExitPrice, EntryQuantity, ExitQuantity, GrossPnL, Commission, NetPnL, PnLPercent, ExitReason, DurationMinutes)
    VALUES 
    ('LIVE-2025-001', 'TQQQ', '2025-12-22 10:00:00', '2025-12-22 11:30:00', 'LONG', 55.50, 56.50, 40, 40, 40.00, 0.80, 39.20, 1.80, 'TAKE_PROFIT', 90),
    ('LIVE-2025-001', 'TQQQ', '2025-12-23 14:00:00', '2025-12-23 15:00:00', 'LONG', 56.00, 55.30, 40, 40, -28.00, 0.80, -28.80, -1.25, 'STOP_LOSS', 60),
    ('LIVE-2025-001', 'TQQQ', '2025-12-26 09:45:00', '2025-12-26 12:00:00', 'LONG', 56.50, 58.00, 50, 50, 75.00, 1.00, 74.00, 2.65, 'TAKE_PROFIT', 135),
    ('LIVE-2025-001', 'SQQQ', '2025-12-27 11:00:00', '2025-12-27 12:30:00', 'LONG', 11.50, 11.80, 100, 100, 30.00, 1.00, 29.00, 2.61, 'TAKE_PROFIT', 90);
    
    PRINT '  Inserted 36 trades';
    
    -- =========================================================================
    -- 3. DAILY PERFORMANCE - Aggregated daily stats
    -- =========================================================================
    PRINT 'Creating Daily Performance...';
    
    DECLARE @i INT = 0;
    DECLARE @date DATE;
    DECLARE @sessionId NVARCHAR(50);
    DECLARE @baseEquity DECIMAL(18,2);
    DECLARE @dailyPnL DECIMAL(18,2);
    DECLARE @equity DECIMAL(18,2);
    
    -- Backtest daily performance (BACKTEST-2025-001)
    SET @sessionId = 'BACKTEST-2025-001';
    SET @baseEquity = 100000.00;
    SET @equity = @baseEquity;
    SET @i = 0;
    WHILE @i < 20
    BEGIN
        SET @date = DATEADD(day, @i, '2025-12-10');
        IF DATEPART(dw, @date) NOT IN (1, 7) -- Skip weekends
        BEGIN
            SET @dailyPnL = ROUND((RAND(CHECKSUM(NEWID())) - 0.4) * 500, 2);
            SET @equity = @equity + @dailyPnL;
            INSERT INTO dbo.DailyPerformance (SessionId, Date, StartingEquity, EndingEquity, DailyPnL, DailyPnLPercent, CumulativePnL, NumTrades, WinningTrades, LosingTrades, GrossProfit, GrossLoss, MaxDrawdown)
            VALUES (@sessionId, @date, @equity - @dailyPnL, @equity, @dailyPnL, @dailyPnL / (@equity - @dailyPnL) * 100, @equity - @baseEquity, 
                    ABS(CHECKSUM(NEWID())) % 5 + 1, ABS(CHECKSUM(NEWID())) % 4, ABS(CHECKSUM(NEWID())) % 3, 
                    CASE WHEN @dailyPnL > 0 THEN @dailyPnL ELSE 0 END, CASE WHEN @dailyPnL < 0 THEN ABS(@dailyPnL) ELSE 0 END, 
                    ROUND((RAND(CHECKSUM(NEWID()))) * 3, 2));
        END
        SET @i = @i + 1;
    END
    
    -- Paper daily performance (PAPER-2026-001)
    SET @sessionId = 'PAPER-2026-001';
    SET @baseEquity = 50000.00;
    SET @equity = @baseEquity;
    SET @i = 0;
    WHILE @i < 12
    BEGIN
        SET @date = DATEADD(day, @i, '2026-01-02');
        IF DATEPART(dw, @date) NOT IN (1, 7)
        BEGIN
            SET @dailyPnL = ROUND((RAND(CHECKSUM(NEWID())) - 0.35) * 300, 2);
            SET @equity = @equity + @dailyPnL;
            INSERT INTO dbo.DailyPerformance (SessionId, Date, StartingEquity, EndingEquity, DailyPnL, DailyPnLPercent, CumulativePnL, NumTrades, WinningTrades, LosingTrades, GrossProfit, GrossLoss, MaxDrawdown)
            VALUES (@sessionId, @date, @equity - @dailyPnL, @equity, @dailyPnL, @dailyPnL / (@equity - @dailyPnL) * 100, @equity - @baseEquity,
                    ABS(CHECKSUM(NEWID())) % 4 + 1, ABS(CHECKSUM(NEWID())) % 3, ABS(CHECKSUM(NEWID())) % 2,
                    CASE WHEN @dailyPnL > 0 THEN @dailyPnL ELSE 0 END, CASE WHEN @dailyPnL < 0 THEN ABS(@dailyPnL) ELSE 0 END,
                    ROUND((RAND(CHECKSUM(NEWID()))) * 2, 2));
        END
        SET @i = @i + 1;
    END
    
    -- Live daily performance (LIVE-2026-001)
    SET @sessionId = 'LIVE-2026-001';
    SET @baseEquity = 25000.00;
    SET @equity = @baseEquity;
    SET @i = 0;
    WHILE @i < 10
    BEGIN
        SET @date = DATEADD(day, @i, '2026-01-06');
        IF DATEPART(dw, @date) NOT IN (1, 7)
        BEGIN
            SET @dailyPnL = ROUND((RAND(CHECKSUM(NEWID())) - 0.35) * 150, 2);
            SET @equity = @equity + @dailyPnL;
            INSERT INTO dbo.DailyPerformance (SessionId, Date, StartingEquity, EndingEquity, DailyPnL, DailyPnLPercent, CumulativePnL, NumTrades, WinningTrades, LosingTrades, GrossProfit, GrossLoss, MaxDrawdown)
            VALUES (@sessionId, @date, @equity - @dailyPnL, @equity, @dailyPnL, @dailyPnL / (@equity - @dailyPnL) * 100, @equity - @baseEquity,
                    ABS(CHECKSUM(NEWID())) % 3 + 1, ABS(CHECKSUM(NEWID())) % 2 + 1, ABS(CHECKSUM(NEWID())) % 2,
                    CASE WHEN @dailyPnL > 0 THEN @dailyPnL ELSE 0 END, CASE WHEN @dailyPnL < 0 THEN ABS(@dailyPnL) ELSE 0 END,
                    ROUND((RAND(CHECKSUM(NEWID()))) * 1.5, 2));
        END
        SET @i = @i + 1;
    END
    
    PRINT '  Inserted daily performance records';
    
    -- =========================================================================
    -- 4. MARKET REGIMES - Market condition classifications
    -- =========================================================================
    PRINT 'Creating Market Regimes...';
    
    INSERT INTO dbo.MarketRegimes (Date, Regime, Confidence, QQQ_Close, EMA_Spread, QQQ_ATR, TrendStrength)
    VALUES 
    ('2026-01-03', 'BULLISH', 0.85, 520.50, 2.4, 8.5, 0.75),
    ('2026-01-04', 'BULLISH', 0.82, 525.20, 3.3, 8.2, 0.78),
    ('2026-01-05', 'BULLISH', 0.78, 522.80, 1.8, 9.1, 0.65),
    ('2026-01-06', 'RANGING', 0.65, 518.40, -0.5, 10.2, 0.35),
    ('2026-01-07', 'BEARISH', 0.72, 512.30, -2.1, 11.5, -0.45),
    ('2026-01-08', 'BEARISH', 0.68, 508.90, -1.8, 12.0, -0.38),
    ('2026-01-09', 'VOLATILE', 0.75, 515.60, 0.8, 14.5, 0.15),
    ('2026-01-10', 'BULLISH', 0.70, 522.40, 2.5, 11.8, 0.55),
    ('2026-01-11', 'BULLISH', 0.80, 528.10, 3.8, 9.5, 0.72),
    ('2026-01-12', 'BULLISH', 0.85, 532.50, 4.2, 8.8, 0.82);
    
    PRINT '  Inserted 10 market regime records';
    
    -- =========================================================================
    -- 5. LEARNING STORE - Pattern learning data
    -- =========================================================================
    PRINT 'Creating Learning Store...';
    
    INSERT INTO dbo.LearningStore (PatternType, PatternData, Confidence, Description, Metadata, IsActive, CreatedAt)
    VALUES 
    ('RSI_REVERSAL', '{"rsi_threshold": 28, "confirmation_bars": 2}', 0.82, 'RSI oversold reversal pattern identified', '{"source": "backtest", "sample_size": 150}', 1, DATEADD(day, -5, GETDATE())),
    ('EMA_CROSSOVER', '{"fast_ema": 9, "slow_ema": 21, "confirmation": "volume"}', 0.78, 'EMA crossover with volume confirmation', '{"source": "backtest", "sample_size": 120}', 1, DATEADD(day, -4, GETDATE())),
    ('MOMENTUM_SHIFT', '{"momentum_threshold": 0.5, "atr_multiplier": 1.5}', 0.75, 'Momentum regime shift detection', '{"source": "live", "sample_size": 85}', 1, DATEADD(day, -3, GETDATE())),
    ('VOLATILITY_BREAKOUT', '{"atr_period": 14, "breakout_mult": 2.0}', 0.70, 'High volatility breakout pattern', '{"source": "paper", "sample_size": 95}', 1, DATEADD(day, -2, GETDATE())),
    ('TREND_CONTINUATION', '{"trend_strength": 0.6, "pullback_depth": 0.382}', 0.85, 'Trend continuation after pullback', '{"source": "backtest", "sample_size": 200}', 1, DATEADD(day, -1, GETDATE())),
    ('MEAN_REVERSION', '{"bb_period": 20, "bb_std": 2.0}', 0.72, 'Bollinger band mean reversion', '{"source": "backtest", "sample_size": 110}', 1, GETDATE()),
    ('GAP_FILL', '{"min_gap_percent": 1.0, "fill_probability": 0.65}', 0.68, 'Opening gap fill pattern', '{"source": "live", "sample_size": 75}', 1, GETDATE()),
    ('VOLUME_SPIKE', '{"volume_mult": 2.5, "price_change_min": 0.5}', 0.74, 'Volume spike with price movement', '{"source": "paper", "sample_size": 90}', 1, GETDATE());
    
    PRINT '  Inserted 8 learning patterns';
    
    -- =========================================================================
    -- 6. AUDIT LOG - System activity log
    -- =========================================================================
    PRINT 'Creating Audit Log...';
    
    INSERT INTO dbo.AuditLog (Timestamp, EventType, Severity, Source, Message, Symbol, SessionId)
    VALUES 
    (DATEADD(hour, -168, GETDATE()), 'SYSTEM_START', 'INFO', 'TradingEngine', 'Trading system initialized successfully', NULL, 'LIVE-2026-001'),
    (DATEADD(hour, -144, GETDATE()), 'TRADE_EXECUTED', 'INFO', 'OrderManager', 'Buy order executed for TQQQ', 'TQQQ', 'LIVE-2026-001'),
    (DATEADD(hour, -120, GETDATE()), 'PARAMETER_UPDATE', 'INFO', 'AdaptiveAgent', 'Updated stop loss parameter from 0.02 to 0.018', NULL, 'LIVE-2026-001'),
    (DATEADD(hour, -96, GETDATE()), 'REGIME_CHANGE', 'WARNING', 'RegimeDetector', 'Market regime changed from BULLISH to RANGING', NULL, NULL),
    (DATEADD(hour, -72, GETDATE()), 'TRADE_EXECUTED', 'INFO', 'OrderManager', 'Sell order executed for TQQQ - Take Profit', 'TQQQ', 'LIVE-2026-001'),
    (DATEADD(hour, -48, GETDATE()), 'API_ERROR', 'ERROR', 'AlpacaConnector', 'Rate limit exceeded, retrying in 60s', NULL, NULL),
    (DATEADD(hour, -36, GETDATE()), 'BACKTEST_COMPLETE', 'INFO', 'BacktestEngine', 'Backtest completed: 15.2% return, 1.85 Sharpe', NULL, 'BACKTEST-2025-001'),
    (DATEADD(hour, -24, GETDATE()), 'LEARNING_UPDATE', 'INFO', 'LearningStore', 'New pattern identified: RSI_REVERSAL', NULL, NULL),
    (DATEADD(hour, -12, GETDATE()), 'TRADE_EXECUTED', 'INFO', 'OrderManager', 'Buy order executed for SQQQ', 'SQQQ', 'PAPER-2026-001'),
    (DATEADD(hour, -6, GETDATE()), 'RISK_ALERT', 'WARNING', 'RiskManager', 'Position size approaching limit (85% of max)', 'TQQQ', 'LIVE-2026-001'),
    (DATEADD(hour, -2, GETDATE()), 'TRADE_EXECUTED', 'INFO', 'OrderManager', 'Sell order executed for SQQQ - Stop Loss', 'SQQQ', 'PAPER-2026-001'),
    (DATEADD(hour, -1, GETDATE()), 'SYSTEM_HEALTH', 'INFO', 'HealthMonitor', 'System health check passed - all components operational', NULL, NULL);
    
    PRINT '  Inserted 12 audit log entries';
    
    -- =========================================================================
    -- 7. OPTIMAL PARAMETERS - Parameter recommendations
    -- =========================================================================
    PRINT 'Creating Optimal Parameters...';
    
    INSERT INTO dbo.OptimalParameters (StrategyId, MarketRegime, ParametersJson, ExpectedSharpe, ExpectedWinRate, ExpectedDrawdown, BasedOnBacktests, ConfidenceScore, IsActive, ValidFrom, ValidUntil)
    VALUES 
    (1, 'BULLISH', '{"stopLoss": 0.02, "takeProfit": 0.05, "positionSize": 0.15}', 1.85, 0.65, 0.12, 50, 0.88, 1, GETDATE(), DATEADD(month, 1, GETDATE())),
    (1, 'BEARISH', '{"stopLoss": 0.015, "takeProfit": 0.03, "positionSize": 0.10}', 1.45, 0.58, 0.15, 45, 0.75, 1, GETDATE(), DATEADD(month, 1, GETDATE())),
    (1, 'RANGING', '{"stopLoss": 0.025, "takeProfit": 0.04, "positionSize": 0.08}', 1.20, 0.52, 0.10, 40, 0.68, 1, GETDATE(), DATEADD(month, 1, GETDATE())),
    (1, 'VOLATILE', '{"stopLoss": 0.03, "takeProfit": 0.06, "positionSize": 0.05}', 1.10, 0.50, 0.18, 35, 0.62, 1, GETDATE(), DATEADD(month, 1, GETDATE())),
    (2, 'BULLISH', '{"rsiThreshold": 30, "emaPeriod": 20, "atrMultiplier": 1.5}', 2.05, 0.70, 0.08, 60, 0.92, 1, GETDATE(), DATEADD(month, 1, GETDATE()));
    
    PRINT '  Inserted 5 optimal parameter sets';
    
    -- =========================================================================
    -- 8. PARAMETER PERFORMANCE - Historical parameter performance
    -- =========================================================================
    PRINT 'Creating Parameter Performance...';
    
    INSERT INTO dbo.ParameterPerformance (StrategyId, ParamName, ParamValue, MarketRegime, SampleCount, AvgSharpeRatio, AvgWinRate, AvgProfitFactor, AvgMaxDrawdown, AvgReturn, BestSharpe, WorstSharpe, BestReturn, WorstReturn, StdDevSharpe, ConfidenceScore, IsRecommended)
    VALUES 
    ('TQQQ_SCALP', 'StopLossPercent', '0.015', 'BULLISH', 45, 1.82, 65.5, 1.45, 3.2, 25.50, 2.1, 1.5, 35.0, 15.0, 0.18, 0.85, 1),
    ('TQQQ_SCALP', 'StopLossPercent', '0.020', 'BULLISH', 52, 1.65, 62.0, 1.35, 4.1, 22.10, 1.9, 1.3, 30.0, 12.0, 0.22, 0.78, 1),
    ('TQQQ_SCALP', 'StopLossPercent', '0.025', 'BULLISH', 38, 1.42, 58.5, 1.20, 5.5, 18.75, 1.7, 1.1, 25.0, 10.0, 0.25, 0.65, 0),
    ('TQQQ_SCALP', 'TakeProfitPercent', '0.03', 'BULLISH', 42, 1.95, 68.0, 1.55, 2.8, 28.50, 2.3, 1.6, 38.0, 18.0, 0.15, 0.90, 1),
    ('TQQQ_SCALP', 'TakeProfitPercent', '0.04', 'BULLISH', 55, 1.78, 60.5, 1.40, 3.5, 32.10, 2.0, 1.4, 42.0, 20.0, 0.20, 0.82, 1),
    ('TQQQ_SCALP', 'RSIThreshold', '25', 'BULLISH', 48, 2.05, 70.0, 1.65, 2.5, 35.50, 2.5, 1.7, 45.0, 22.0, 0.12, 0.92, 1),
    ('TQQQ_SCALP', 'RSIThreshold', '30', 'BULLISH', 62, 1.88, 65.0, 1.48, 3.2, 28.80, 2.2, 1.5, 38.0, 18.0, 0.18, 0.85, 1),
    ('TQQQ_SCALP', 'RSIThreshold', '35', 'BULLISH', 75, 1.52, 58.0, 1.25, 4.5, 22.50, 1.8, 1.2, 30.0, 12.0, 0.25, 0.72, 0),
    ('TQQQ_SCALP', 'RSIThreshold', '25', 'VOLATILE', 25, 0.85, 52.0, 1.05, 8.5, 15.20, 1.2, 0.5, 25.0, 5.0, 0.35, 0.55, 0),
    ('TQQQ_SCALP', 'RSIThreshold', '30', 'VOLATILE', 32, 0.65, 48.5, 0.95, 10.2, 8.50, 1.0, 0.3, 18.0, -2.0, 0.40, 0.45, 0);
    
    PRINT '  Inserted 10 parameter performance records';
    
    -- =========================================================================
    -- 9. BACKTEST RUNS - Backtest execution history
    -- =========================================================================
    PRINT 'Creating Backtest Runs...';
    
    INSERT INTO dbo.BacktestRuns (RunID, StartTime, EndTime, Status, AlgorithmName, BacktestStartDate, BacktestEndDate, InitialCapital)
    VALUES 
    ('RUN-001', DATEADD(day, -7, GETDATE()), DATEADD(day, -7, DATEADD(hour, 2, GETDATE())), 'Completed', 'TQQQScalpingAlgorithm', '2025-01-01', '2025-12-31', 100000.00),
    ('RUN-002', DATEADD(day, -5, GETDATE()), DATEADD(day, -5, DATEADD(hour, 1, GETDATE())), 'Completed', 'TQQQScalpingAlgorithm', '2025-06-01', '2025-12-31', 100000.00),
    ('RUN-003', DATEADD(day, -3, GETDATE()), DATEADD(day, -3, DATEADD(minute, 45, GETDATE())), 'Completed', 'TQQQScalpingAlgorithm', '2025-10-01', '2025-12-31', 50000.00),
    ('RUN-004', DATEADD(day, -2, GETDATE()), DATEADD(day, -2, DATEADD(hour, 3, GETDATE())), 'Completed', 'TQQQScalpingAlgorithm', '2025-11-01', '2025-12-31', 100000.00),
    ('RUN-005', DATEADD(hour, -12, GETDATE()), DATEADD(hour, -10, GETDATE()), 'Completed', 'TQQQScalpingAlgorithm', '2025-12-01', '2025-12-31', 100000.00),
    ('RUN-006', DATEADD(hour, -2, GETDATE()), NULL, 'Running', 'TQQQScalpingAlgorithm', '2025-01-01', '2026-01-12', 100000.00),
    ('RUN-007', DATEADD(day, -10, GETDATE()), DATEADD(day, -10, DATEADD(hour, 1, GETDATE())), 'Failed', 'TQQQScalpingAlgorithm', '2024-01-01', '2024-12-31', 100000.00);
    
    PRINT '  Inserted 7 backtest runs';
    
    -- =========================================================================
    -- 10. BACKTEST METRICS - Backtest performance metrics
    -- =========================================================================
    PRINT 'Creating Backtest Metrics...';
    
    INSERT INTO dbo.BacktestMetrics (RunID, MetricName, MetricValue)
    VALUES 
    ('RUN-001', 'TotalReturn', 15.42),
    ('RUN-001', 'SharpeRatio', 1.85),
    ('RUN-001', 'MaxDrawdown', -8.5),
    ('RUN-001', 'WinRate', 62.5),
    ('RUN-001', 'TotalTrades', 156),
    ('RUN-002', 'TotalReturn', 12.18),
    ('RUN-002', 'SharpeRatio', 1.62),
    ('RUN-002', 'MaxDrawdown', -6.2),
    ('RUN-002', 'WinRate', 58.3),
    ('RUN-003', 'TotalReturn', 8.75),
    ('RUN-003', 'SharpeRatio', 1.45),
    ('RUN-003', 'MaxDrawdown', -5.1),
    ('RUN-003', 'WinRate', 55.0),
    ('RUN-004', 'TotalReturn', 6.22),
    ('RUN-004', 'SharpeRatio', 1.35),
    ('RUN-004', 'MaxDrawdown', -4.8),
    ('RUN-004', 'WinRate', 57.5),
    ('RUN-005', 'TotalReturn', 3.85),
    ('RUN-005', 'SharpeRatio', 1.55),
    ('RUN-005', 'MaxDrawdown', -3.2),
    ('RUN-005', 'WinRate', 60.0);
    
    PRINT '  Inserted 21 backtest metrics';
    
    -- =========================================================================
    -- 11. OPTIMAL PARAMETER VALUES - Detailed parameter recommendations
    -- =========================================================================
    PRINT 'Creating Optimal Parameter Values...';
    
    INSERT INTO dbo.OptimalParameterValues (StrategyId, ParamName, MarketRegime, OptimalValue, ConfidenceScore, SampleSize, ExpectedSharpe, ExpectedReturn, ExpectedDrawdown)
    VALUES 
    ('TQQQ_SCALPING', 'rsi_oversold', 'TRENDING_UP', '28', 0.70, 50, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'stop_loss_pct', 'TRENDING_UP', '0.02', 0.70, 50, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'take_profit_pct', 'TRENDING_UP', '0.02', 0.70, 50, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'rsi_overbought', 'TRENDING_DOWN', '72', 0.70, 50, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'stop_loss_pct', 'TRENDING_DOWN', '0.015', 0.65, 40, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'take_profit_pct', 'TRENDING_DOWN', '0.012', 0.65, 40, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'rsi_oversold', 'MEAN_REVERTING', '32', 0.60, 30, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'rsi_overbought', 'MEAN_REVERTING', '68', 0.60, 30, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'take_profit_pct', 'MEAN_REVERTING', '0.01', 0.60, 30, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'stop_loss_pct', 'VOLATILE', '0.025', 0.75, 60, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'position_size_level1', 'VOLATILE', '0.35', 0.75, 60, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'rsi_oversold', 'ALL', '30', 0.50, 100, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'rsi_overbought', 'ALL', '70', 0.50, 100, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'stop_loss_pct', 'ALL', '0.02', 0.50, 100, NULL, NULL, NULL),
    ('TQQQ_SCALPING', 'take_profit_pct', 'ALL', '0.015', 0.50, 100, NULL, NULL, NULL);
    
    PRINT '  Inserted 15 optimal parameter values';
    
    -- =========================================================================
    -- 12. PARAMETERS - Algorithm parameters
    -- =========================================================================
    PRINT 'Creating Parameters...';
    
    INSERT INTO dbo.Parameters (AlgorithmName, ParamName, ParamValue, ParamType, IsActive)
    VALUES 
    ('TQQQScalpingAlgorithm', 'rsi_period', '14', 'int', 1),
    ('TQQQScalpingAlgorithm', 'rsi_oversold', '30', 'int', 1),
    ('TQQQScalpingAlgorithm', 'rsi_overbought', '70', 'int', 1),
    ('TQQQScalpingAlgorithm', 'ema_fast', '9', 'int', 1),
    ('TQQQScalpingAlgorithm', 'ema_slow', '21', 'int', 1),
    ('TQQQScalpingAlgorithm', 'stop_loss_pct', '0.02', 'float', 1),
    ('TQQQScalpingAlgorithm', 'take_profit_pct', '0.04', 'float', 1),
    ('TQQQScalpingAlgorithm', 'max_position_size', '0.15', 'float', 1),
    ('TQQQScalpingAlgorithm', 'atr_period', '14', 'int', 1),
    ('TQQQScalpingAlgorithm', 'atr_multiplier', '1.5', 'float', 1),
    ('TQQQScalpingAlgorithm', 'trade_start_hour', '9', 'int', 1),
    ('TQQQScalpingAlgorithm', 'trade_end_hour', '15', 'int', 1),
    ('TQQQScalpingAlgorithm', 'min_volume', '1000000', 'int', 1),
    ('TQQQScalpingAlgorithm', 'enable_shorting', 'true', 'bool', 1),
    ('TQQQScalpingAlgorithm', 'use_trailing_stop', 'false', 'bool', 1);
    
    PRINT '  Inserted 15 parameters';
    
    -- =========================================================================
    -- 13. STRATEGY PARAMETERS - Detailed strategy configuration
    -- =========================================================================
    PRINT 'Creating Strategy Parameters...';
    
    INSERT INTO dbo.StrategyParameters (StrategyId, ParamName, ParamValue, ParamType, Description, Category, MinValue, MaxValue, DefaultValue, IsActive, UpdatedBy)
    VALUES 
    ('TQQQ_SCALP', 'rsi_period', '14', 'int', 'RSI calculation period', 'Indicators', '5', '30', '14', 1, 'system'),
    ('TQQQ_SCALP', 'rsi_oversold', '30', 'int', 'RSI oversold threshold for entry', 'Entry', '20', '40', '30', 1, 'system'),
    ('TQQQ_SCALP', 'rsi_overbought', '70', 'int', 'RSI overbought threshold for exit', 'Exit', '60', '80', '70', 1, 'system'),
    ('TQQQ_SCALP', 'ema_fast_period', '9', 'int', 'Fast EMA period', 'Indicators', '5', '20', '9', 1, 'system'),
    ('TQQQ_SCALP', 'ema_slow_period', '21', 'int', 'Slow EMA period', 'Indicators', '15', '50', '21', 1, 'system'),
    ('TQQQ_SCALP', 'stop_loss_pct', '0.02', 'float', 'Stop loss percentage', 'RiskManagement', '0.01', '0.05', '0.02', 1, 'system'),
    ('TQQQ_SCALP', 'take_profit_pct', '0.04', 'float', 'Take profit percentage', 'RiskManagement', '0.02', '0.10', '0.04', 1, 'system'),
    ('TQQQ_SCALP', 'max_position_pct', '0.15', 'float', 'Maximum position as % of portfolio', 'RiskManagement', '0.05', '0.25', '0.15', 1, 'system'),
    ('TQQQ_SCALP', 'atr_period', '14', 'int', 'ATR calculation period', 'Indicators', '7', '21', '14', 1, 'system'),
    ('TQQQ_SCALP', 'atr_multiplier', '1.5', 'float', 'ATR multiplier for volatility adjustment', 'RiskManagement', '1.0', '3.0', '1.5', 1, 'system'),
    ('TQQQ_SCALP', 'trade_start_hour', '9', 'int', 'Trading start hour (EST)', 'Schedule', '9', '10', '9', 1, 'system'),
    ('TQQQ_SCALP', 'trade_end_hour', '15', 'int', 'Trading end hour (EST)', 'Schedule', '14', '16', '15', 1, 'system'),
    ('TQQQ_SCALP', 'min_volume', '1000000', 'int', 'Minimum daily volume required', 'Filters', '500000', '5000000', '1000000', 1, 'system'),
    ('TQQQ_SCALP', 'max_spread_pct', '0.001', 'float', 'Maximum bid-ask spread percentage', 'Filters', '0.0005', '0.005', '0.001', 1, 'system'),
    ('TQQQ_SCALP', 'enable_shorting', 'true', 'bool', 'Enable short positions with SQQQ', 'Trading', 'false', 'true', 'true', 1, 'system');
    
    PRINT '  Inserted 15 strategy parameters';
    
    -- =========================================================================
    -- 14. SYSTEM CONFIG - System configuration settings
    -- =========================================================================
    PRINT 'Creating System Config...';
    
    INSERT INTO dbo.SystemConfig (ConfigKey, ConfigValue, ConfigType, Description, IsEncrypted, UpdatedBy)
    VALUES 
    ('trading.enabled', 'true', 'bool', 'Enable/disable trading system', 0, 'system'),
    ('trading.mode', 'paper', 'string', 'Trading mode: backtest, paper, live', 0, 'system'),
    ('trading.max_daily_loss', '500', 'decimal', 'Maximum daily loss before stopping', 0, 'system'),
    ('trading.max_daily_trades', '20', 'int', 'Maximum trades per day', 0, 'system'),
    ('alpaca.api_key', '***ENCRYPTED***', 'string', 'Alpaca API key', 1, 'system'),
    ('alpaca.api_secret', '***ENCRYPTED***', 'string', 'Alpaca API secret', 1, 'system'),
    ('alpaca.base_url', 'https://paper-api.alpaca.markets', 'string', 'Alpaca API base URL', 0, 'system'),
    ('dashboard.refresh_interval', '30', 'int', 'Dashboard refresh interval in seconds', 0, 'system'),
    ('dashboard.default_days', '30', 'int', 'Default days to show in dashboard', 0, 'system'),
    ('alerts.email_enabled', 'false', 'bool', 'Enable email alerts', 0, 'system'),
    ('alerts.slack_enabled', 'false', 'bool', 'Enable Slack alerts', 0, 'system'),
    ('logging.level', 'INFO', 'string', 'Logging level: DEBUG, INFO, WARNING, ERROR', 0, 'system');
    
    PRINT '  Inserted 12 system config entries';
    
    PRINT '';
    PRINT 'INSERT COMPLETE';
    PRINT '';
END
GO

-- ============================================================================
-- SUMMARY REPORT
-- ============================================================================
PRINT '============================================';
PRINT 'SAMPLE DATA SUMMARY';
PRINT '============================================';

SELECT 'Sessions' as TableName, COUNT(*) as Rows FROM dbo.Sessions
UNION ALL SELECT 'Trades', COUNT(*) FROM dbo.Trades
UNION ALL SELECT 'DailyPerformance', COUNT(*) FROM dbo.DailyPerformance
UNION ALL SELECT 'MarketRegimes', COUNT(*) FROM dbo.MarketRegimes
UNION ALL SELECT 'LearningStore', COUNT(*) FROM dbo.LearningStore
UNION ALL SELECT 'AuditLog', COUNT(*) FROM dbo.AuditLog
UNION ALL SELECT 'OptimalParameters', COUNT(*) FROM dbo.OptimalParameters
UNION ALL SELECT 'OptimalParameterValues', COUNT(*) FROM dbo.OptimalParameterValues
UNION ALL SELECT 'ParameterPerformance', COUNT(*) FROM dbo.ParameterPerformance
UNION ALL SELECT 'Parameters', COUNT(*) FROM dbo.Parameters
UNION ALL SELECT 'StrategyParameters', COUNT(*) FROM dbo.StrategyParameters
UNION ALL SELECT 'SystemConfig', COUNT(*) FROM dbo.SystemConfig
UNION ALL SELECT 'BacktestRuns', COUNT(*) FROM dbo.BacktestRuns
UNION ALL SELECT 'BacktestMetrics', COUNT(*) FROM dbo.BacktestMetrics;

GO
