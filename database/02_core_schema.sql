-- ============================================
-- TQQQ/SQQQ Trading System - Core Schema
-- ============================================
-- Trading tables for orders, trades, positions
-- Execute with: sqlcmd -S localhost -E -d TradingDB -i 02_core_schema.sql
-- ============================================

USE TradingDB;
GO

-- ============================================
-- 1. ORDERS TABLE
-- ============================================
-- Stores all order events from the algorithm
CREATE TABLE Orders (
    OrderId             BIGINT IDENTITY(1,1) PRIMARY KEY,
    ExternalOrderId     VARCHAR(100) NOT NULL,          -- LEAN/Alpaca order ID
    Symbol              VARCHAR(10) NOT NULL,           -- TQQQ, SQQQ
    Quantity            DECIMAL(18, 8) NOT NULL,        -- Order quantity
    FilledQuantity      DECIMAL(18, 8) DEFAULT 0,       -- Actually filled
    Price               DECIMAL(18, 4),                 -- Limit price (if applicable)
    FillPrice           DECIMAL(18, 4),                 -- Average fill price
    OrderType           VARCHAR(20) NOT NULL,           -- MARKET, LIMIT, STOP, STOP_LIMIT
    Direction           VARCHAR(10) NOT NULL,           -- BUY, SELL
    Status              VARCHAR(20) NOT NULL,           -- SUBMITTED, FILLED, PARTIAL, CANCELED, REJECTED
    TimeInForce         VARCHAR(10) DEFAULT 'DAY',      -- DAY, GTC, IOC, FOK
    SubmittedAt         DATETIME2 NOT NULL,
    FilledAt            DATETIME2,
    Tag                 NVARCHAR(500),                  -- Algorithm tag/reason
    Commission          DECIMAL(18, 4) DEFAULT 0,
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    INDEX IX_Orders_Symbol (Symbol),
    INDEX IX_Orders_SubmittedAt (SubmittedAt DESC),
    INDEX IX_Orders_Status (Status),
    INDEX IX_Orders_ExternalId (ExternalOrderId)
);
GO

-- ============================================
-- 2. TRADES TABLE
-- ============================================
-- Stores completed round-trip trades (entry to exit)
CREATE TABLE Trades (
    TradeId             BIGINT IDENTITY(1,1) PRIMARY KEY,
    Symbol              VARCHAR(10) NOT NULL,
    Direction           VARCHAR(10) NOT NULL,           -- LONG, SHORT
    
    -- Entry details
    EntryTime           DATETIME2 NOT NULL,
    EntryPrice          DECIMAL(18, 4) NOT NULL,        -- Average entry price
    EntryQuantity       DECIMAL(18, 8) NOT NULL,
    
    -- Exit details
    ExitTime            DATETIME2,
    ExitPrice           DECIMAL(18, 4),                 -- Average exit price
    ExitQuantity        DECIMAL(18, 8),
    ExitReason          VARCHAR(50),                    -- TAKE_PROFIT, STOP_LOSS, EOD_CLOSE, MANUAL
    
    -- Performance metrics
    GrossPnL            DECIMAL(18, 4),                 -- Profit/Loss before fees
    Commission          DECIMAL(18, 4) DEFAULT 0,
    NetPnL              DECIMAL(18, 4),                 -- Profit/Loss after fees
    PnLPercent          DECIMAL(10, 4),                 -- P&L as percentage
    
    -- Pyramiding info
    NumEntries          INT DEFAULT 1,                  -- Number of pyramid levels used
    MaxQuantity         DECIMAL(18, 8),                 -- Maximum position size reached
    
    -- Price extremes during trade
    HighestPrice        DECIMAL(18, 4),                 -- For MFE calculation
    LowestPrice         DECIMAL(18, 4),                 -- For MAE calculation
    MAE                 DECIMAL(10, 4),                 -- Maximum Adverse Excursion %
    MFE                 DECIMAL(10, 4),                 -- Maximum Favorable Excursion %
    
    -- Duration
    DurationMinutes     INT,
    
    -- Metadata
    SessionId           VARCHAR(50),                    -- Backtest or live session ID
    AlgorithmVersion    VARCHAR(20),
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    INDEX IX_Trades_Symbol (Symbol),
    INDEX IX_Trades_EntryTime (EntryTime DESC),
    INDEX IX_Trades_ExitTime (ExitTime DESC),
    INDEX IX_Trades_SessionId (SessionId),
    INDEX IX_Trades_Direction (Direction)
);
GO

-- ============================================
-- 3. POSITION ENTRIES TABLE
-- ============================================
-- Stores individual pyramid entries for each trade
CREATE TABLE PositionEntries (
    EntryId             BIGINT IDENTITY(1,1) PRIMARY KEY,
    TradeId             BIGINT NOT NULL,
    EntryLevel          INT NOT NULL,                   -- 1, 2, or 3
    
    Price               DECIMAL(18, 4) NOT NULL,
    Quantity            DECIMAL(18, 8) NOT NULL,
    EntryTime           DATETIME2 NOT NULL,
    
    -- Entry conditions captured
    RSI_Value           DECIMAL(10, 4),
    BB_Lower            DECIMAL(18, 4),
    BB_Upper            DECIMAL(18, 4),
    VWAP_Value          DECIMAL(18, 4),
    Volume              BIGINT,
    
    OrderId             BIGINT,                         -- Reference to Orders table
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_PositionEntries_Trades 
        FOREIGN KEY (TradeId) REFERENCES Trades(TradeId) ON DELETE CASCADE,
    CONSTRAINT FK_PositionEntries_Orders 
        FOREIGN KEY (OrderId) REFERENCES Orders(OrderId),
    
    INDEX IX_PositionEntries_TradeId (TradeId),
    INDEX IX_PositionEntries_EntryTime (EntryTime DESC)
);
GO

-- ============================================
-- 4. DAILY PERFORMANCE TABLE
-- ============================================
-- Aggregated daily performance metrics
CREATE TABLE DailyPerformance (
    PerformanceId       BIGINT IDENTITY(1,1) PRIMARY KEY,
    Date                DATE NOT NULL UNIQUE,
    
    -- Equity tracking
    StartingEquity      DECIMAL(18, 4) NOT NULL,
    EndingEquity        DECIMAL(18, 4) NOT NULL,
    HighWaterMark       DECIMAL(18, 4),
    
    -- P&L
    DailyPnL            DECIMAL(18, 4) NOT NULL,
    DailyPnLPercent     DECIMAL(10, 4) NOT NULL,
    CumulativePnL       DECIMAL(18, 4),
    
    -- Trade statistics
    NumTrades           INT DEFAULT 0,
    WinningTrades       INT DEFAULT 0,
    LosingTrades        INT DEFAULT 0,
    BreakEvenTrades     INT DEFAULT 0,
    
    -- Amounts
    GrossProfit         DECIMAL(18, 4) DEFAULT 0,
    GrossLoss           DECIMAL(18, 4) DEFAULT 0,
    TotalCommission     DECIMAL(18, 4) DEFAULT 0,
    
    -- Risk metrics
    MaxDrawdown         DECIMAL(10, 4),                 -- Intraday max drawdown %
    MaxDrawdownAmount   DECIMAL(18, 4),
    
    -- Volume
    TotalVolume         BIGINT DEFAULT 0,
    
    -- Market regime
    MarketRegime        VARCHAR(20),                    -- TRENDING_UP, TRENDING_DOWN, MEAN_REVERTING
    
    SessionId           VARCHAR(50),
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    INDEX IX_DailyPerformance_Date (Date DESC),
    INDEX IX_DailyPerformance_SessionId (SessionId)
);
GO

-- ============================================
-- 5. ACCOUNT SNAPSHOTS TABLE
-- ============================================
-- Periodic snapshots of account state
CREATE TABLE AccountSnapshots (
    SnapshotId          BIGINT IDENTITY(1,1) PRIMARY KEY,
    Timestamp           DATETIME2 NOT NULL,
    
    -- Account values
    TotalEquity         DECIMAL(18, 4) NOT NULL,
    Cash                DECIMAL(18, 4) NOT NULL,
    PositionValue       DECIMAL(18, 4) NOT NULL,
    BuyingPower         DECIMAL(18, 4),
    
    -- Position details
    UnrealizedPnL       DECIMAL(18, 4) DEFAULT 0,
    RealizedPnL         DECIMAL(18, 4) DEFAULT 0,
    
    -- Positions held (JSON for flexibility)
    PositionsJson       NVARCHAR(MAX),
    
    -- Margin info
    MarginUsed          DECIMAL(18, 4),
    MaintenanceMargin   DECIMAL(18, 4),
    
    SessionId           VARCHAR(50),
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    INDEX IX_AccountSnapshots_Timestamp (Timestamp DESC),
    INDEX IX_AccountSnapshots_SessionId (SessionId)
);
GO

-- ============================================
-- 6. SIGNALS TABLE
-- ============================================
-- Stores all signals generated (for analysis)
CREATE TABLE Signals (
    SignalId            BIGINT IDENTITY(1,1) PRIMARY KEY,
    Timestamp           DATETIME2 NOT NULL,
    Symbol              VARCHAR(10) NOT NULL,
    
    -- Signal details
    SignalType          VARCHAR(30) NOT NULL,           -- ENTRY_L1, ENTRY_L2, ENTRY_L3, EXIT, STOP_LOSS
    Action              VARCHAR(10) NOT NULL,           -- BUY, SELL, HOLD
    Strength            DECIMAL(5, 2),                  -- Signal strength 0-100
    
    -- Price data
    Price               DECIMAL(18, 4) NOT NULL,
    
    -- Indicator values at signal time
    RSI                 DECIMAL(10, 4),
    BB_Upper            DECIMAL(18, 4),
    BB_Middle           DECIMAL(18, 4),
    BB_Lower            DECIMAL(18, 4),
    VWAP                DECIMAL(18, 4),
    EMA_Fast            DECIMAL(18, 4),                 -- QQQ EMA(9)
    EMA_Slow            DECIMAL(18, 4),                 -- QQQ EMA(21)
    
    -- Volume
    Volume              BIGINT,
    AvgVolume           BIGINT,
    VolumeRatio         DECIMAL(10, 4),
    
    -- Market context
    MarketRegime        VARCHAR(20),
    QQQ_Price           DECIMAL(18, 4),
    
    -- Was signal acted upon?
    WasExecuted         BIT DEFAULT 0,
    ExecutedOrderId     BIGINT,
    NonExecutionReason  VARCHAR(100),                   -- DAILY_LIMIT, POSITION_OPEN, etc.
    
    SessionId           VARCHAR(50),
    CreatedAt           DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Signals_Orders 
        FOREIGN KEY (ExecutedOrderId) REFERENCES Orders(OrderId),
    
    INDEX IX_Signals_Timestamp (Timestamp DESC),
    INDEX IX_Signals_Symbol (Symbol),
    INDEX IX_Signals_SignalType (SignalType),
    INDEX IX_Signals_SessionId (SessionId)
);
GO

-- ============================================
-- 7. BARS TABLE (Optional - High Volume)
-- ============================================
-- Stores 5-minute bars for analysis
CREATE TABLE Bars (
    BarId               BIGINT IDENTITY(1,1) PRIMARY KEY,
    Symbol              VARCHAR(10) NOT NULL,
    Timestamp           DATETIME2 NOT NULL,
    Resolution          VARCHAR(10) NOT NULL,           -- 1MIN, 5MIN, 15MIN, 1H, 1D
    
    -- OHLCV
    [Open]              DECIMAL(18, 4) NOT NULL,
    High                DECIMAL(18, 4) NOT NULL,
    Low                 DECIMAL(18, 4) NOT NULL,
    [Close]             DECIMAL(18, 4) NOT NULL,
    Volume              BIGINT NOT NULL,
    
    -- Computed indicators (optional, for fast queries)
    RSI                 DECIMAL(10, 4),
    VWAP                DECIMAL(18, 4),
    BB_Upper            DECIMAL(18, 4),
    BB_Lower            DECIMAL(18, 4),
    
    SessionId           VARCHAR(50),
    
    -- Composite index for efficient queries
    INDEX IX_Bars_Symbol_Timestamp (Symbol, Timestamp DESC),
    INDEX IX_Bars_Resolution (Resolution),
    
    -- Unique constraint
    CONSTRAINT UQ_Bars_Symbol_Timestamp_Resolution 
        UNIQUE (Symbol, Timestamp, Resolution)
);
GO

-- ============================================
-- 8. AUDIT LOG TABLE
-- ============================================
-- System audit trail
CREATE TABLE AuditLog (
    LogId               BIGINT IDENTITY(1,1) PRIMARY KEY,
    Timestamp           DATETIME2 DEFAULT GETUTCDATE(),
    
    EventType           VARCHAR(50) NOT NULL,           -- ALGORITHM_START, ALGORITHM_STOP, TRADE_EXECUTED, ERROR, etc.
    Severity            VARCHAR(20) NOT NULL,           -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    Source              VARCHAR(100),                   -- Algorithm, MCP, Dashboard, etc.
    Message             NVARCHAR(MAX) NOT NULL,
    
    -- Optional context
    Symbol              VARCHAR(10),
    OrderId             BIGINT,
    TradeId             BIGINT,
    
    -- Error details
    ExceptionType       VARCHAR(200),
    StackTrace          NVARCHAR(MAX),
    
    SessionId           VARCHAR(50),
    UserId              VARCHAR(50),
    
    INDEX IX_AuditLog_Timestamp (Timestamp DESC),
    INDEX IX_AuditLog_EventType (EventType),
    INDEX IX_AuditLog_Severity (Severity),
    INDEX IX_AuditLog_SessionId (SessionId)
);
GO

PRINT 'Core schema created successfully.';
GO
