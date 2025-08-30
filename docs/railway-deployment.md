# Railway Deployment Guide for Umbra Bot System

This guide explains how to deploy the Umbra Bot System to Railway using the **one-click deployment** configuration.

## Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **GitHub Repository**: Connected to Railway
3. **Environment Variables**: Prepared for each service
4. **API Keys**: OpenRouter, Telegram Bot, S3/R2, etc.

## One-Click Deployment Steps

### 1. Connect Repository to Railway

1. Log in to Railway dashboard
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your Umbra repository
4. Railway will automatically detect the root `railway.json` configuration and deploy all 6 services

### 2. Automatic Service Creation

Railway will automatically create all 6 services from the root `railway.json`:

- **umbra** (port 8080) - Main Agent
- **finance** (port 8081) - Financial processing  
- **concierge** (port 9090) - VPS management (deploys to Railway)
- **business** (port 8082) - Client lifecycle
- **production** (port 8083) - Workflow creation
- **creator** (port 8084) - Media generation

### 3. Configure Environment Variables

For each service, add the environment variables from their respective `.env.example` files:

#### Umbra Service Variables
```
NODE_ENV=production
PORT=8080
BOT_TOKEN=your_telegram_bot_token
WEBHOOK_URL=https://umbra-production.railway.app/webhook/telegram
OPENROUTER_API_KEY=your_openrouter_key
STORAGE_ENDPOINT=https://your-s3-endpoint.com
STORAGE_ACCESS_KEY=your_access_key
STORAGE_SECRET_KEY=your_secret_key
STORAGE_BUCKET=umbra-storage
FINANCE_API_KEY=secure_finance_key
CONCIERGE_API_KEY=secure_concierge_key
```

#### Finance Service Variables
```
NODE_ENV=production
PORT=8081
OPENROUTER_API_KEY=your_openrouter_key
STORAGE_ENDPOINT=https://your-s3-endpoint.com
STORAGE_ACCESS_KEY=your_access_key
STORAGE_SECRET_KEY=your_secret_key
STORAGE_BUCKET=umbra-finance-storage
UMBRA_API_KEY=secure_finance_key
```

#### Concierge Service Variables
```
NODE_ENV=production
PORT=9090
VPS_HOST=your_vps_ip
VPS_USERNAME=your_ssh_user
VPS_PRIVATE_KEY=your_ssh_private_key
VPS_PORT=22
UMBRA_API_KEY=secure_concierge_key
```

### 4. Update Service URLs

After deployment, update the service URL environment variables in the Umbra service:

```
FINANCE_URL=https://finance-production.railway.app
CONCIERGE_URL=https://concierge-production.railway.app
```

### 5. Set Up Telegram Webhook

Configure your Telegram bot webhook to point to your Railway deployment:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://umbra-production.railway.app/webhook/telegram"}'
```

## Build Process

The multi-stage Docker builds will:

1. **Stage 1**: Build the shared package
   - Copy shared package files
   - Install dependencies
   - Build TypeScript

2. **Stage 2**: Build the service
   - Copy built shared package
   - Install service dependencies
   - Build service TypeScript

3. **Stage 3**: Create production image
   - Copy only built code and production dependencies
   - Install runtime dependencies (curl, etc.)
   - Set up health checks

## Monitoring

Each service includes health check endpoints:
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed health information

Monitor these endpoints to ensure services are running properly.

## Troubleshooting

### Build Issues
- Ensure all environment variables are set
- Check Railway build logs for specific errors
- Verify Docker build context includes all necessary files

### Service Communication
- Verify service URLs are correctly configured
- Check API key authentication between services
- Ensure services are deployed and healthy

### Common Issues
1. **Missing Environment Variables**: Check each service has required vars
2. **Build Context Errors**: Ensure using root directory as build context
3. **Port Conflicts**: Verify each service uses its designated port
4. **API Key Mismatches**: Ensure inter-service API keys match
5. **Nixpacks Auto-Detection**: If Railway uses Nixpacks instead of Dockerfiles, the `railway.toml` file forces Railway to use the multi-service configuration

### One-Click Deployment Notes
- Railway automatically deploys all 6 services from the root configuration
- Concierge service deploys to Railway (not VPS) - VPS is only for n8n instances

## Security Notes

- Use strong, unique API keys for inter-service communication
- Store sensitive data (SSH keys, API keys) in Railway environment variables
- Enable audit logging for production environments
- Regularly rotate API keys and credentials

## Support

For deployment issues:
1. Check Railway build and deployment logs
2. Verify environment variable configuration
3. Test service health endpoints
4. Review inter-service communication setup