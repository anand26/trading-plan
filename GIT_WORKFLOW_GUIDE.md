# Git Workflow Guide - Feature Branch Creation Script

## Overview
The `create_feature_branch.ps1` script automates the feature branch creation workflow with optional feature naming.

## ✅ What Just Happened

1. **Everything Committed** to main branch:
   - All webhook server fixes
   - Timezone configuration
   - Dockerfile improvements
   - WebSocket error fixes
   - Database async operations

2. **Feature Branch Created**: `feature/webhook-websocket-fixes-2026-02-04`
   - Automatically named with timestamp
   - Ready for development

## 📝 Script Usage

### Basic Usage (Auto-generates name):
```powershell
.\create_feature_branch.ps1
```
**Output**: `feature/2026-02-04_1234-update`

### With Custom Feature Name:
```powershell
.\create_feature_branch.ps1 -FeatureName "add-auth-system"
```
**Output**: `feature/add-auth-system`

### With Spaces (auto-converted to dashes):
```powershell
.\create_feature_branch.ps1 -FeatureName "Add Multi Factor Auth"
```
**Output**: `feature/add-multi-factor-auth`

## 🔄 Script Workflow

The script automatically:

1. ✅ Validates git repository
2. ✅ Checks current branch (switches to main if needed)
3. ✅ Pulls latest changes from origin
4. ✅ Detects uncommitted changes
5. ✅ Prompts to commit changes if found
6. ✅ Sanitizes feature name (removes special chars, converts to lowercase)
7. ✅ Creates feature branch with `feature/` prefix
8. ✅ Shows commit history
9. ✅ Displays next steps

## 📋 Script Features

### Colors
- 🟢 Green = Success messages
- 🔴 Red = Errors
- 🔵 Cyan = Info messages
- 🟡 Yellow = Warnings

### Error Handling
- ❌ Validates git repository
- ❌ Handles branch switching failures
- ❌ Gracefully handles pull failures
- ❌ Sanitizes input names

### User Interaction
- Asks if you want to commit pending changes
- Shows current status
- Displays next steps with exact commands

## 🚀 Complete Development Workflow

### 1. Create Feature Branch
```powershell
# Option A: Auto-generated name
.\create_feature_branch.ps1

# Option B: Custom name
.\create_feature_branch.ps1 -FeatureName "webhooks-auth"
```

### 2. Make Your Changes
```
- Edit files
- Test changes
- Repeat as needed
```

### 3. Stage and Commit
```powershell
git add .
git commit -m "feat: Your feature description"
```

### 4. Push Branch
```powershell
git push origin <feature-branch-name>
```

### 5. Create Pull Request
- Go to GitHub
- Create PR from feature branch → main
- Add description and tests
- Request review

### 6. Merge and Cleanup
```powershell
# After PR approval and merge on GitHub
git checkout main
git pull origin main
git branch -d <feature-branch-name>
```

## 📊 Current Status

**Latest Commit:**
```
b3879df feat: Fix webhook server WebSocket errors and add timezone support
```

**Current Branch:**
```
feature/webhook-websocket-fixes-2026-02-04
```

**Changes Made:**
- ✅ Webhook server async refactoring
- ✅ Database connection cleanup
- ✅ Timeout protection (5 seconds)
- ✅ Dockerfile timezone configuration
- ✅ Optional zscore parameter handling
- ✅ Single worker configuration
- ✅ Feature branch creation script

## 💡 Tips & Best Practices

1. **Always use descriptive feature names**
   - ✅ Good: `fix-websocket-timeout`
   - ❌ Bad: `fix1`, `test`, `update`

2. **One feature per branch**
   - Keep branches focused and small
   - Easier to review and test

3. **Keep commits atomic**
   ```powershell
   git commit -m "fix: [issue] - [solution]"
   git commit -m "feat: [feature] - [description]"
   git commit -m "docs: [file] - [changes]"
   ```

4. **Sync frequently**
   ```powershell
   # From feature branch, pull latest main
   git fetch origin
   git rebase origin/main
   ```

5. **Never force push to main**
   ```powershell
   # Always use merge requests/PRs
   # Never do: git push origin main --force
   ```

## 🔧 Customization

To modify the script, edit these sections:

- **Thread pool size**: Change max_workers in webhook_server.py (line 48)
- **DB timeout**: Change TIMEOUT in database calls (currently 5 seconds)
- **Commit message prefix**: Add your custom convention
- **Branch prefix**: Currently uses `feature/` prefix

## ❓ Troubleshooting

### Script won't run
```powershell
# Allow script execution
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Branch already exists
```powershell
# Delete existing branch
git branch -d feature-name
git branch -D feature-name  # Force delete
```

### Uncommitted changes conflict
```powershell
# Stash changes temporarily
git stash
.\create_feature_branch.ps1
git stash pop  # Restore later
```

### Need to go back to main
```powershell
git checkout main
git pull origin main
```

## 📚 More Info

For detailed Git workflow:
- [Git Feature Branch Workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/feature-branch-workflow)
- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [Conventional Commits](https://www.conventionalcommits.org/)
