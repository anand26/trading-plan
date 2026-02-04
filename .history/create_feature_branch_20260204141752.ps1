# ============================================================================
# Git Workflow Tool - Feature Branch Creator & Code Check-in
# ============================================================================
# Usage: 
#   .\create_feature_branch.ps1 -FeatureName "your-feature-name"  (Create feature branch)
#   .\create_feature_branch.ps1 -CheckinOnly                       (Simple code check-in)
#   .\create_feature_branch.ps1                                    (Interactive mode)
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$FeatureName = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$CheckinOnly = $false
)

# Colors for output
$successColor = "Green"
$errorColor = "Red"
$infoColor = "Cyan"
$warningColor = "Yellow"

function Write-Success {
    param([string]$Message)
    Write-Host $Message -ForegroundColor $successColor
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host $Message -ForegroundColor $errorColor
}

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor $infoColor
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host $Message -ForegroundColor $warningColor
}

# Check if we're in a git repository
try {
    git rev-parse --git-dir | Out-Null
} catch {
    Write-Error-Custom "Not a git repository! Please run this script from the project root."
    exit 1
}

Write-Info "============================================"
Write-Info "Git Workflow Tool"
Write-Info "============================================"

# CODE CHECK-IN ONLY MODE - No feature branch
if ($CheckinOnly) {
    Write-Info "`nCode Check-in Mode (current branch)"
    $currentBranch = git rev-parse --abbrev-ref HEAD
    Write-Info "Current branch: $currentBranch"
    
    # Check for uncommitted changes
    $status = git status --porcelain
    if (-not $status) {
        Write-Warning-Custom "No uncommitted changes found!"
        exit 0
    }
    
    Write-Warning-Custom "Uncommitted changes detected:"
    Write-Host $status
    
    Write-Info "`nProcessing check-in..."
    git add -A
    Write-Success "Changes staged"
    
    $commitMsg = Read-Host "Enter commit message (default: 'chore: Code check-in')"
    if ([string]::IsNullOrWhiteSpace($commitMsg)) {
        $commitMsg = "chore: Code check-in - $(Get-Date -Format 'yyyy-MM-dd HHmm')"
    }
    
    git commit -m $commitMsg
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Commit failed"
        exit 1
    }
    
    Write-Success "Changes committed"
    
    Write-Info "`nPushing to GitHub..."
    git push origin $currentBranch
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Warning: Could not push to GitHub"
    } else {
        Write-Success "Pushed to GitHub"
    }
    
    Write-Info "`n============================================"
    Write-Success "Code check-in completed!"
    Write-Info "============================================"
    Write-Info "`nTo create a feature branch next time, use:"
    Write-Info "   .\create_feature_branch.ps1 -FeatureName 'your-feature'"
    Write-Info "============================================"
    exit 0
}

# FEATURE BRANCH CREATION MODE
Write-Info "Feature Branch Creator"
Write-Info "============================================"

# Verify we're on main branch
$currentBranch = git rev-parse --abbrev-ref HEAD
if ($currentBranch -ne "main") {
    Write-Warning-Custom "Currently on branch: $currentBranch"
    Write-Info "Switching to main branch..."
    git checkout main
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Failed to switch to main branch"
        exit 1
    }
}

Write-Info "On main branch"

# Pull latest changes
Write-Info "Pulling latest changes from main..."
git pull origin main
if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Warning: Could not pull latest changes"
}

# Check for uncommitted changes
$status = git status --porcelain
if ($status) {
    Write-Warning-Custom "You have uncommitted changes:"
    Write-Host $status
    $commit = Read-Host "Do you want to commit these changes before creating feature branch? (yes/no)"
    
    if ($commit -eq "yes" -or $commit -eq "y") {
        git add -A
        $commitMsg = Read-Host "Enter commit message (default: 'WIP: Checkpoint commit')"
        if ([string]::IsNullOrWhiteSpace($commitMsg)) {
            $commitMsg = "WIP: Checkpoint commit"
        }
        
        git commit -m $commitMsg
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Commit failed"
            exit 1
        }
        Write-Success "Changes committed"
    } else {
        Write-Warning-Custom "Skipping commit - proceeding with feature branch creation"
    }
}

# Generate feature branch name
if ([string]::IsNullOrWhiteSpace($FeatureName)) {
    # Auto-generate from timestamp
    $timestamp = Get-Date -Format "yyyy-MM-dd_HHmm"
    $FeatureName = "feature/$timestamp-update"
    Write-Info "No feature name provided. Using auto-generated name: $FeatureName"
} else {
    # Sanitize feature name
    $FeatureName = $FeatureName.ToLower() -replace '[^a-z0-9\-_]', '-'
    $FeatureName = "feature/$FeatureName"
}

# Create and switch to feature branch
Write-Info "Creating feature branch: $FeatureName"
git checkout -b $FeatureName
if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Failed to create feature branch"
    exit 1
}

Write-Success "Feature branch created: $FeatureName"

Write-Info "`nCurrent Status:"
git log --oneline -3
Write-Info "`nBranch Information:"
git branch -v

# Push feature branch to GitHub
Write-Info "`nPushing branch to GitHub..."
git push -u origin $FeatureName
if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Failed to push branch to GitHub"
    exit 1
}

Write-Success "Branch pushed to GitHub"

Write-Info "`n============================================"
Write-Success "Feature branch ready for development!"
Write-Success "GitHub: https://github.com/anand26/trading-plan/tree/$FeatureName"
Write-Info "============================================"
Write-Info "`nNext steps:"
Write-Info "1. Make your changes locally"
Write-Info "2. Stage changes:        git add ."
Write-Info "3. Commit changes:       git commit -m 'Your message'"
Write-Info "4. Push commits:         git push origin $FeatureName"
Write-Info "5. Create Pull Request on GitHub"
Write-Info "`nFor quick code check-in (no feature branch):"
Write-Info "   .\create_feature_branch.ps1 -CheckinOnly"
Write-Info "`nTo undo and go back to main:"
Write-Info "   git checkout main"
Write-Info "   git branch -d $FeatureName"
Write-Info "   git push origin --delete $FeatureName"
Write-Info "============================================"
