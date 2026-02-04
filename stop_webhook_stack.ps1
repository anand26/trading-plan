# ============================================
# TQQQ/SQQQ Pairs Trading - Stop Docker Stack
# ============================================
# Stops all webhook + ngrok containers
# Usage: .\stop_webhook_stack.ps1
# ============================================

param(
    [switch]$RemoveVolumes
)

Write-Host "============================================" -ForegroundColor Yellow
Write-Host "  Stopping Webhook Stack...                 " -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow
Write-Host ""

# Show current status
Write-Host "Current containers:" -ForegroundColor Cyan
docker compose ps 2>$null

Write-Host ""
Write-Host "Stopping containers..." -ForegroundColor Yellow

if ($RemoveVolumes) {
    docker compose down --remove-orphans --volumes
} else {
    docker compose down --remove-orphans
}

Write-Host ""
Write-Host "Stack stopped." -ForegroundColor Green

# Check for any remaining webhook processes
$localWebhook = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*webhook*" }
if ($localWebhook) {
    Write-Host ""
    Write-Host "Note: Local webhook server still running (PID: $($localWebhook.Id))" -ForegroundColor Yellow
    Write-Host "Stop it with: Stop-Process -Id $($localWebhook.Id)" -ForegroundColor Yellow
}
