# UMBRA Feature Branch Seeding System

This directory contains GitHub Actions workflows and scripts for automatically seeding feature branches with development environment setup.

## Overview

When developers create new feature branches, the seeding system automatically:

- ✅ Sets up development environment templates
- ✅ Initializes directory structure  
- ✅ Validates dependencies and project setup
- ✅ Creates branch-specific documentation
- ✅ Prepares development database structure
- ✅ Provides testing scripts for MCP modules

## Workflows

### `seed-feature-branches.yml`
Main workflow that automatically triggers when feature branches are created or updated.

**Triggers:**
- Push to branches: `feature/*`, `feat/*`, `enhancement/*`, `dev/*`
- Branch creation for the same patterns
- Manual dispatch with optional parameters

**What it does:**
1. Detects if branch is a feature branch
2. Checks if already seeded (skips if so)
3. Installs Python dependencies
4. Runs project validation
5. Creates development environment template (`.env.dev`)
6. Initializes development directories
7. Sets up development database structure
8. Creates branch-specific documentation (`DEVELOPMENT.md`)
9. Commits seeding artifacts to the branch
10. Provides detailed summary report

### `test-seeding.yml`
Test workflow for validating the seeding process itself.

**Usage:**
- Run manually via GitHub Actions interface
- Tests all seeding components without affecting real branches
- Validates that seeding artifacts are created correctly

## Scripts

### `scripts/validate_branch_setup.py`
Comprehensive validation script that checks:
- Python version compatibility
- Project file structure
- Dependency availability
- UMBRA module imports
- Environment configuration
- Development directory structure
- Seeding status

**Usage:**
```bash
# Basic validation
python scripts/validate_branch_setup.py

# Quiet mode (only show results)
python scripts/validate_branch_setup.py --quiet

# Final validation with additional checks
python scripts/validate_branch_setup.py --final-check
```

### `scripts/init_dev_database.py`
Initializes development database with proper table structure for all MCP modules.

**Usage:**
```bash
python scripts/init_dev_database.py
```

**Creates tables for:**
- User management
- Conversation history
- System metrics
- Finance module (transactions, budgets)
- Business module (clients, projects)
- Production module (workflows)
- Creator module (content)
- Concierge module (monitoring)

### `scripts/test_modules.py`
Tests all MCP modules to ensure they work correctly.

**Usage:**
```bash
python scripts/test_modules.py
```

**Tests:**
- Module imports
- Module initialization
- Health checks
- Capability reporting
- Basic integration

## Branch Naming Conventions

The seeding system activates for branches matching these patterns:
- `feature/*` - New features
- `feat/*` - Alternative feature naming
- `enhancement/*` - Improvements to existing features
- `dev/*` - Development branches

Examples:
- ✅ `feature/add-new-mcp-module`
- ✅ `feat/telegram-improvements`
- ✅ `enhancement/better-finance-tracking`
- ✅ `dev/experimental-ai-features`
- ❌ `main` (not seeded)
- ❌ `bugfix/fix-typo` (not seeded)

## Files Created During Seeding

When a feature branch is seeded, these files are automatically created:

### `.env.dev`
Development environment template with:
- Debug log level
- Development database path
- Feature branch identification
- All configuration options from `.env.example`

### `DEVELOPMENT.md`
Branch-specific documentation including:
- Quick start guide
- Development database info
- Available scripts
- Module status overview
- Branch information and seeding timestamp

### `.github/.seeded`
Marker file indicating the branch has been seeded, containing:
- Branch name
- Seeding timestamp
- Workflow information

### Directory Structure
```
data/dev/          # Development data files
logs/dev/          # Development log files  
temp/dev/          # Development temporary files
```

## Manual Seeding

You can manually trigger seeding for any branch:

1. Go to GitHub Actions → "Seed Feature Branches"
2. Click "Run workflow"
3. Optionally specify branch name
4. Use "force_seed" to re-seed already seeded branches

## Seeding Status

Check if a branch has been seeded:
```bash
# Check for seeding marker
cat .github/.seeded

# Run validation to see overall status
python scripts/validate_branch_setup.py --quiet
```

## Troubleshooting

### Seeding Failed
1. Check the GitHub Actions logs for the specific error
2. Ensure branch name matches supported patterns
3. Verify repository permissions allow workflow execution

### Validation Failures
Most validation failures are due to missing environment variables, which is expected. To fix:
1. Copy `.env.dev` to `.env`: `cp .env.dev .env`
2. Edit `.env` with your actual Telegram bot credentials
3. Re-run validation: `python scripts/validate_branch_setup.py`

### Module Import Errors
If UMBRA modules fail to import:
1. Ensure all dependencies are installed: `pip install -r requirements.txt`
2. Check that you're in the project root directory
3. Verify Python version is 3.11+

## Configuration

The seeding system uses these environment variables (all optional):
- `DATABASE_PATH` - Database location (defaults to `data/umbra_dev.db`)
- `LOG_LEVEL` - Logging level (defaults to `DEBUG` for development)
- `ENVIRONMENT` - Environment name (set to `development`)

## Integration with UMBRA

The seeding system is designed specifically for the UMBRA MCP project and:
- Uses the existing project structure from `ACTION_PLAN.md`
- Validates against the architecture defined in `PROJECT_MAP.md`
- Works with all 5 MCP modules (Concierge, Finance, Business, Production, Creator)
- Follows the development patterns established in the project

## Benefits

✅ **Consistent Development Environment** - Every feature branch gets the same setup
✅ **Faster Onboarding** - New developers get working environment immediately  
✅ **Reduced Setup Errors** - Automated validation catches configuration issues
✅ **Documentation** - Each branch gets tailored development documentation
✅ **Testing Ready** - Modules are validated and ready for development
✅ **Isolated Development** - Separate database and logs for each feature branch