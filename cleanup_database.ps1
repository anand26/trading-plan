# ============================================
# Database Cleanup Script
# ============================================
# Cleans database while preserving backtest data
# Removes incomplete OptimizationRuns and stale data
# Prepares for fresh paper trading
# ============================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Database Cleanup for Paper Trading" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Load environment variables
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, 'Process')
        }
    }
    Write-Host "[OK] Loaded environment variables" -ForegroundColor Green
} else {
    Write-Host "[!] .env file not found" -ForegroundColor Yellow
}

# Get connection string
$DB_SERVER = $env:DB_SERVER
$DB_NAME = $env:DB_NAME

if (-not $DB_SERVER) {
    $DB_SERVER = "localhost"
}
if (-not $DB_NAME) {
    $DB_NAME = "TradingDB"
}

Write-Host "Database: $DB_SERVER\$DB_NAME" -ForegroundColor Cyan
Write-Host ""

# Warning prompt
Write-Host "WARNING: This will:" -ForegroundColor Yellow
Write-Host "  - Keep ALL backtest data (sessions, trades, metrics)" -ForegroundColor Yellow
Write-Host "  - Delete incomplete OptimizationRuns" -ForegroundColor Yellow
Write-Host "  - Delete ALL paper/live trading data" -ForegroundColor Yellow
Write-Host "  - Clean orphaned and stale data" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Do you want to continue? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Cleanup cancelled." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Running cleanup script..." -ForegroundColor Cyan

# Run the SQL script
try {
    sqlcmd -S $DB_SERVER -d $DB_NAME -i "cleanup_database.sql" -E
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "============================================" -ForegroundColor Green
        Write-Host "  Cleanup completed successfully!" -ForegroundColor Green
        Write-Host "============================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Cyan
        Write-Host "  1. Start webhook stack: .\start_webhook_stack.ps1" -ForegroundColor White
        Write-Host "  2. Send paper trading signal to test" -ForegroundColor White
        Write-Host ""
    } else {
        Write-Host "Cleanup failed with error code: $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} catch {
    Write-Host "Error running cleanup: $_" -ForegroundColor Red
    exit 1
}
