# ============================================
# TQQQ/SQQQ Pairs Trading - Docker Stack Launcher
# ============================================
# Builds and starts webhook server + ngrok tunnel
# Usage: .\start_webhook_stack.ps1
# ============================================

param(
    [switch]$NoBuild,
    [switch]$Logs
)

$ErrorActionPreference = "Continue"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  TQQQ/SQQQ Pairs Trading - Webhook Stack  " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env has ngrok token
$envFile = Join-Path $PSScriptRoot ".env"
$envContent = Get-Content $envFile -Raw
if ($envContent -match "NGROK_AUTHTOKEN=\s*$" -or $envContent -match "NGROK_AUTHTOKEN=your-ngrok-authtoken") {
    Write-Host "ERROR: NGROK_AUTHTOKEN not set in .env file!" -ForegroundColor Red
    Write-Host "Get your token from: https://dashboard.ngrok.com/get-started/your-authtoken" -ForegroundColor Yellow
    Write-Host "Then update .env: NGROK_AUTHTOKEN=your-actual-token" -ForegroundColor Yellow
    exit 1
}

# Stop any existing containers
Write-Host "Stopping existing containers..." -ForegroundColor Yellow
docker compose down --remove-orphans 2>$null

# Build images
if (-not $NoBuild) {
    Write-Host ""
    Write-Host "Building images (no cache)..." -ForegroundColor Cyan
    docker compose build --no-cache
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Build failed!" -ForegroundColor Red
        exit 1
    }
}

# Start services
Write-Host ""
Write-Host "Starting services (webhook + ngrok)..." -ForegroundColor Cyan
docker compose up -d --remove-orphans
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start services!" -ForegroundColor Red
    exit 1
}

# Wait for containers to start
Write-Host ""
Write-Host "Waiting for containers to become healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 8

# Show container status
Write-Host ""
Write-Host "Container status:" -ForegroundColor Cyan
docker compose ps

# Show webhook logs
Write-Host ""
Write-Host "Webhook server logs:" -ForegroundColor Cyan
docker logs pairs-webhook --tail 20 2>&1

# Get ngrok public URL
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  DEPLOYMENT STATUS                         " -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

# Local endpoints
Write-Host ""
Write-Host "Local Endpoints:" -ForegroundColor Cyan
Write-Host "  Webhook Server: http://localhost:8080" -ForegroundColor White
Write-Host "  Ngrok Inspector: http://localhost:4040" -ForegroundColor White

# Get public URL from ngrok API
Write-Host ""
Write-Host "Public Webhook URL (for TradingView):" -ForegroundColor Cyan
$maxRetries = 5
$retryCount = 0
$publicUrl = $null

while ($retryCount -lt $maxRetries -and -not $publicUrl) {
    try {
        Start-Sleep -Seconds 2
        $tunnel = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:4040/api/tunnels" -ErrorAction Stop
        $publicUrl = $tunnel.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1 -ExpandProperty public_url
        if (-not $publicUrl) {
            $publicUrl = $tunnel.tunnels.public_url | Select-Object -First 1
        }
    } catch {
        $retryCount++
        Write-Host "  Waiting for ngrok tunnel... (attempt $retryCount/$maxRetries)" -ForegroundColor DarkYellow
    }
}

if ($publicUrl) {
    Write-Host ""
    Write-Host "  ┌─────────────────────────────────────────────────────────┐" -ForegroundColor Green
    Write-Host "  │  $publicUrl/webhook  │" -ForegroundColor Green
    Write-Host "  └─────────────────────────────────────────────────────────┘" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Copy this URL to TradingView Alert Webhook URL field" -ForegroundColor Yellow
} else {
    Write-Host "  Could not fetch ngrok URL. Check: http://localhost:4040" -ForegroundColor Red
}

# Test health endpoint
Write-Host ""
Write-Host "Testing webhook health..." -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Method Get -Uri "http://localhost:8080/health" -ErrorAction Stop
    Write-Host "  Status: $($health.status)" -ForegroundColor Green
    Write-Host "  Alpaca Connected: $($health.alpaca_connected)" -ForegroundColor Green
    Write-Host "  Account Equity: `$$($health.account.equity)" -ForegroundColor Green
    Write-Host "  Mode: $($health.mode)" -ForegroundColor Green
} catch {
    Write-Host "  Could not reach webhook server health endpoint" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  NEXT STEPS                                " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Copy the Pine Script to TradingView:" -ForegroundColor White
Write-Host "   tradingview\TQQQ_SQQQ_Pairs_Strategy.pine" -ForegroundColor Yellow
Write-Host ""
Write-Host "2. Add to TQQQ chart (5-minute timeframe)" -ForegroundColor White
Write-Host ""
Write-Host "3. Create Alert in TradingView:" -ForegroundColor White
Write-Host "   - Condition: TQQQ/SQQQ Pairs Z-Score" -ForegroundColor Yellow
Write-Host "   - Webhook URL: $publicUrl/webhook" -ForegroundColor Yellow
Write-Host ""
Write-Host "4. Monitor:" -ForegroundColor White
Write-Host "   - Logs: docker logs -f pairs-webhook" -ForegroundColor Yellow
Write-Host "   - Ngrok: http://localhost:4040" -ForegroundColor Yellow
Write-Host "   - Dashboard: streamlit run dashboard/src/app.py" -ForegroundColor Yellow
Write-Host ""

if ($Logs) {
    Write-Host "Following webhook logs (Ctrl+C to stop)..." -ForegroundColor Cyan
    docker logs -f pairs-webhook
}
