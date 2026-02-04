# TQQQ/SQQQ Trading System - Run Script
# This script compiles LEAN (if needed) and starts the dashboard
# Run: .\run.ps1

param(
    [switch]$ForceBuild,
    [switch]$SkipBuild,
    [ValidateSet("Release", "Debug")]
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  TQQQ/SQQQ Trading System" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# 1. Check Python Environment
# ============================================
Write-Host "[1/4] Checking Python environment..." -ForegroundColor Yellow

$venvPath = Join-Path $PSScriptRoot ".venv"
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"

if (-not (Test-Path $activateScript)) {
    Write-Host "  Creating virtual environment..." -ForegroundColor Gray
    python -m venv .venv
}

# Activate virtual environment
Write-Host "  Activating virtual environment..." -ForegroundColor Gray
& $activateScript

# NOTE: PYTHONNET_PYDLL, PYTHONHOME, PYTHONPATH are set by backtest_runner.py
# when launching LEAN, NOT here. Setting them globally breaks the venv.
# Just verify Python 3.11 is available for LEAN to use.
$python311Home = "C:\Users\anand\AppData\Local\Programs\Python\Python311"
$pythonDll = Join-Path $python311Home "python311.dll"

if (Test-Path $pythonDll) {
    Write-Host "  OK: Python 3.11 available for LEAN at $python311Home" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Python 3.11 not found. LEAN requires Python 3.8-3.11" -ForegroundColor Yellow
    Write-Host "  Install from: https://www.python.org/downloads/release/python-3119/" -ForegroundColor Gray
}

Write-Host "  OK: Python environment ready" -ForegroundColor Green

# ============================================
# 2. Check/Build LEAN
# ============================================
Write-Host ""
Write-Host "[2/4] Checking LEAN Engine..." -ForegroundColor Yellow

$leanPath = Join-Path $PSScriptRoot "quantconnect-lean"
$launcherPath = Join-Path $leanPath "Launcher\bin\$Configuration\QuantConnect.Lean.Launcher.exe"
$launcherNet6Path = Join-Path $leanPath "Launcher\bin\$Configuration\net6.0\QuantConnect.Lean.Launcher.exe"

$leanBuilt = (Test-Path $launcherPath) -or (Test-Path $launcherNet6Path)

if ($SkipBuild) {
    Write-Host "  Skipping LEAN build (--SkipBuild)" -ForegroundColor Gray
}
elseif ($ForceBuild -or -not $leanBuilt) {
    Write-Host "  Building LEAN Engine..." -ForegroundColor Gray
    
    # Check for .NET SDK
    $dotnetVersion = dotnet --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: .NET SDK not found!" -ForegroundColor Red
        Write-Host "  Please install .NET 8 SDK from: https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Yellow
        exit 1
    }
    
    Push-Location $leanPath
    try {
        Write-Host "  Restoring packages..." -ForegroundColor Gray
        dotnet restore QuantConnect.Lean.sln --verbosity quiet
        
        Write-Host "  Compiling ($Configuration)..." -ForegroundColor Gray
        dotnet build QuantConnect.Lean.sln -c $Configuration --no-restore --verbosity quiet
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  ERROR: Build failed!" -ForegroundColor Red
            exit 1
        }
        Write-Host "  OK: LEAN compiled successfully" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "  OK: LEAN already built" -ForegroundColor Green
}

# ============================================
# 3. Check Data Files
# ============================================
Write-Host ""
Write-Host "[3/4] Checking market data..." -ForegroundColor Yellow

$dataPath = Join-Path $leanPath "Data\equity\usa\minute"
$tqqqPath = Join-Path $dataPath "tqqq"
$sqqqPath = Join-Path $dataPath "sqqq"
$qqqPath = Join-Path $dataPath "qqq"

$dataReady = $true
$dataStats = @{}

foreach ($symbol in @("tqqq", "sqqq", "qqq")) {
    $symbolPath = Join-Path $dataPath $symbol
    if (Test-Path $symbolPath) {
        $fileCount = (Get-ChildItem $symbolPath -Filter "*.zip").Count
        $dataStats[$symbol.ToUpper()] = $fileCount
        if ($fileCount -eq 0) {
            $dataReady = $false
        }
    }
    else {
        $dataStats[$symbol.ToUpper()] = 0
        $dataReady = $false
    }
}

if ($dataReady) {
    Write-Host "  OK: Market data ready" -ForegroundColor Green
    foreach ($key in $dataStats.Keys) {
        Write-Host "    $key`: $($dataStats[$key]) trading days" -ForegroundColor Gray
    }
}
else {
    Write-Host "  WARNING: Some market data missing" -ForegroundColor Yellow
    Write-Host "  Run: python convert_databento_to_lean.py" -ForegroundColor Gray
}

# ============================================
# 4. Start Dashboard
# ============================================
Write-Host ""
Write-Host "[4/4] Starting Dashboard..." -ForegroundColor Yellow

$dashboardPath = Join-Path $PSScriptRoot "dashboard"

Push-Location $dashboardPath
try {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  Dashboard Starting!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Open in browser: http://localhost:8501" -ForegroundColor White
    Write-Host "  Press Ctrl+C to stop" -ForegroundColor Gray
    Write-Host ""
    
    streamlit run src/dashboard/app.py
}
finally {
    Pop-Location
}
