# TQQQ/SQQQ Adaptive Trading System - Setup Script
# Run: .\setup.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TQQQ/SQQQ Trading System Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "[1/6] Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($pythonVersion -match "Python 3\.1[1-9]") {
    Write-Host "  ✓ $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ Python 3.11+ required. Found: $pythonVersion" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "[2/6] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "  ✓ Virtual environment already exists" -ForegroundColor Green
} else {
    python -m venv .venv
    Write-Host "  ✓ Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "[3/6] Activating virtual environment..." -ForegroundColor Yellow
.\.venv\Scripts\Activate.ps1
Write-Host "  ✓ Activated" -ForegroundColor Green

# Install dependencies
Write-Host ""
Write-Host "[4/6] Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip -q
pip install -r requirements.txt -q
Write-Host "  ✓ Dependencies installed" -ForegroundColor Green

# Install local packages in editable mode
Write-Host ""
Write-Host "[5/6] Installing local packages..." -ForegroundColor Yellow

$packages = @("adaptive-agent", "learning-store", "tests")
foreach ($pkg in $packages) {
    if (Test-Path "$pkg\setup.py") {
        Push-Location $pkg
        pip install -e . -q
        Pop-Location
        Write-Host "  ✓ Installed $pkg" -ForegroundColor Green
    } else {
        Write-Host "  - Skipped $pkg (no setup.py)" -ForegroundColor Gray
    }
}

# Create .env if not exists
Write-Host ""
Write-Host "[6/6] Setting up configuration..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  ✓ .env already exists" -ForegroundColor Green
} else {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "  ✓ Created .env from template" -ForegroundColor Green
        Write-Host "  ! IMPORTANT: Edit .env with your settings!" -ForegroundColor Yellow
    } else {
        Write-Host "  ✗ No .env.example found" -ForegroundColor Red
    }
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit .env with your database and Alpaca credentials" -ForegroundColor Gray
Write-Host "  2. Run database schema: sqlcmd -S localhost -d TradingDB -i database\*.sql" -ForegroundColor Gray
Write-Host "  3. Run tests: cd tests && python run_tests.py" -ForegroundColor Gray
Write-Host "  4. Start dashboard: cd dashboard && streamlit run app.py" -ForegroundColor Gray
Write-Host ""
Write-Host "For detailed instructions, see:" -ForegroundColor White
Write-Host "  - GETTING_STARTED.md" -ForegroundColor Cyan
Write-Host "  - CONFIGURATION_GUIDE.md" -ForegroundColor Cyan
Write-Host ""

