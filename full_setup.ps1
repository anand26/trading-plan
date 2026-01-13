# TQQQ/SQQQ Adaptive Trading System - Full Setup Script
# This script sets up the complete development environment
# Run: .\full_setup.ps1

param(
    [switch]$SkipPython,
    [switch]$SkipDatabase,
    [switch]$SkipLean,
    [string]$SqlServer = "localhost"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  TQQQ/SQQQ Trading System - Full Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# 1. PYTHON ENVIRONMENT
# ============================================
if (-not $SkipPython) {
    Write-Host "[1/4] Setting up Python environment..." -ForegroundColor Yellow
    
    # Check Python version
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python 3\.1[1-9]") {
        Write-Host "  OK: $pythonVersion" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Python 3.11+ required. Found: $pythonVersion" -ForegroundColor Red
        exit 1
    }
    
    # Create virtual environment
    if (-not (Test-Path ".venv")) {
        Write-Host "  Creating virtual environment..." -ForegroundColor Gray
        python -m venv .venv
    }
    Write-Host "  OK: Virtual environment exists" -ForegroundColor Green
    
    # Activate virtual environment
    Write-Host "  Activating virtual environment..." -ForegroundColor Gray
    .\.venv\Scripts\Activate.ps1
    
    # Upgrade pip
    Write-Host "  Upgrading pip..." -ForegroundColor Gray
    pip install --upgrade pip -q
    
    # Install requirements
    if (Test-Path "requirements.txt") {
        Write-Host "  Installing requirements.txt..." -ForegroundColor Gray
        pip install -r requirements.txt -q
        Write-Host "  OK: Requirements installed" -ForegroundColor Green
    }
    
    # Install local packages in editable mode
    $packages = @("adaptive-agent", "learning-store", "lean-ops-mcp", "trade-mind-mcp", "dashboard", "tests")
    foreach ($pkg in $packages) {
        if (Test-Path "$pkg\pyproject.toml") {
            Write-Host "  Installing $pkg..." -ForegroundColor Gray
            pip install -e ".\$pkg" -q 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  OK: Installed $pkg" -ForegroundColor Green
            }
        }
    }
    
    Write-Host ""
}

# ============================================
# 2. DATABASE SETUP
# ============================================
if (-not $SkipDatabase) {
    Write-Host "[2/4] Setting up database..." -ForegroundColor Yellow
    
    # Check if sqlcmd is available
    $sqlcmd = Get-Command sqlcmd -ErrorAction SilentlyContinue
    if (-not $sqlcmd) {
        Write-Host "  WARNING: sqlcmd not found. Skipping database setup." -ForegroundColor Yellow
        Write-Host "  Install SQL Server tools or run database scripts manually." -ForegroundColor Gray
    } else {
        Write-Host "  OK: sqlcmd found" -ForegroundColor Green
        
        # Run schema files in order
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
                
                # First file creates the database, use master
                if ($file -eq "01_create_database.sql") {
                    sqlcmd -S $SqlServer -d master -i $filePath -b 2>&1 | Out-Null
                } else {
                    sqlcmd -S $SqlServer -d TradingDB -i $filePath -b 2>&1 | Out-Null
                }
                
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "  OK: $file" -ForegroundColor Green
                } else {
                    Write-Host "  WARNING: $file had errors (may be OK if re-running)" -ForegroundColor Yellow
                }
            }
        }
    }
    
    Write-Host ""
}

# ============================================
# 3. CONFIGURATION
# ============================================
Write-Host "[3/4] Setting up configuration..." -ForegroundColor Yellow

# Create .env from template if needed
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "  OK: Created .env from template" -ForegroundColor Green
        Write-Host "  ACTION REQUIRED: Edit .env with your credentials!" -ForegroundColor Yellow
    } else {
        # Create a basic .env template
        $envContent = @"
# Database Configuration
DB_SERVER=localhost
DB_NAME=TradingDB
DB_DRIVER=ODBC Driver 17 for SQL Server

# Alpaca API (Paper Trading)
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# QuantConnect LEAN
LEAN_DATA_PATH=./quantconnect-lean/Data
LEAN_RESULTS_PATH=./quantconnect-lean/Results

# Agent Configuration
AGENT_MODE=observe
AGENT_CYCLE_SECONDS=300
"@
        $envContent | Out-File -FilePath ".env" -Encoding utf8
        Write-Host "  OK: Created .env template" -ForegroundColor Green
        Write-Host "  ACTION REQUIRED: Edit .env with your credentials!" -ForegroundColor Yellow
    }
} else {
    Write-Host "  OK: .env already exists" -ForegroundColor Green
}

Write-Host ""

# ============================================
# 4. QUANTCONNECT LEAN (Optional)
# ============================================
if (-not $SkipLean) {
    Write-Host "[4/4] Checking QuantConnect LEAN..." -ForegroundColor Yellow
    
    if (Test-Path "quantconnect-lean") {
        # Check if .NET SDK is available
        $dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
        if ($dotnet) {
            Write-Host "  OK: .NET SDK found" -ForegroundColor Green
            Write-Host "  To build LEAN: cd quantconnect-lean && dotnet build QuantConnect.Lean.sln" -ForegroundColor Gray
        } else {
            Write-Host "  WARNING: .NET SDK not found. Install for LEAN backtesting." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  INFO: quantconnect-lean folder not found" -ForegroundColor Gray
    }
    
    Write-Host ""
}

# ============================================
# SUMMARY
# ============================================
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit .env with your database and Alpaca credentials" -ForegroundColor Gray
Write-Host "  2. Verify database: sqlcmd -S localhost -d TradingDB -Q 'SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES'" -ForegroundColor Gray
Write-Host "  3. Run tests: cd tests && python run_tests.py" -ForegroundColor Gray
Write-Host "  4. Start dashboard: cd dashboard && streamlit run src/dashboard/app.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Documentation:" -ForegroundColor White
Write-Host "  - GETTING_STARTED.md" -ForegroundColor Cyan
Write-Host "  - CONFIGURATION_GUIDE.md" -ForegroundColor Cyan
Write-Host "  - ARCHITECTURE_COMPARISON.md" -ForegroundColor Cyan
Write-Host ""
