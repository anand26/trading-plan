# TQQQ/SQQQ Adaptive Trading System - Database Reset Script
# Drops and recreates all database objects
# Run: .\reset_database.ps1

param(
    [string]$SqlServer = "localhost",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Red
Write-Host "  DATABASE RESET SCRIPT" -ForegroundColor Red
Write-Host "============================================" -ForegroundColor Red
Write-Host ""
Write-Host "WARNING: This will DROP and RECREATE the TradingDB database!" -ForegroundColor Yellow
Write-Host "All data will be PERMANENTLY DELETED!" -ForegroundColor Yellow
Write-Host ""

if (-not $Force) {
    $confirm = Read-Host "Type 'YES' to confirm"
    if ($confirm -ne "YES") {
        Write-Host "Aborted." -ForegroundColor Gray
        exit 0
    }
}

# Check sqlcmd
$sqlcmd = Get-Command sqlcmd -ErrorAction SilentlyContinue
if (-not $sqlcmd) {
    Write-Host "ERROR: sqlcmd not found. Install SQL Server tools." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Dropping database..." -ForegroundColor Yellow

# Drop database
$dropSql = @"
USE master;
IF EXISTS (SELECT name FROM sys.databases WHERE name = 'TradingDB')
BEGIN
    ALTER DATABASE TradingDB SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE TradingDB;
    PRINT 'Database dropped.';
END
"@

$dropSql | sqlcmd -S $SqlServer -b

Write-Host "Recreating database..." -ForegroundColor Yellow

# Run all schema files
$schemaFiles = @(
    "01_create_database.sql",
    "02_core_schema.sql",
    "03_learning_schema.sql",
    "04_config_schema.sql",
    "05_stored_procedures.sql",
    "06_views_indexes.sql",
    "07_lean_ops_mcp_schema.sql",
    "08_trade_mind_mcp_schema.sql",
    "09_learning_store_schema.sql",
    "10_adaptive_agent_schema.sql"
)

foreach ($file in $schemaFiles) {
    $filePath = "database\$file"
    if (Test-Path $filePath) {
        Write-Host "  Running $file..." -ForegroundColor Gray
        
        if ($file -eq "01_create_database.sql") {
            sqlcmd -S $SqlServer -d master -i $filePath -b 2>&1 | Out-Null
        } else {
            sqlcmd -S $SqlServer -d TradingDB -i $filePath -b 2>&1 | Out-Null
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  OK: $file" -ForegroundColor Green
        } else {
            Write-Host "  ERROR: $file failed" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "Database reset complete!" -ForegroundColor Green

# Verify
Write-Host ""
Write-Host "Verifying tables..." -ForegroundColor Yellow
sqlcmd -S $SqlServer -d TradingDB -Q "SELECT COUNT(*) AS TableCount FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'"
