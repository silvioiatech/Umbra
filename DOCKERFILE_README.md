# Root Dockerfile Implementation Notes

This root Dockerfile was created to address Railway deployment errors caused by the absence of a root-level Dockerfile.

## Purpose
- **Primary**: Serve as a fallback when Railway doesn't properly detect the multi-service configuration from `railway.json`
- **Secondary**: Allow Railway to have a buildable Dockerfile at the root level for deployment detection

## How it works
1. Railway will first attempt to use the multi-service configuration defined in `railway.json`
2. If that fails, Railway can fall back to this root Dockerfile which builds the main umbra service
3. The existing individual service Dockerfiles in `services/*/Dockerfile` remain the preferred method for deployment

## Technical Details
- Builds the main umbra service (port 8080) as the primary application
- Uses the same build pattern as the individual service Dockerfiles
- Handles the monorepo structure by building the shared package first
- Copies the entire needed project structure for proper workspace resolution

## Deployment Priority
1. **Preferred**: Multi-service deployment via `railway.json` configuration
2. **Fallback**: Single service deployment via root `Dockerfile`

This minimal change ensures Railway deployment compatibility while maintaining the existing multi-service architecture.