-- ============================================
-- TQQQ/SQQQ Trading System - Database Creation
-- ============================================
-- Run this script first to create the database
-- Execute with: sqlcmd -S localhost -E -i 01_create_database.sql
-- ============================================

USE master;
GO

-- Drop database if it exists (BE CAREFUL IN PRODUCTION!)
IF EXISTS (SELECT name FROM sys.databases WHERE name = N'TradingDB')
BEGIN
    ALTER DATABASE TradingDB SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE TradingDB;
END
GO

-- Create the database
CREATE DATABASE TradingDB
ON PRIMARY 
(
    NAME = TradingDB_Data,
    FILENAME = 'C:\SQLData\TradingDB.mdf',
    SIZE = 100MB,
    MAXSIZE = 10GB,
    FILEGROWTH = 100MB
)
LOG ON 
(
    NAME = TradingDB_Log,
    FILENAME = 'C:\SQLData\TradingDB_log.ldf',
    SIZE = 50MB,
    MAXSIZE = 5GB,
    FILEGROWTH = 50MB
);
GO

-- Set recovery model to SIMPLE for trading (less log overhead)
ALTER DATABASE TradingDB SET RECOVERY SIMPLE;
GO

-- Enable snapshot isolation for read consistency
ALTER DATABASE TradingDB SET ALLOW_SNAPSHOT_ISOLATION ON;
GO

USE TradingDB;
GO

PRINT 'Database TradingDB created successfully.';
GO
