&lt;# 
.SYNOPSIS
    Sync algorithm files from algorithms/ to quantconnect-lean/Algorithm.Python/
    
.DESCRIPTION
    LEAN runs algorithms from quantconnect-lean/Algorithm.Python/
    This script copies your algorithm files there before running backtests.
    
.EXAMPLE
    .\sync_algorithm.ps1
#&gt;

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $projectRoot) {
    $projectRoot = (Get-Location).Path
}

$sourceDir = Join-Path $projectRoot "algorithms"
$targetDir = Join-Path $projectRoot "quantconnect-lean\Algorithm.Python"
$backtestDir = Join-Path $projectRoot "backtest"

Write-Host "Syncing algorithm files..." -ForegroundColor Cyan
Write-Host "Source: $sourceDir"
Write-Host "Target: $targetDir"

# Files to sync
$filesToSync = @(
    "TQQQScalpingAlgorithm.py",
    "sql_connector.py"
)

# Also sync webhook_simulator from backtest folder
$webhookSource = Join-Path $backtestDir "webhook_simulator.py"

foreach ($file in $filesToSync) {
    $src = Join-Path $sourceDir $file
    $dst = Join-Path $targetDir $file
    
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "  Copied: $file" -ForegroundColor Green
    } else {
        Write-Host "  Not found: $src" -ForegroundColor Yellow
    }
}

# Sync webhook_simulator
if (Test-Path $webhookSource) {
    $webhookDest = Join-Path $targetDir "webhook_simulator.py"
    Copy-Item -Path $webhookSource -Destination $webhookDest -Force
    Write-Host "  Copied: webhook_simulator.py (from backtest/)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Sync complete!" -ForegroundColor Green
Write-Host "LEAN will use files from: $targetDir"
