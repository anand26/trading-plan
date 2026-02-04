-- ============================================
-- Webhook Trading Schema Updates
-- ============================================
-- Updates to support TradingView webhook trading
-- Run after existing schema files
-- Execute with: sqlcmd -S localhost -E -d TradingDB -i 15_webhook_trading_schema.sql
-- ============================================

USE TradingDB;
GO

PRINT 'Applying webhook trading schema updates...';
GO

-- ============================================
-- 1. UPDATE SESSIONS TABLE
-- ============================================
-- Add default for Status column if not present
IF NOT EXISTS (
    SELECT 1 FROM sys.default_constraints 
    WHERE parent_object_id = OBJECT_ID('Sessions') 
    AND COL_NAME(parent_object_id, parent_column_id) = 'Status'
)
BEGIN
    ALTER TABLE Sessions ADD CONSTRAINT DF_Sessions_Status DEFAULT 'active' FOR Status;
    PRINT 'Added default constraint for Sessions.Status';
END
GO

-- ============================================
-- 2. UPDATE WEBHOOKEVENTS TABLE
-- ============================================
-- Make SessionId nullable for webhook events that don't have a session yet
IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'WebhookEvents' AND COLUMN_NAME = 'SessionId' AND IS_NULLABLE = 'NO')
BEGIN
    -- Drop existing FK constraint if present
    IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_WebhookEvents_Sessions')
    BEGIN
        ALTER TABLE WebhookEvents DROP CONSTRAINT FK_WebhookEvents_Sessions;
        PRINT 'Dropped FK_WebhookEvents_Sessions';
    END
    
    -- Make SessionId nullable
    ALTER TABLE WebhookEvents ALTER COLUMN SessionId VARCHAR(50) NULL;
    PRINT 'Made WebhookEvents.SessionId nullable';
END
GO

-- ============================================
-- 3. UPDATE SIGNALS TABLE
-- ============================================
-- Ensure ExecutedOrderId is VARCHAR to store Alpaca order IDs
IF EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'Signals' AND COLUMN_NAME = 'ExecutedOrderId' AND DATA_TYPE = 'bigint'
)
BEGIN
    -- Drop the FK constraint first
    IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Signals_Orders')
    BEGIN
        ALTER TABLE Signals DROP CONSTRAINT FK_Signals_Orders;
        PRINT 'Dropped FK_Signals_Orders constraint';
    END
    
    -- Change to VARCHAR to store Alpaca order IDs (UUIDs)
    ALTER TABLE Signals ALTER COLUMN ExecutedOrderId VARCHAR(100) NULL;
    PRINT 'Changed Signals.ExecutedOrderId to VARCHAR(100)';
END
GO

-- ============================================
-- 4. CREATE WEBHOOK-SPECIFIC INDEXES
-- ============================================
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Sessions_StrategyId_Status')
BEGIN
    CREATE INDEX IX_Sessions_StrategyId_Status ON Sessions(StrategyId, Status);
    PRINT 'Created index IX_Sessions_StrategyId_Status';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Orders_Tag')
BEGIN
    CREATE INDEX IX_Orders_Tag ON Orders(Tag);
    PRINT 'Created index IX_Orders_Tag';
END
GO

-- ============================================
-- 5. STORED PROCEDURES FOR WEBHOOK TRADING
-- ============================================

-- Get or create active webhook session
CREATE OR ALTER PROCEDURE dbo.sp_GetOrCreateWebhookSession
    @SessionType VARCHAR(20) = 'PAPER',
    @StrategyId VARCHAR(50) = 'TQQQ_SQQQ_PAIRS',
    @SessionId VARCHAR(50) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Try to get existing active session
    SELECT TOP 1 @SessionId = SessionId 
    FROM Sessions 
    WHERE SessionType = @SessionType 
      AND StrategyId = @StrategyId 
      AND Status = 'active'
    ORDER BY StartTime DESC;
    
    -- If no active session, create one
    IF @SessionId IS NULL
    BEGIN
        SET @SessionId = 'WH-' + CONVERT(VARCHAR(8), NEWID());
        
        INSERT INTO Sessions (SessionId, SessionType, StrategyId, StartTime, Status, Notes, CreatedAt)
        VALUES (
            @SessionId,
            @SessionType,
            @StrategyId,
            GETUTCDATE(),
            'active',
            'Auto-created by webhook server',
            GETUTCDATE()
        );
        
        PRINT 'Created new webhook session: ' + @SessionId;
    END
END
GO

-- Log webhook trade signal
CREATE OR ALTER PROCEDURE dbo.sp_LogWebhookSignal
    @Symbol VARCHAR(10),
    @Action VARCHAR(20),
    @Price DECIMAL(18, 4),
    @ZScore DECIMAL(10, 4) = NULL,
    @OrderId VARCHAR(100) = NULL,
    @SessionType VARCHAR(20) = 'PAPER'
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @SessionId VARCHAR(50);
    
    -- Get or create session
    EXEC dbo.sp_GetOrCreateWebhookSession 
        @SessionType = @SessionType, 
        @SessionId = @SessionId OUTPUT;
    
    -- Insert signal
    INSERT INTO Signals (
        Timestamp, Symbol, SignalType, Action, Strength, Price, 
        WasExecuted, ExecutedOrderId, SessionId, CreatedAt
    )
    VALUES (
        GETUTCDATE(),
        @Symbol,
        'WEBHOOK',
        @Action,
        @ZScore,
        @Price,
        CASE WHEN @OrderId IS NOT NULL THEN 1 ELSE 0 END,
        @OrderId,
        @SessionId,
        GETUTCDATE()
    );
    
    SELECT SCOPE_IDENTITY() AS SignalId, @SessionId AS SessionId;
END
GO

-- Log webhook order
CREATE OR ALTER PROCEDURE dbo.sp_LogWebhookOrder
    @ExternalOrderId VARCHAR(100),
    @Symbol VARCHAR(10),
    @Quantity DECIMAL(18, 8),
    @Price DECIMAL(18, 4),
    @Direction VARCHAR(10),
    @Action VARCHAR(50),
    @ZScore DECIMAL(10, 4) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    INSERT INTO Orders (
        ExternalOrderId, Symbol, Quantity, Price, OrderType, Direction,
        Status, SubmittedAt, Tag, CreatedAt
    )
    VALUES (
        @ExternalOrderId,
        @Symbol,
        @Quantity,
        @Price,
        'market',
        @Direction,
        'accepted',
        GETUTCDATE(),
        'Webhook: ' + @Action + ISNULL(', ZScore: ' + CAST(@ZScore AS VARCHAR), ''),
        GETUTCDATE()
    );
    
    SELECT SCOPE_IDENTITY() AS OrderId;
END
GO

-- Clean up webhook test data
CREATE OR ALTER PROCEDURE dbo.sp_CleanupWebhookTestData
AS
BEGIN
    SET NOCOUNT ON;
    
    BEGIN TRANSACTION;
    
    BEGIN TRY
        -- Get webhook session IDs
        DECLARE @SessionIds TABLE (SessionId VARCHAR(50));
        INSERT INTO @SessionIds
        SELECT SessionId FROM Sessions 
        WHERE SessionId LIKE 'WH-%' OR StrategyId = 'TQQQ_SQQQ_PAIRS';
        
        DECLARE @DeletedWebhooks INT, @DeletedSignals INT, @DeletedOrders INT, @DeletedSessions INT;
        
        -- Delete webhook events
        DELETE FROM WebhookEvents WHERE SessionId IN (SELECT SessionId FROM @SessionIds);
        SET @DeletedWebhooks = @@ROWCOUNT;
        
        -- Delete signals
        DELETE FROM Signals WHERE SessionId IN (SELECT SessionId FROM @SessionIds);
        SET @DeletedSignals = @@ROWCOUNT;
        
        -- Delete orders with webhook tag
        DELETE FROM Orders WHERE Tag LIKE '%Webhook%';
        SET @DeletedOrders = @@ROWCOUNT;
        
        -- Delete sessions
        DELETE FROM Sessions WHERE SessionId IN (SELECT SessionId FROM @SessionIds);
        SET @DeletedSessions = @@ROWCOUNT;
        
        COMMIT TRANSACTION;
        
        SELECT 
            @DeletedWebhooks AS DeletedWebhookEvents,
            @DeletedSignals AS DeletedSignals,
            @DeletedOrders AS DeletedOrders,
            @DeletedSessions AS DeletedSessions;
            
        PRINT 'Webhook test data cleanup completed.';
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END
GO

-- ============================================
-- 6. VIEW FOR WEBHOOK TRADING SUMMARY
-- ============================================
CREATE OR ALTER VIEW dbo.vw_WebhookTradingSummary AS
SELECT 
    s.SessionId,
    s.SessionType,
    s.StartTime,
    s.Status,
    COUNT(DISTINCT sig.SignalId) AS TotalSignals,
    SUM(CASE WHEN sig.WasExecuted = 1 THEN 1 ELSE 0 END) AS ExecutedSignals,
    COUNT(DISTINCT o.OrderId) AS TotalOrders,
    SUM(CASE WHEN sig.Action LIKE '%BUY%' THEN 1 ELSE 0 END) AS BuySignals,
    SUM(CASE WHEN sig.Action = 'EXIT' THEN 1 ELSE 0 END) AS ExitSignals,
    MIN(sig.Timestamp) AS FirstSignal,
    MAX(sig.Timestamp) AS LastSignal
FROM Sessions s
LEFT JOIN Signals sig ON s.SessionId = sig.SessionId
LEFT JOIN Orders o ON o.Tag LIKE '%Webhook%' AND o.SubmittedAt >= s.StartTime
WHERE s.StrategyId = 'TQQQ_SQQQ_PAIRS'
GROUP BY s.SessionId, s.SessionType, s.StartTime, s.Status;
GO

PRINT 'Webhook trading schema updates completed successfully.';
GO
