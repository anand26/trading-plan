# =============================================================================
# TQQQ/SQQQ Pairs Strategy - Webhook Test Script
# =============================================================================
# Usage:
#   .\test_webhook.ps1                    # Run full test cycle (BUY + EXIT)
#   .\test_webhook.ps1 -Action BUY_TQQQ   # Test specific action
#   .\test_webhook.ps1 -Action BUY_SQQQ   # Test SQQQ buy
#   .\test_webhook.ps1 -Action EXIT       # Test exit
#   .\test_webhook.ps1 -Rollback          # Rollback database entries
#   .\test_webhook.ps1 -ClosePositions    # Close all Alpaca positions
# =============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("BUY_TQQQ", "BUY_SQQQ", "EXIT", "HEALTH", "POSITIONS", "")]
    [string]$Action = "",
    
    [switch]$Rollback,
    [switch]$ClosePositions,
    [switch]$FullCycle,
    
    [string]$NgrokUrl = "https://unemended-hae-semipathologically.ngrok-free.dev"
)

$Headers = @{
    "Content-Type" = "application/json"
    "ngrok-skip-browser-warning" = "true"
}

# Colors for output
function Write-Success { param($msg) Write-Host "[SUCCESS] $msg" -ForegroundColor Green }
function Write-Info { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warning { param($msg) Write-Host "[WARNING] $msg" -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

# =============================================================================
# DATABASE ROLLBACK FUNCTIONS
# =============================================================================

function Rollback-WebhookTestData {
    Write-Info "Rolling back webhook test data from database..."
    
    $query = @"
-- Rollback webhook test data
BEGIN TRANSACTION;

-- Get the webhook session IDs
DECLARE @SessionIds TABLE (SessionId VARCHAR(50));
INSERT INTO @SessionIds
SELECT SessionId FROM Sessions 
WHERE Notes LIKE '%webhook%' OR StrategyId = 'TQQQ_SQQQ_PAIRS';

-- Delete webhook events
DELETE FROM WebhookEvents WHERE SessionId IN (SELECT SessionId FROM @SessionIds);
PRINT 'Deleted WebhookEvents';

-- Delete signals from webhook
DELETE FROM Signals WHERE SessionId IN (SELECT SessionId FROM @SessionIds);
PRINT 'Deleted Signals';

-- Delete orders from webhook (by tag)
DELETE FROM Orders WHERE Tag LIKE '%Webhook%';
PRINT 'Deleted Orders with Webhook tag';

-- Delete the sessions
DELETE FROM Sessions WHERE SessionId IN (SELECT SessionId FROM @SessionIds);
PRINT 'Deleted Sessions';

-- Show counts
SELECT 'Remaining Sessions' as TableName, COUNT(*) as Count FROM Sessions WHERE StrategyId = 'TQQQ_SQQQ_PAIRS'
UNION ALL
SELECT 'Remaining WebhookEvents', COUNT(*) FROM WebhookEvents
UNION ALL  
SELECT 'Remaining Signals', COUNT(*) FROM Signals WHERE SessionId LIKE 'WH-%';

COMMIT TRANSACTION;
"@
    
    try {
        $result = Invoke-Sqlcmd -ServerInstance "localhost" -Database "TradingDB" -Query $query -TrustServerCertificate
        Write-Success "Database rollback completed!"
        $result | Format-Table -AutoSize
    }
    catch {
        Write-Err "Database rollback failed: $_"
    }
}

function Cancel-AllAlpacaOrders {
    Write-Info "Cancelling all pending Alpaca orders..."
    
    $url = "$NgrokUrl/cancel-all"
    try {
        $response = Invoke-RestMethod -Uri $url -Method POST -Headers $Headers
        Write-Success "Orders cancelled: $($response | ConvertTo-Json -Depth 3)"
    }
    catch {
        # Endpoint may not exist, try alternative approach
        Write-Warning "cancel-all endpoint not available. Check Alpaca dashboard manually."
    }
}

function Full-Rollback {
    Write-Info "=== FULL ROLLBACK: Alpaca + Database ==="
    
    # 1. Cancel pending orders in Alpaca
    Cancel-AllAlpacaOrders
    
    # 2. Close any positions
    Close-AllPositions
    
    # 3. Rollback database
    Rollback-WebhookTestData
    
    Write-Success "Full rollback completed!"
}

# =============================================================================
# ALPACA POSITION FUNCTIONS
# =============================================================================

function Close-AllPositions {
    Write-Info "Closing all Alpaca positions via webhook..."
    
    $url = "$NgrokUrl/close-all"
    try {
        $response = Invoke-RestMethod -Uri $url -Method POST -Headers $Headers
        Write-Success "Positions closed: $($response | ConvertTo-Json -Depth 3)"
    }
    catch {
        Write-Err "Failed to close positions: $_"
    }
}

function Get-CurrentPositions {
    Write-Info "Getting current Alpaca positions..."
    
    $url = "$NgrokUrl/positions"
    try {
        $response = Invoke-RestMethod -Uri $url -Method GET -Headers $Headers
        Write-Success "Current positions:"
        $response | ConvertTo-Json -Depth 3
    }
    catch {
        Write-Err "Failed to get positions: $_"
    }
}

# =============================================================================
# WEBHOOK TEST FUNCTIONS
# =============================================================================

function Test-Health {
    Write-Info "Testing webhook health..."
    
    $url = "$NgrokUrl/health"
    try {
        $response = Invoke-RestMethod -Uri $url -Method GET -Headers $Headers
        Write-Success "Webhook is healthy!"
        Write-Host "  Alpaca Connected: $($response.alpaca_connected)"
        Write-Host "  Account Equity: `$$($response.account.equity)"
        Write-Host "  Buying Power: `$$($response.account.buying_power)"
        Write-Host "  Current Position: $($response.current_position)"
        Write-Host "  Mode: $($response.mode)"
        return $true
    }
    catch {
        Write-Err "Health check failed: $_"
        return $false
    }
}

function Send-WebhookSignal {
    param(
        [string]$SignalAction,
        [float]$ZScore = 1.6,
        [float]$Ratio = 0.85,
        [float]$PositionSize = 0.57,
        [float]$StopLossPct = 0.02
    )
    
    Write-Info "Sending $SignalAction signal..."
    
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    
    $payload = @{
        action = $SignalAction
        zscore = $ZScore
        ratio = $Ratio
        position_size = $PositionSize
        stop_loss_pct = $StopLossPct
        timestamp = $timestamp
        strategy = "TQQQ_SQQQ_Pairs"
    } | ConvertTo-Json
    
    Write-Host "  Payload: $payload" -ForegroundColor Gray
    
    $url = "$NgrokUrl/webhook"
    try {
        $response = Invoke-RestMethod -Uri $url -Method POST -Body $payload -Headers $Headers
        
        if ($response.status -eq "executed") {
            Write-Success "$SignalAction executed!"
            Write-Host "  Order ID: $($response.order_id)"
            Write-Host "  Message: $($response.message)"
        }
        elseif ($response.status -eq "skipped") {
            Write-Warning "$SignalAction skipped: $($response.message)"
        }
        else {
            Write-Info "Response: $($response | ConvertTo-Json)"
        }
        return $response
    }
    catch {
        Write-Err "Webhook failed: $_"
        return $null
    }
}

# =============================================================================
# FULL CYCLE TEST
# =============================================================================

function Run-FullCycleTest {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host "  FULL CYCLE TEST: BUY_TQQQ -> EXIT" -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host ""
    
    # Step 1: Health check
    if (-not (Test-Health)) {
        Write-Err "Aborting: Webhook not healthy"
        return
    }
    Write-Host ""
    
    # Step 2: Check initial positions
    Write-Info "Checking initial positions..."
    Get-CurrentPositions
    Write-Host ""
    
    # Step 3: Send BUY_TQQQ signal
    Write-Host "--- Step 1: Buy TQQQ ---" -ForegroundColor Yellow
    $buyResult = Send-WebhookSignal -SignalAction "BUY_TQQQ" -ZScore 1.75 -Ratio 0.32
    Write-Host ""
    
    # Step 4: Poll for position (market orders may take time to fill, especially after hours)
    Write-Info "Polling for position to appear (max 60 seconds)..."
    $posUrl = "$NgrokUrl/positions"
    $maxAttempts = 12
    $attempt = 0
    $positionFound = $false
    
    while ($attempt -lt $maxAttempts -and -not $positionFound) {
        $attempt++
        Start-Sleep -Seconds 5
        try {
            $positions = Invoke-RestMethod -Uri $posUrl -Method GET -Headers $Headers
            if ($positions.count -gt 0) {
                $positionFound = $true
                Write-Success "Position found after $($attempt * 5) seconds!"
                Write-Host "  Position: $($positions.positions | ConvertTo-Json -Compress)" -ForegroundColor Gray
            } else {
                Write-Host "  Attempt $attempt/$maxAttempts - No position yet..." -ForegroundColor Gray
            }
        } catch {
            Write-Warning "  Attempt $attempt failed: $_"
        }
    }
    
    if (-not $positionFound) {
        Write-Err "Position not found after 60 seconds."
        Write-Warning "Note: Market may be closed. Paper trading only works during market hours (9:30 AM - 4:00 PM ET)"
        Write-Warning "Order may be queued and will fill when market opens."
        
        $continue = Read-Host "Continue with EXIT anyway? (yes/no)"
        if ($continue -ne "yes") {
            Write-Info "Test aborted. Run rollback to clean up database."
            return
        }
    }
    
    Write-Host ""
    
    # Step 5: Send EXIT signal
    Write-Host "--- Step 2: Exit Position ---" -ForegroundColor Yellow
    $exitResult = Send-WebhookSignal -SignalAction "EXIT" -ZScore 0.3 -Ratio 0.5
    Start-Sleep -Seconds 5
    Write-Host ""
    
    # Step 6: Check final positions
    Write-Info "Final positions:"
    Get-CurrentPositions
    Write-Host ""
    
    # Step 7: Ask about rollback
    Write-Host ""
    $doRollback = Read-Host "Roll back database entries? (yes/no)"
    if ($doRollback -eq "yes") {
        Rollback-WebhookTestData
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host "  FULL CYCLE TEST COMPLETE" -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  TQQQ/SQQQ Pairs Strategy - Webhook Tester" -ForegroundColor Cyan
Write-Host "  URL: $NgrokUrl" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Handle different modes
if ($Rollback) {
    Rollback-WebhookTestData
}
elseif ($ClosePositions) {
    Close-AllPositions
}
elseif ($Action -eq "HEALTH") {
    Test-Health
}
elseif ($Action -eq "POSITIONS") {
    Get-CurrentPositions
}
elseif ($Action -eq "BUY_TQQQ" -or $Action -eq "BUY_SQQQ" -or $Action -eq "EXIT") {
    Test-Health
    Write-Host ""
    Send-WebhookSignal -SignalAction $Action
}
elseif ($FullCycle -or $Action -eq "") {
    Run-FullCycleTest
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Quick Commands:" -ForegroundColor Cyan
Write-Host "    .\test_webhook.ps1                 # Full cycle test" -ForegroundColor Gray
Write-Host "    .\test_webhook.ps1 -Action BUY_TQQQ" -ForegroundColor Gray
Write-Host "    .\test_webhook.ps1 -Action EXIT" -ForegroundColor Gray
Write-Host "    .\test_webhook.ps1 -Rollback       # Clean database" -ForegroundColor Gray
Write-Host "    .\test_webhook.ps1 -ClosePositions # Close Alpaca" -ForegroundColor Gray
Write-Host "================================================" -ForegroundColor Cyan
