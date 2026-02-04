-- ============================================
-- Webhook Events Schema for Backtest Runner UI
-- ============================================
-- This schema stores webhook events that are triggered during backtests,
-- allowing the dashboard to display real-time webhook activity.

-- Drop if exists for clean migration
IF OBJECT_ID('dbo.WebhookEvents', 'U') IS NOT NULL
    DROP TABLE dbo.WebhookEvents;
GO

-- Create WebhookEvents table
CREATE TABLE dbo.WebhookEvents (
    EventId INT IDENTITY(1,1) PRIMARY KEY,
    SessionId VARCHAR(50) NOT NULL,
    Timestamp DATETIME2 NOT NULL DEFAULT GETDATE(),
    WebhookType VARCHAR(50) NOT NULL,  -- SCHEDULED, SIGNAL, ALERT, STATUS
    Symbol VARCHAR(20) NOT NULL,
    TriggerReason NVARCHAR(500),
    Price DECIMAL(18,6),
    MarketData NVARCHAR(MAX),  -- JSON with RSI, VWAP, BB values, etc.
    Conditions NVARCHAR(MAX),  -- JSON with trigger conditions
    CreatedAt DATETIME2 NOT NULL DEFAULT GETDATE(),
    
    -- Index for fast session lookups
    INDEX IX_WebhookEvents_SessionId (SessionId),
    INDEX IX_WebhookEvents_Timestamp (Timestamp DESC),
    INDEX IX_WebhookEvents_Type (WebhookType)
);
GO

-- Add foreign key to Sessions table if it exists
IF OBJECT_ID('dbo.Sessions', 'U') IS NOT NULL
BEGIN
    ALTER TABLE dbo.WebhookEvents
    ADD CONSTRAINT FK_WebhookEvents_Sessions
    FOREIGN KEY (SessionId) REFERENCES dbo.Sessions(SessionId);
END
GO

-- Create view for webhook event summaries by session
CREATE OR ALTER VIEW dbo.vw_WebhookEventSummary AS
SELECT 
    SessionId,
    COUNT(*) as TotalEvents,
    SUM(CASE WHEN WebhookType = 'SCHEDULED' THEN 1 ELSE 0 END) as ScheduledCount,
    SUM(CASE WHEN WebhookType = 'SIGNAL' THEN 1 ELSE 0 END) as SignalCount,
    SUM(CASE WHEN WebhookType = 'ALERT' THEN 1 ELSE 0 END) as AlertCount,
    SUM(CASE WHEN WebhookType = 'STATUS' THEN 1 ELSE 0 END) as StatusCount,
    MIN(Timestamp) as FirstEvent,
    MAX(Timestamp) as LastEvent
FROM dbo.WebhookEvents
GROUP BY SessionId;
GO

-- Stored procedure to insert webhook event
CREATE OR ALTER PROCEDURE dbo.sp_InsertWebhookEvent
    @SessionId VARCHAR(50),
    @WebhookType VARCHAR(50),
    @Symbol VARCHAR(20),
    @TriggerReason NVARCHAR(500),
    @Price DECIMAL(18,6),
    @MarketData NVARCHAR(MAX) = NULL,
    @Conditions NVARCHAR(MAX) = NULL,
    @Timestamp DATETIME2 = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    INSERT INTO dbo.WebhookEvents (
        SessionId, Timestamp, WebhookType, Symbol, 
        TriggerReason, Price, MarketData, Conditions
    )
    VALUES (
        @SessionId, 
        ISNULL(@Timestamp, GETDATE()), 
        @WebhookType, 
        @Symbol, 
        @TriggerReason, 
        @Price, 
        @MarketData, 
        @Conditions
    );
    
    SELECT SCOPE_IDENTITY() as EventId;
END
GO

-- Stored procedure to get webhook events for a session
CREATE OR ALTER PROCEDURE dbo.sp_GetWebhookEvents
    @SessionId VARCHAR(50),
    @WebhookType VARCHAR(50) = NULL,
    @Limit INT = 100
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT TOP (@Limit)
        EventId,
        SessionId,
        Timestamp,
        WebhookType,
        Symbol,
        TriggerReason,
        Price,
        MarketData,
        Conditions
    FROM dbo.WebhookEvents
    WHERE SessionId = @SessionId
        AND (@WebhookType IS NULL OR WebhookType = @WebhookType)
    ORDER BY Timestamp DESC;
END
GO

PRINT 'Webhook Events schema created successfully.';
