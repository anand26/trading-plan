-- ============================================
-- TQQQ/SQQQ Trading System - Learning Schema
-- ============================================
-- Tables for adaptive learning and pattern storage
-- Execute with: sqlcmd -S localhost -E -d TradingDB -i 03_learning_schema.sql
-- ============================================

USE TradingDB;
GO

-- ============================================
-- 1. BACKTEST OUTCOMES TABLE
-- ============================================
-- Stores results from all backtests for pattern learning
CREATE TABLE BacktestOutcomes (
    OutcomeId           BIGINT IDENTITY(1,1) PRIMARY KEY,
    BacktestId          VARCHAR(50) NOT NULL UNIQUE,    -- Unique backtest identifier
    StrategyId          VARCHAR(50) NOT NULL,           -- e.g., TQQQ_SCALPING_V1
    
    -- Time period
    StartDate           DATE NOT NULL,
    EndDate             DATE NOT NULL,
    TradingDays         INT,
    
    -- Parameters used (JSON)
    ParametersJson      NVARCHAR(MAX) NOT NULL,
    
    -- Performance metrics
    TotalReturn         DECIMAL(10, 4),                 -- Total return %
    CAGR                DECIMAL(10, 4),                 -- Compound annual growth rate
    SharpeRatio         DECIMAL(10, 4),
    SortinoRatio        DECIMAL(10, 4),
    CalmarRatio         DECIMAL(10, 4),
    
    -- Risk metrics
    MaxDrawdown         DECIMAL(10, 4),
    MaxDrawdownDuration INT,                            -- Days
    Volatility          DECIMAL(10, 4),                 -- Annualized
    VaR_95              DECIMAL(10, 4),                 -- Value at Risk 95%
    
    -- Trade statistics
    TotalTrades         INT,
    WinningTrades       INT,
    LosingTrades        INT,
    WinRate             DECIMAL(10, 4),
    ProfitFactor        DECIMAL(10, 4),
    
    -- Amounts
    TotalProfit         DECIMAL(18, 4),
    TotalLoss           DECIMAL(18, 4),
    AverageWin          DECIMAL(18, 4),
    AverageLoss         DECIMAL(18, 4),
    LargestWin          DECIMAL(18, 4),
    LargestLoss         DECIMAL(18, 4),
    
    -- Expectancy
    Expectancy          DECIMAL(10, 4),                 -- Expected value per trade
    ExpectancyRatio     DECIMAL(10, 4),                 -- Expectancy / Avg Loss
    
    -- Market regime during backtest
    PrimaryRegime       VARCHAR(20),                    -- Dominant regime
    RegimeBreakdown     NVARCHAR(500),                  -- JSON: {trending: 40%, mean_reverting: 60%}
    
    -- Grading
    PerformanceGrade    CHAR(2),                        -- A, B+, B, C+, C, D, F
    IsSuccessful        BIT,                            -- Based on criteria (Sharpe > 1, etc.)
    
    -- Metadata
    ExecutionTimeSeconds INT,
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    Notes               NVARCHAR(MAX),
    
    INDEX IX_BacktestOutcomes_StrategyId (StrategyId),
    INDEX IX_BacktestOutcomes_IsSuccessful (IsSuccessful),
    INDEX IX_BacktestOutcomes_PerformanceGrade (PerformanceGrade),
    INDEX IX_BacktestOutcomes_SharpeRatio (SharpeRatio DESC),
    INDEX IX_BacktestOutcomes_CreatedAt (CreatedAt DESC)
);
GO

-- ============================================
-- 2. PARAMETER PERFORMANCE TABLE
-- ============================================
-- Correlates individual parameters with performance
CREATE TABLE ParameterPerformance (
    ParamPerfId         BIGINT IDENTITY(1,1) PRIMARY KEY,
    StrategyId          VARCHAR(50) NOT NULL,
    
    -- Parameter identification
    ParamName           VARCHAR(50) NOT NULL,           -- rsi_oversold, stop_loss_pct, etc.
    ParamValue          VARCHAR(50) NOT NULL,           -- The value tested
    
    -- Market regime context
    MarketRegime        VARCHAR(20),                    -- TRENDING_UP, TRENDING_DOWN, MEAN_REVERTING, ALL
    
    -- Aggregated performance (from multiple backtests)
    SampleCount         INT NOT NULL,                   -- Number of backtests with this param
    
    -- Average metrics
    AvgSharpeRatio      DECIMAL(10, 4),
    AvgWinRate          DECIMAL(10, 4),
    AvgProfitFactor     DECIMAL(10, 4),
    AvgMaxDrawdown      DECIMAL(10, 4),
    AvgReturn           DECIMAL(10, 4),
    
    -- Best/Worst case
    BestSharpe          DECIMAL(10, 4),
    WorstSharpe         DECIMAL(10, 4),
    BestReturn          DECIMAL(10, 4),
    WorstReturn         DECIMAL(10, 4),
    
    -- Statistical confidence
    StdDevSharpe        DECIMAL(10, 4),
    ConfidenceScore     DECIMAL(5, 2),                  -- 0-100
    
    -- Recommendation
    IsRecommended       BIT DEFAULT 0,
    
    LastUpdated         DATETIME2 DEFAULT GETUTCDATE(),
    
    INDEX IX_ParamPerf_Strategy_Param (StrategyId, ParamName),
    INDEX IX_ParamPerf_Regime (MarketRegime),
    INDEX IX_ParamPerf_AvgSharpe (AvgSharpeRatio DESC),
    
    CONSTRAINT UQ_ParamPerf_Unique 
        UNIQUE (StrategyId, ParamName, ParamValue, MarketRegime)
);
GO

-- ============================================
-- 3. MARKET REGIMES TABLE
-- ============================================
-- Historical market regime classifications
CREATE TABLE MarketRegimes (
    RegimeId            BIGINT IDENTITY(1,1) PRIMARY KEY,
    Date                DATE NOT NULL,
    
    -- Classification
    Regime              VARCHAR(20) NOT NULL,           -- TRENDING_UP, TRENDING_DOWN, MEAN_REVERTING, VOLATILE
    Confidence          DECIMAL(5, 2),                  -- Confidence in classification 0-100
    
    -- QQQ metrics used for classification
    QQQ_Close           DECIMAL(18, 4),
    QQQ_EMA9            DECIMAL(18, 4),
    QQQ_EMA21           DECIMAL(18, 4),
    EMA_Spread          DECIMAL(10, 4),                 -- (EMA9 - EMA21) / EMA21
    
    -- Volatility context
    QQQ_ATR             DECIMAL(18, 4),
    VIX_Close           DECIMAL(10, 4),
    
    -- Trend strength
    TrendStrength       DECIMAL(5, 2),                  -- 0-100
    TrendDuration       INT,                            -- Days in current regime
    
    -- Additional context
    SPY_Correlation     DECIMAL(5, 4),
    SectorRotation      VARCHAR(50),                    -- Leading sector
    
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    INDEX IX_MarketRegimes_Date (Date DESC),
    INDEX IX_MarketRegimes_Regime (Regime),
    
    CONSTRAINT UQ_MarketRegimes_Date UNIQUE (Date)
);
GO

-- ============================================
-- 4. CORRECTION HISTORY TABLE
-- ============================================
-- Tracks strategy corrections and their effectiveness
CREATE TABLE CorrectionHistory (
    CorrectionId        BIGINT IDENTITY(1,1) PRIMARY KEY,
    
    -- Context
    SessionId           VARCHAR(50) NOT NULL,
    StrategyId          VARCHAR(50) NOT NULL,
    CorrectionTime      DATETIME2 NOT NULL,
    
    -- What triggered the correction
    TriggerType         VARCHAR(50) NOT NULL,           -- LOW_WIN_RATE, HIGH_DRAWDOWN, LOW_SHARPE, etc.
    TriggerValue        DECIMAL(10, 4),                 -- The value that triggered it
    TriggerThreshold    DECIMAL(10, 4),                 -- The threshold that was breached
    
    -- Metrics before correction
    BeforeSharpe        DECIMAL(10, 4),
    BeforeWinRate       DECIMAL(10, 4),
    BeforeDrawdown      DECIMAL(10, 4),
    BeforeProfitFactor  DECIMAL(10, 4),
    
    -- The correction applied
    CorrectionType      VARCHAR(50) NOT NULL,           -- PARAM_CHANGE, POSITION_SIZE, PAUSE, etc.
    ParamChanged        VARCHAR(50),                    -- Which parameter
    OldValue            VARCHAR(50),
    NewValue            VARCHAR(50),
    CorrectionReason    NVARCHAR(500),
    
    -- Was it applied automatically or suggested?
    WasAutoApplied      BIT DEFAULT 0,
    WasAccepted         BIT,                            -- If suggested, was it accepted?
    
    -- Results after correction (filled in later)
    AfterSharpe         DECIMAL(10, 4),
    AfterWinRate        DECIMAL(10, 4),
    AfterDrawdown       DECIMAL(10, 4),
    AfterProfitFactor   DECIMAL(10, 4),
    
    -- Evaluation
    EvaluationPeriodDays INT,                           -- How long before evaluation
    WasEffective        BIT,                            -- Did it improve performance?
    EffectivenessScore  DECIMAL(5, 2),                  -- -100 to +100
    
    EvaluatedAt         DATETIME2,
    Notes               NVARCHAR(MAX),
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    INDEX IX_CorrectionHistory_SessionId (SessionId),
    INDEX IX_CorrectionHistory_StrategyId (StrategyId),
    INDEX IX_CorrectionHistory_TriggerType (TriggerType),
    INDEX IX_CorrectionHistory_WasEffective (WasEffective),
    INDEX IX_CorrectionHistory_CorrectionTime (CorrectionTime DESC)
);
GO

-- ============================================
-- 5. LEARNING PATTERNS TABLE
-- ============================================
-- Discovered patterns and insights
CREATE TABLE LearningPatterns (
    PatternId           BIGINT IDENTITY(1,1) PRIMARY KEY,
    StrategyId          VARCHAR(50) NOT NULL,
    
    -- Pattern identification
    PatternType         VARCHAR(50) NOT NULL,           -- WINNING_SETUP, LOSING_SETUP, TIME_OF_DAY, etc.
    PatternName         VARCHAR(100) NOT NULL,
    
    -- Pattern definition (JSON for flexibility)
    PatternConditions   NVARCHAR(MAX) NOT NULL,         -- JSON defining the pattern
    
    -- Statistics
    Occurrences         INT NOT NULL,
    WinCount            INT,
    LossCount           INT,
    WinRate             DECIMAL(10, 4),
    AvgPnLPercent       DECIMAL(10, 4),
    
    -- Significance
    StatisticalSignificance DECIMAL(5, 4),              -- p-value
    ConfidenceLevel     DECIMAL(5, 2),                  -- 0-100
    
    -- Actionable insight
    Recommendation      NVARCHAR(500),
    ActionType          VARCHAR(50),                    -- AVOID, PREFER, ADJUST_SIZE, etc.
    
    -- Validity
    IsActive            BIT DEFAULT 1,
    ValidFrom           DATE,
    ValidUntil          DATE,
    
    DiscoveredAt        DATETIME2 DEFAULT GETUTCDATE(),
    LastValidated       DATETIME2,
    
    INDEX IX_LearningPatterns_StrategyId (StrategyId),
    INDEX IX_LearningPatterns_PatternType (PatternType),
    INDEX IX_LearningPatterns_IsActive (IsActive),
    INDEX IX_LearningPatterns_WinRate (WinRate DESC)
);
GO

-- ============================================
-- 6. OPTIMAL PARAMETERS TABLE
-- ============================================
-- Best parameters per regime (computed from backtests)
CREATE TABLE OptimalParameters (
    OptParamId          BIGINT IDENTITY(1,1) PRIMARY KEY,
    StrategyId          VARCHAR(50) NOT NULL,
    MarketRegime        VARCHAR(20) NOT NULL,
    
    -- The optimal parameter set (JSON)
    ParametersJson      NVARCHAR(MAX) NOT NULL,
    
    -- Performance with these parameters
    ExpectedSharpe      DECIMAL(10, 4),
    ExpectedWinRate     DECIMAL(10, 4),
    ExpectedDrawdown    DECIMAL(10, 4),
    
    -- How it was determined
    BasedOnBacktests    INT,                            -- Number of backtests analyzed
    ConfidenceScore     DECIMAL(5, 2),
    
    -- Validity
    IsActive            BIT DEFAULT 1,
    ValidFrom           DATE NOT NULL,
    ValidUntil          DATE,
    
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    LastUpdated         DATETIME2,
    
    INDEX IX_OptimalParams_Strategy_Regime (StrategyId, MarketRegime),
    INDEX IX_OptimalParams_IsActive (IsActive),
    
    CONSTRAINT UQ_OptimalParams_Active 
        UNIQUE (StrategyId, MarketRegime, IsActive) -- Only one active per regime
);
GO

PRINT 'Learning schema created successfully.';
GO
