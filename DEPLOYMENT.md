# Complete Deployment Guide - Umbra Bot System

This guide covers deploying the complete 7-service Umbra Bot system to Railway.

## Prerequisites

### Required External Services

1. **Telegram Bot Token**: Create a bot via @BotFather
2. **OpenRouter Account**: Sign up at https://openrouter.ai for LLM access
3. **Storage Provider**: Cloudflare R2 or AWS S3 compatible storage
4. **VPS Access**: SSH credentials for the VPS that Concierge will manage
5. **n8n Instance**: Self-hosted or n8n.cloud for workflow management

### Optional Media Providers

- **Runway**: Text-to-video generation
- **Shotstack**: Video editing capabilities  
- **ElevenLabs**: Text-to-speech synthesis

## Railway Deployment Steps

### 1. Connect Repository

1. Go to https://railway.app and create a new project
2. Connect your GitHub repository
3. Railway will automatically detect the `railway.json` configuration

### 2. Deploy All Services

Railway will create all 6 services based on the configuration:

- **umbra** (port 8080) - Main Agent
- **finance** (port 8081) - Financial processing
- **concierge** (port 9090) - VPS management (deploys to Railway, not VPS)
- **business** (port 8082) - Client lifecycle
- **production** (port 8083) - Workflow creation
- **creator** (port 8084) - Media generation

**Note**: MCP service is hosted externally and not deployed to Railway

### 3. Configure Environment Variables

For each service, add the required environment variables. Here's the breakdown:

#### Umbra Service (Main Agent)
```
NODE_ENV=production
PORT=8080
BOT_TOKEN=your_telegram_bot_token
WEBHOOK_URL=https://umbra-production.railway.app/webhook/telegram
OPENROUTER_API_KEY=your_openrouter_key
STORAGE_ENDPOINT=https://your-bucket.r2.cloudflarestorage.com
STORAGE_ACCESS_KEY=your_r2_access_key
STORAGE_SECRET_KEY=your_r2_secret_key
STORAGE_BUCKET=umbra-production
FINANCE_API_KEY=generate_secure_key
CONCIERGE_API_KEY=generate_secure_key
BUSINESS_API_KEY=generate_secure_key
PRODUCTION_API_KEY=generate_secure_key
CREATOR_API_KEY=generate_secure_key
MCP_API_KEY=generate_secure_key
```

#### Finance Service
```
NODE_ENV=production
PORT=8081
OPENROUTER_API_KEY=your_openrouter_key
STORAGE_ENDPOINT=https://your-bucket.r2.cloudflarestorage.com
STORAGE_ACCESS_KEY=your_r2_access_key
STORAGE_SECRET_KEY=your_r2_secret_key
STORAGE_BUCKET=umbra-finance-storage
UMBRA_API_KEY=same_as_finance_key_above
```

#### Concierge Service (VPS Management)
```
NODE_ENV=production
PORT=9090
VPS_HOST=your.vps.ip.address
VPS_USERNAME=your_vps_username
VPS_PRIVATE_KEY=your_vps_private_key_content
VPS_PORT=22
UMBRA_API_KEY=same_as_concierge_key_above
BUSINESS_API_KEY=same_as_business_key_above
```

#### Business Service
```
NODE_ENV=production
PORT=8082
UMBRA_API_KEY=same_as_business_key_above
CONCIERGE_API_KEY=same_as_concierge_key_above
PRODUCTION_API_KEY=same_as_production_key_above
CONCIERGE_URL=https://concierge-production.railway.app
PRODUCTION_URL=https://production-production.railway.app
```

#### Production Service
```
NODE_ENV=production
PORT=8083
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=https://umbra.ai
MCP_URL=https://your-external-mcp-service.com
UMBRA_API_KEY=same_as_production_key_above
BUSINESS_API_KEY=same_as_business_key_above
MCP_API_KEY=your_external_mcp_api_key
```

#### Creator Service
```
NODE_ENV=production
PORT=8084
OPENROUTER_API_KEY=your_openrouter_key
RUNWAY_API_KEY=your_runway_key
SHOTSTACK_API_KEY=your_shotstack_key
ELEVENLABS_API_KEY=your_elevenlabs_key
STORAGE_ENDPOINT=https://your-bucket.r2.cloudflarestorage.com
STORAGE_ACCESS_KEY=your_r2_access_key
STORAGE_SECRET_KEY=your_r2_secret_key
STORAGE_BUCKET=umbra-media
BOT_TOKEN=your_telegram_bot_token
UMBRA_API_KEY=same_as_creator_key_above
```

**Note**: MCP service is hosted externally. Configure your external MCP service with the n8n instance URLs from your VPS.

### 4. Generate API Keys

Generate secure random keys for inter-service communication:

```bash
# Use a secure random generator
openssl rand -hex 32  # Generate 64-character hex key
```

Use the same key values across services that need to communicate.

### 5. Configure Service URLs

Update service environment variables with actual Railway URLs:

1. Get the deployed URLs from Railway dashboard
2. Update `CONCIERGE_URL`, `PRODUCTION_URL`, `MCP_URL` variables
3. Set the main `WEBHOOK_URL` for Telegram

### 6. Set Up Telegram Webhook

After deployment, configure the Telegram webhook:

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://umbra-production.railway.app/webhook/telegram"}'
```

## Verification Steps

### 1. Health Checks

Verify all services are running:

```bash
curl https://umbra-production.railway.app/health
curl https://finance-production.railway.app/health  
curl https://concierge-production.railway.app/health
curl https://business-production.railway.app/health
curl https://production-production.railway.app/health
curl https://creator-production.railway.app/health
```

### 2. Test Telegram Bot

1. Send `/start` to your bot
2. Upload a receipt/invoice for OCR testing
3. Try different languages (EN/FR/PT)

### 3. Service Communication

Test inter-service communication by checking logs in Railway dashboard.

## Monitoring & Maintenance

### Logs

Monitor logs via Railway dashboard for each service:
- Check for authentication errors between services
- Monitor API rate limits and provider errors
- Watch for VPS connection issues (Concierge)

### Scaling

Adjust replicas in Railway dashboard based on usage:
- Umbra: Scale based on Telegram traffic
- Finance: Scale based on OCR processing load
- Creator: Scale based on media generation requests

### Updates

Deploy updates via Railway:
1. Push changes to your repository
2. Railway automatically redeploys affected services
3. Monitor deployment logs for issues

## Security Considerations

1. **Rotate API Keys**: Regularly rotate all inter-service API keys
2. **VPS Access**: Ensure VPS private key is securely stored
3. **Rate Limiting**: Monitor and adjust rate limits based on usage
4. **Storage**: Use signed URLs and implement PII redaction
5. **Webhook Security**: Validate Telegram webhook signatures

## Troubleshooting

### Common Issues

1. **Service Communication Failures**
   - Check API keys match between services
   - Verify service URLs are correct
   - Check Railway networking

2. **VPS Connection Issues**
   - Verify VPS credentials in Concierge service
   - Check SSH key format and permissions
   - Test VPS connectivity

3. **Provider API Failures**
   - Check API key validity
   - Monitor rate limits
   - Implement circuit breakers

4. **Telegram Issues**
   - Verify webhook URL is accessible
   - Check bot token validity
   - Monitor webhook signature validation

For additional support, check service logs and Railway documentation.