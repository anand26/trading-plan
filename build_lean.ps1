# TQQQ/SQQQ Trading System - Build LEAN Script
# This script compiles the QuantConnect LEAN engine
# Run: .\build_lean.ps1

param(
    [ValidateSet("Release", "Debug")]
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LEAN Engine Build Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check for .NET SDK
Write-Host "[1/4] Checking .NET SDK..." -ForegroundColor Yellow

$dotnetVersion = dotnet --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: .NET SDK not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please install .NET 8 SDK from:" -ForegroundColor Yellow
    Write-Host "  https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Gray
    exit 1
}

Write-Host "  OK: .NET SDK $dotnetVersion" -ForegroundColor Green

# Check LEAN folder exists
Write-Host ""
Write-Host "[2/4] Checking LEAN source..." -ForegroundColor Yellow

$leanPath = Join-Path $PSScriptRoot "quantconnect-lean"
$slnPath = Join-Path $leanPath "QuantConnect.Lean.sln"

if (-not (Test-Path $slnPath)) {
    Write-Host "  ERROR: QuantConnect.Lean.sln not found at:" -ForegroundColor Red
    Write-Host "  $slnPath" -ForegroundColor Gray
    exit 1
}

Write-Host "  OK: LEAN solution found" -ForegroundColor Green

# Restore NuGet packages
Write-Host ""
Write-Host "[3/4] Restoring NuGet packages..." -ForegroundColor Yellow

Push-Location $leanPath
try {
    dotnet restore QuantConnect.Lean.sln --verbosity minimal
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Package restore failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK: Packages restored" -ForegroundColor Green
}
finally {
    Pop-Location
}

# Build LEAN
Write-Host ""
Write-Host "[4/4] Building LEAN ($Configuration)..." -ForegroundColor Yellow

Push-Location $leanPath
try {
    dotnet build QuantConnect.Lean.sln -c $Configuration --no-restore
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK: Build successful" -ForegroundColor Green
}
finally {
    Pop-Location
}

# Verify output
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan

$launcherPath = Join-Path $leanPath "Launcher\bin\$Configuration\QuantConnect.Lean.Launcher.exe"
$launcherNet6Path = Join-Path $leanPath "Launcher\bin\$Configuration\net6.0\QuantConnect.Lean.Launcher.exe"

if (Test-Path $launcherPath) {
    Write-Host ""
    Write-Host "Launcher ready at:" -ForegroundColor White
    Write-Host "  $launcherPath" -ForegroundColor Cyan
}
elseif (Test-Path $launcherNet6Path) {
    Write-Host ""
    Write-Host "Launcher ready at:" -ForegroundColor White
    Write-Host "  $launcherNet6Path" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Start the dashboard: cd dashboard && streamlit run src/dashboard/app.py" -ForegroundColor Gray
Write-Host "  2. Go to 'Backtest Runner' page to run backtests" -ForegroundColor Gray
Write-Host ""
