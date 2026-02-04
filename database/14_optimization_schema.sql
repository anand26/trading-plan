-- ============================================
-- Schema Migration: Optimization Support
-- ============================================
-- Adds tables and columns needed for parameter optimization tracking

-- 1. Add OptimizationRunId column to BacktestOutcomes if not exists
IF NOT EXISTS (
    SELECT 1 FROM sys.columns 
    WHERE object_id = OBJECT_ID('BacktestOutcomes') 
    AND name = 'OptimizationRunId'
)
BEGIN
    ALTER TABLE BacktestOutcomes ADD OptimizationRunId VARCHAR(100) NULL;
    PRINT 'Added OptimizationRunId column to BacktestOutcomes';
END
GO

-- 2. Create OptimizationRuns table if not exists
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'OptimizationRuns')
BEGIN
    CREATE TABLE OptimizationRuns (
        RunId VARCHAR(100) PRIMARY KEY,
        StartTime DATETIME2 NOT NULL,
        EndTime DATETIME2 NULL,
        TotalCombinations INT NOT NULL DEFAULT 0,
        CompletedCombinations INT NOT NULL DEFAULT 0,
        Status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
        SourceFile VARCHAR(500) NULL,
        CreatedAt DATETIME2 DEFAULT GETUTCDATE()
    );
    PRINT 'Created OptimizationRuns table';
END
GO

-- 3. Create index on OptimizationRunId for faster filtering
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes 
    WHERE name = 'IX_BacktestOutcomes_OptimizationRunId' 
    AND object_id = OBJECT_ID('BacktestOutcomes')
)
BEGIN
    CREATE INDEX IX_BacktestOutcomes_OptimizationRunId 
    ON BacktestOutcomes(OptimizationRunId);
    PRINT 'Created index IX_BacktestOutcomes_OptimizationRunId';
END
GO

-- 4. Create index on ParametersJson for JSON queries (computed column approach)
-- Note: SQL Server can use indexes on computed columns for JSON_VALUE queries
IF NOT EXISTS (
    SELECT 1 FROM sys.columns 
    WHERE object_id = OBJECT_ID('BacktestOutcomes') 
    AND name = 'ParamHash'
)
BEGIN
    ALTER TABLE BacktestOutcomes 
    ADD ParamHash AS CAST(JSON_VALUE(ParametersJson, '$._hash') AS VARCHAR(20)) PERSISTED;
    PRINT 'Added computed ParamHash column';
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes 
    WHERE name = 'IX_BacktestOutcomes_ParamHash' 
    AND object_id = OBJECT_ID('BacktestOutcomes')
)
BEGIN
    CREATE INDEX IX_BacktestOutcomes_ParamHash 
    ON BacktestOutcomes(ParamHash);
    PRINT 'Created index IX_BacktestOutcomes_ParamHash';
END
GO

PRINT 'Optimization schema migration completed';
