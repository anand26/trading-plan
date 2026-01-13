-- ============================================
-- Learning Store Extended Schema
-- Additional tables for pattern storage and recommendations
-- ============================================

USE TradingDB;
GO

-- ============================================
-- Patterns Table - Stores recognized trading patterns
-- ============================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.Patterns') AND type = 'U')
BEGIN
    CREATE TABLE dbo.Patterns (
        PatternID INT IDENTITY(1,1) PRIMARY KEY,
        PatternType NVARCHAR(50) NOT NULL,
        Name NVARCHAR(100) NOT NULL,
        Description NVARCHAR(500),
        Conditions NVARCHAR(MAX),  -- JSON
        ExpectedOutcome NVARCHAR(50),
        Confidence DECIMAL(5,4) NOT NULL DEFAULT 0.5,
        SampleSize INT NOT NULL DEFAULT 0,
        WinRate DECIMAL(5,4) NOT NULL DEFAULT 0.0,
        AvgPnL DECIMAL(18,4) NOT NULL DEFAULT 0.0,
        Regime NVARCHAR(50),
        CreatedAt DATETIME2 NOT NULL DEFAULT GETDATE(),
        UpdatedAt DATETIME2 NOT NULL DEFAULT GETDATE(),
        IsActive BIT NOT NULL DEFAULT 1,
        
        INDEX IX_Patterns_Type (PatternType),
        INDEX IX_Patterns_Regime (Regime),
        INDEX IX_Patterns_Confidence (Confidence DESC)
    );
    PRINT 'Created table: Patterns';
END
GO

-- ============================================
-- Recommendations Table - Parameter adjustment recommendations
-- ============================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.Recommendations') AND type = 'U')
BEGIN
    CREATE TABLE dbo.Recommendations (
        RecommendationID INT IDENTITY(1,1) PRIMARY KEY,
        ParameterName NVARCHAR(100) NOT NULL,
        CurrentValue NVARCHAR(200),
        RecommendedValue NVARCHAR(200) NOT NULL,
        Confidence DECIMAL(5,4) NOT NULL,
        ExpectedImprovement DECIMAL(5,4),
        Reasoning NVARCHAR(1000),
        SupportingPatterns NVARCHAR(MAX),  -- JSON array of pattern IDs
        Regime NVARCHAR(50),
        ValidUntil DATETIME2,
        CreatedAt DATETIME2 NOT NULL DEFAULT GETDATE(),
        Applied BIT NOT NULL DEFAULT 0,
        AppliedAt DATETIME2,
        Outcome NVARCHAR(200),
        
        INDEX IX_Recommendations_Parameter (ParameterName),
        INDEX IX_Recommendations_Applied (Applied),
        INDEX IX_Recommendations_Confidence (Confidence DESC)
    );
    PRINT 'Created table: Recommendations';
END
GO

-- ============================================
-- Extended LearningStore columns (if not exists)
-- ============================================
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.LearningStore') AND name = 'RelatedPatternID')
BEGIN
    ALTER TABLE dbo.LearningStore ADD RelatedPatternID INT NULL;
    PRINT 'Added column: LearningStore.RelatedPatternID';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.LearningStore') AND name = 'RelatedTradeID')
BEGIN
    ALTER TABLE dbo.LearningStore ADD RelatedTradeID INT NULL;
    PRINT 'Added column: LearningStore.RelatedTradeID';
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.LearningStore') AND name = 'Metadata')
BEGIN
    ALTER TABLE dbo.LearningStore ADD Metadata NVARCHAR(MAX) NULL;
    PRINT 'Added column: LearningStore.Metadata';
END
GO

-- ============================================
-- Pattern Analysis View
-- ============================================
IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_PatternAnalysis')
    DROP VIEW vw_PatternAnalysis;
GO

CREATE VIEW vw_PatternAnalysis AS
SELECT 
    p.PatternID,
    p.PatternType,
    p.Name,
    p.Confidence,
    p.SampleSize,
    p.WinRate,
    p.AvgPnL,
    p.Regime,
    p.IsActive,
    -- Performance Score
    p.WinRate * p.Confidence * 
        CASE WHEN p.SampleSize >= 50 THEN 1.0
             WHEN p.SampleSize >= 20 THEN 0.8
             WHEN p.SampleSize >= 10 THEN 0.6
             ELSE 0.4 END AS PerformanceScore,
    -- Age in days
    DATEDIFF(DAY, p.UpdatedAt, GETDATE()) AS DaysSinceUpdate,
    -- Recent trade count (last 7 days)
    (SELECT COUNT(*) FROM dbo.Trades t 
     WHERE t.EntryTime >= DATEADD(DAY, -7, GETDATE())) AS RecentTradeCount
FROM dbo.Patterns p
WHERE p.IsActive = 1;
GO

PRINT 'Created view: vw_PatternAnalysis';
GO

-- ============================================
-- Recommendation Effectiveness View
-- ============================================
IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_RecommendationEffectiveness')
    DROP VIEW vw_RecommendationEffectiveness;
GO

CREATE VIEW vw_RecommendationEffectiveness AS
SELECT 
    ParameterName,
    COUNT(*) AS TotalRecommendations,
    SUM(CASE WHEN Applied = 1 THEN 1 ELSE 0 END) AS AppliedCount,
    AVG(Confidence) AS AvgConfidence,
    AVG(ExpectedImprovement) AS AvgExpectedImprovement,
    -- Application rate
    CAST(SUM(CASE WHEN Applied = 1 THEN 1 ELSE 0 END) AS FLOAT) / 
        NULLIF(COUNT(*), 0) AS ApplicationRate
FROM dbo.Recommendations
WHERE CreatedAt >= DATEADD(DAY, -30, GETDATE())
GROUP BY ParameterName;
GO

PRINT 'Created view: vw_RecommendationEffectiveness';
GO

-- ============================================
-- Stored Procedure: Get Top Patterns
-- ============================================
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_GetTopPatterns')
    DROP PROCEDURE sp_GetTopPatterns;
GO

CREATE PROCEDURE sp_GetTopPatterns
    @PatternType NVARCHAR(50) = NULL,
    @Regime NVARCHAR(50) = NULL,
    @MinConfidence DECIMAL(5,4) = 0.3,
    @Limit INT = 10
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT TOP (@Limit)
        PatternID,
        PatternType,
        Name,
        Description,
        Conditions,
        ExpectedOutcome,
        Confidence,
        SampleSize,
        WinRate,
        AvgPnL,
        Regime,
        CreatedAt,
        UpdatedAt
    FROM dbo.Patterns
    WHERE IsActive = 1
      AND Confidence >= @MinConfidence
      AND (@PatternType IS NULL OR PatternType = @PatternType)
      AND (@Regime IS NULL OR Regime = @Regime OR Regime IS NULL)
    ORDER BY 
        WinRate * Confidence * 
        CASE WHEN SampleSize >= 50 THEN 1.0
             WHEN SampleSize >= 20 THEN 0.8
             ELSE 0.5 END DESC;
END
GO

PRINT 'Created procedure: sp_GetTopPatterns';
GO

-- ============================================
-- Stored Procedure: Get Active Recommendations
-- ============================================
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_GetActiveRecommendations')
    DROP PROCEDURE sp_GetActiveRecommendations;
GO

CREATE PROCEDURE sp_GetActiveRecommendations
    @ParameterName NVARCHAR(100) = NULL,
    @Regime NVARCHAR(50) = NULL,
    @MinConfidence DECIMAL(5,4) = 0.5
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        RecommendationID,
        ParameterName,
        CurrentValue,
        RecommendedValue,
        Confidence,
        ExpectedImprovement,
        Reasoning,
        SupportingPatterns,
        Regime,
        ValidUntil,
        CreatedAt
    FROM dbo.Recommendations
    WHERE Applied = 0
      AND (ValidUntil IS NULL OR ValidUntil > GETDATE())
      AND Confidence >= @MinConfidence
      AND (@ParameterName IS NULL OR ParameterName = @ParameterName)
      AND (@Regime IS NULL OR Regime = @Regime OR Regime IS NULL)
    ORDER BY Confidence DESC, ExpectedImprovement DESC;
END
GO

PRINT 'Created procedure: sp_GetActiveRecommendations';
GO

-- ============================================
-- Stored Procedure: Apply Recommendation
-- ============================================
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_ApplyRecommendation')
    DROP PROCEDURE sp_ApplyRecommendation;
GO

CREATE PROCEDURE sp_ApplyRecommendation
    @RecommendationID INT,
    @Outcome NVARCHAR(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE dbo.Recommendations
    SET Applied = 1,
        AppliedAt = GETDATE(),
        Outcome = @Outcome
    WHERE RecommendationID = @RecommendationID;
    
    -- Log the action using correct AuditLog columns
    INSERT INTO dbo.AuditLog (EventType, Severity, Source, Message)
    VALUES (
        'APPLY_RECOMMENDATION',
        'INFO',
        'LearningStore',
        CONCAT('Applied recommendation ID: ', @RecommendationID)
    );
    
    SELECT @@ROWCOUNT AS RowsAffected;
END
GO

PRINT 'Created procedure: sp_ApplyRecommendation';
GO

-- ============================================
-- Stored Procedure: Decay Pattern Confidence
-- ============================================
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_DecayPatternConfidence')
    DROP PROCEDURE sp_DecayPatternConfidence;
GO

CREATE PROCEDURE sp_DecayPatternConfidence
    @DecayRate DECIMAL(5,4) = 0.95,
    @MaxAgeDays INT = 90
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Apply decay to patterns not updated recently
    UPDATE dbo.Patterns
    SET Confidence = Confidence * @DecayRate,
        UpdatedAt = GETDATE()
    WHERE IsActive = 1
      AND UpdatedAt < DATEADD(DAY, -7, GETDATE());
    
    DECLARE @DecayedCount INT = @@ROWCOUNT;
    
    -- Deactivate very old patterns with low confidence
    UPDATE dbo.Patterns
    SET IsActive = 0
    WHERE IsActive = 1
      AND Confidence < 0.2
      AND UpdatedAt < DATEADD(DAY, -@MaxAgeDays, GETDATE());
    
    DECLARE @DeactivatedCount INT = @@ROWCOUNT;
    
    SELECT 
        @DecayedCount AS PatternsDecayed,
        @DeactivatedCount AS PatternsDeactivated;
END
GO

PRINT 'Created procedure: sp_DecayPatternConfidence';
GO

-- ============================================
-- Stored Procedure: Get Learning Summary
-- ============================================
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_GetLearningSummary')
    DROP PROCEDURE sp_GetLearningSummary;
GO

CREATE PROCEDURE sp_GetLearningSummary
    @Days INT = 30
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        -- Learning counts (using CreatedAt instead of Timestamp)
        (SELECT COUNT(*) FROM dbo.LearningStore 
         WHERE CreatedAt >= DATEADD(DAY, -@Days, GETDATE())) AS TotalLearnings,
        
        -- Pattern counts
        (SELECT COUNT(*) FROM dbo.Patterns WHERE IsActive = 1) AS ActivePatterns,
        (SELECT COUNT(*) FROM dbo.Patterns 
         WHERE IsActive = 1 AND Confidence >= 0.7) AS HighConfidencePatterns,
        (SELECT AVG(Confidence) FROM dbo.Patterns 
         WHERE IsActive = 1) AS AvgPatternConfidence,
        
        -- Recommendation counts
        (SELECT COUNT(*) FROM dbo.Recommendations 
         WHERE CreatedAt >= DATEADD(DAY, -@Days, GETDATE())) AS TotalRecommendations,
        (SELECT COUNT(*) FROM dbo.Recommendations 
         WHERE Applied = 1 
           AND AppliedAt >= DATEADD(DAY, -@Days, GETDATE())) AS AppliedRecommendations,
        
        -- Learning by type (using PatternType instead of LearningType)
        (SELECT COUNT(*) FROM dbo.LearningStore 
         WHERE PatternType = 'TRADE_OUTCOME'
           AND CreatedAt >= DATEADD(DAY, -@Days, GETDATE())) AS TradeOutcomeLearnings,
        (SELECT COUNT(*) FROM dbo.LearningStore 
         WHERE PatternType = 'PATTERN_CONFIRMED'
           AND CreatedAt >= DATEADD(DAY, -@Days, GETDATE())) AS PatternConfirmedLearnings,
        (SELECT COUNT(*) FROM dbo.LearningStore 
         WHERE PatternType = 'PARAMETER_ADJUSTED'
           AND CreatedAt >= DATEADD(DAY, -@Days, GETDATE())) AS ParameterAdjustedLearnings;
END
GO

PRINT 'Created procedure: sp_GetLearningSummary';
GO

PRINT 'Learning Store extended schema created successfully!';
GO
