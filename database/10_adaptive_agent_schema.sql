-- ============================================
-- Adaptive Agent Schema
-- Tables for agent state, decisions, and audit
-- ============================================

-- Agent Actions (audit log of all agent activities)
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'AgentActions') AND type = 'U')
CREATE TABLE AgentActions (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    ActionId NVARCHAR(50) UNIQUE,
    ActionType NVARCHAR(50) NOT NULL,
    ParameterName NVARCHAR(100),
    OldValue NVARCHAR(MAX),
    NewValue NVARCHAR(MAX),
    Description NVARCHAR(MAX),
    Executed BIT NOT NULL DEFAULT 0,
    ExecutedAt DATETIME,
    Confidence FLOAT,
    Reasoning NVARCHAR(MAX),
    PatternIds NVARCHAR(MAX),
    CreatedAt DATETIME NOT NULL DEFAULT GETDATE()
);
GO

-- Agent Decisions (full decision records with context)
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'AgentDecisions') AND type = 'U')
CREATE TABLE AgentDecisions (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    DecisionId NVARCHAR(50) UNIQUE NOT NULL,
    DecisionType NVARCHAR(50) NOT NULL,
    Action NVARCHAR(100) NOT NULL,
    Confidence FLOAT NOT NULL,
    ParameterName NVARCHAR(100),
    OldValue NVARCHAR(MAX),
    NewValue NVARCHAR(MAX),
    Reasoning NVARCHAR(MAX),
    SupportingPatterns NVARCHAR(MAX),
    ContributingFactors NVARCHAR(MAX),
    MarketSnapshot NVARCHAR(MAX),
    PerformanceSnapshot NVARCHAR(MAX),
    Executed BIT NOT NULL DEFAULT 0,
    ExecutedAt DATETIME,
    ExecutionResult NVARCHAR(500),
    OutcomeRecorded BIT DEFAULT 0,
    Outcome NVARCHAR(500),
    CreatedAt DATETIME NOT NULL DEFAULT GETDATE()
);
GO

-- Agent State (current and historical state)
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'AgentState') AND type = 'U')
CREATE TABLE AgentState (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    AgentId NVARCHAR(50) NOT NULL,
    Mode NVARCHAR(20) NOT NULL,
    IsRunning BIT NOT NULL DEFAULT 0,
    IsPaused BIT NOT NULL DEFAULT 0,
    TradingEnabled BIT NOT NULL DEFAULT 1,
    EmergencyStopActive BIT NOT NULL DEFAULT 0,
    EmergencyStopReason NVARCHAR(500),
    CurrentRegime NVARCHAR(50),
    CyclesCompleted INT DEFAULT 0,
    DecisionsMade INT DEFAULT 0,
    DecisionsExecuted INT DEFAULT 0,
    ParameterChangesToday INT DEFAULT 0,
    StartedAt DATETIME,
    LastCycleAt DATETIME,
    RecordedAt DATETIME NOT NULL DEFAULT GETDATE()
);
GO

-- Agent Alerts
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'AgentAlerts') AND type = 'U')
CREATE TABLE AgentAlerts (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    AlertId NVARCHAR(50) UNIQUE,
    Severity NVARCHAR(20) NOT NULL,
    Category NVARCHAR(50) NOT NULL,
    Message NVARCHAR(MAX) NOT NULL,
    RelatedDecisionId NVARCHAR(50),
    Data NVARCHAR(MAX),
    Notified BIT DEFAULT 0,
    NotifiedAt DATETIME,
    Acknowledged BIT DEFAULT 0,
    AcknowledgedAt DATETIME,
    AcknowledgedBy NVARCHAR(100),
    CreatedAt DATETIME NOT NULL DEFAULT GETDATE()
);
GO

-- Indexes for performance (only create if not exists)
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AgentActions_ActionType' AND object_id = OBJECT_ID('AgentActions'))
    CREATE INDEX IX_AgentActions_ActionType ON AgentActions(ActionType);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AgentActions_ExecutedAt' AND object_id = OBJECT_ID('AgentActions'))
    CREATE INDEX IX_AgentActions_ExecutedAt ON AgentActions(ExecutedAt);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AgentDecisions_DecisionType' AND object_id = OBJECT_ID('AgentDecisions'))
    CREATE INDEX IX_AgentDecisions_DecisionType ON AgentDecisions(DecisionType);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AgentDecisions_CreatedAt' AND object_id = OBJECT_ID('AgentDecisions'))
    CREATE INDEX IX_AgentDecisions_CreatedAt ON AgentDecisions(CreatedAt);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AgentAlerts_Severity' AND object_id = OBJECT_ID('AgentAlerts'))
    CREATE INDEX IX_AgentAlerts_Severity ON AgentAlerts(Severity);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AgentAlerts_Acknowledged' AND object_id = OBJECT_ID('AgentAlerts'))
    CREATE INDEX IX_AgentAlerts_Acknowledged ON AgentAlerts(Acknowledged);
GO

-- ============================================
-- Views
-- ============================================

-- Recent Agent Activity
CREATE OR ALTER VIEW vw_RecentAgentActivity AS
SELECT TOP 100
    d.DecisionId,
    d.DecisionType,
    d.Action,
    d.Confidence,
    d.ParameterName,
    d.OldValue,
    d.NewValue,
    d.Reasoning,
    d.Executed,
    d.ExecutionResult,
    d.CreatedAt
FROM AgentDecisions d
ORDER BY d.CreatedAt DESC;
GO

-- Agent Decision Statistics
CREATE OR ALTER VIEW vw_AgentDecisionStats AS
SELECT 
    DecisionType,
    COUNT(*) as TotalDecisions,
    SUM(CASE WHEN Executed = 1 THEN 1 ELSE 0 END) as ExecutedDecisions,
    AVG(Confidence) as AvgConfidence,
    MIN(CreatedAt) as FirstDecision,
    MAX(CreatedAt) as LastDecision
FROM AgentDecisions
GROUP BY DecisionType;
GO

-- Pending Alerts
CREATE OR ALTER VIEW vw_PendingAlerts AS
SELECT TOP 1000
    AlertId,
    Severity,
    Category,
    Message,
    RelatedDecisionId,
    CreatedAt
FROM AgentAlerts
WHERE Acknowledged = 0
ORDER BY 
    CASE Severity 
        WHEN 'critical' THEN 1 
        WHEN 'warning' THEN 2 
        ELSE 3 
    END,
    CreatedAt DESC;
GO

-- ============================================
-- Stored Procedures
-- ============================================

-- Get Agent Summary
CREATE OR ALTER PROCEDURE sp_GetAgentSummary
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Latest state
    SELECT TOP 1 *
    FROM AgentState
    ORDER BY RecordedAt DESC;
    
    -- Today's activity
    SELECT 
        COUNT(*) as DecisionsToday,
        SUM(CASE WHEN Executed = 1 THEN 1 ELSE 0 END) as ExecutedToday,
        SUM(CASE WHEN DecisionType = 'PARAMETER_ADJUSTMENT' AND Executed = 1 THEN 1 ELSE 0 END) as ParamChangesToday,
        AVG(Confidence) as AvgConfidenceToday
    FROM AgentDecisions
    WHERE CAST(CreatedAt AS DATE) = CAST(GETDATE() AS DATE);
    
    -- Pending alerts count
    SELECT 
        Severity,
        COUNT(*) as Count
    FROM AgentAlerts
    WHERE Acknowledged = 0
    GROUP BY Severity;
END;
GO

-- Record Agent State
CREATE OR ALTER PROCEDURE sp_RecordAgentState
    @AgentId NVARCHAR(50),
    @Mode NVARCHAR(20),
    @IsRunning BIT,
    @IsPaused BIT,
    @TradingEnabled BIT,
    @EmergencyStopActive BIT,
    @EmergencyStopReason NVARCHAR(500) = NULL,
    @CurrentRegime NVARCHAR(50) = NULL,
    @CyclesCompleted INT = 0,
    @DecisionsMade INT = 0,
    @DecisionsExecuted INT = 0,
    @ParameterChangesToday INT = 0
AS
BEGIN
    SET NOCOUNT ON;
    
    INSERT INTO AgentState (
        AgentId, Mode, IsRunning, IsPaused, TradingEnabled,
        EmergencyStopActive, EmergencyStopReason, CurrentRegime,
        CyclesCompleted, DecisionsMade, DecisionsExecuted,
        ParameterChangesToday, StartedAt, LastCycleAt
    ) VALUES (
        @AgentId, @Mode, @IsRunning, @IsPaused, @TradingEnabled,
        @EmergencyStopActive, @EmergencyStopReason, @CurrentRegime,
        @CyclesCompleted, @DecisionsMade, @DecisionsExecuted,
        @ParameterChangesToday, GETDATE(), GETDATE()
    );
END;
GO

-- Acknowledge Alert
CREATE OR ALTER PROCEDURE sp_AcknowledgeAlert
    @AlertId NVARCHAR(50),
    @AcknowledgedBy NVARCHAR(100) = 'System'
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE AgentAlerts
    SET 
        Acknowledged = 1,
        AcknowledgedAt = GETDATE(),
        AcknowledgedBy = @AcknowledgedBy
    WHERE AlertId = @AlertId;
END;
GO

-- Get Decision Effectiveness
CREATE OR ALTER PROCEDURE sp_GetDecisionEffectiveness
    @DaysBack INT = 30
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        DecisionType,
        Action,
        COUNT(*) as TotalDecisions,
        SUM(CASE WHEN Executed = 1 THEN 1 ELSE 0 END) as ExecutedCount,
        SUM(CASE WHEN OutcomeRecorded = 1 AND Outcome = 'POSITIVE' THEN 1 ELSE 0 END) as PositiveOutcomes,
        SUM(CASE WHEN OutcomeRecorded = 1 AND Outcome = 'NEGATIVE' THEN 1 ELSE 0 END) as NegativeOutcomes,
        AVG(Confidence) as AvgConfidence,
        AVG(CASE 
            WHEN OutcomeRecorded = 1 AND Outcome = 'POSITIVE' THEN 1.0 
            WHEN OutcomeRecorded = 1 AND Outcome = 'NEGATIVE' THEN 0.0 
            ELSE NULL 
        END) as SuccessRate
    FROM AgentDecisions
    WHERE CreatedAt >= DATEADD(day, -@DaysBack, GETDATE())
    GROUP BY DecisionType, Action
    ORDER BY TotalDecisions DESC;
END;
GO

-- Record Decision Outcome
CREATE OR ALTER PROCEDURE sp_RecordDecisionOutcome
    @DecisionId NVARCHAR(50),
    @Outcome NVARCHAR(500)
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE AgentDecisions
    SET 
        OutcomeRecorded = 1,
        Outcome = @Outcome
    WHERE DecisionId = @DecisionId;
END;
GO

PRINT 'Adaptive Agent schema created successfully';
GO
