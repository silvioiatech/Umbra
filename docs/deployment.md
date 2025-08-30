# Production Deployment Guide

This guide covers deploying the Umbra Bot System to production using Railway.

## Railway Deployment

### Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **Domain** (optional): For custom webhooks
3. **S3/R2 Storage**: Cloudflare R2 or AWS S3 bucket
4. **API Keys**: OpenRouter, Telegram Bot, etc.

### Step 1: Prepare Environment Variables

Create environment variables for each service in Railway:

#### Umbra Service
```bash
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
```

#### Finance Service
```bash
NODE_ENV=production
PORT=8081
OPENROUTER_API_KEY=your_openrouter_key
STORAGE_ENDPOINT=https://your-bucket.r2.cloudflarestorage.com
STORAGE_ACCESS_KEY=your_r2_access_key
STORAGE_SECRET_KEY=your_r2_secret_key
STORAGE_BUCKET=umbra-production
UMBRA_API_KEY=same_as_finance_api_key_above
```

### Step 2: Deploy Services

1. **Connect Repository**: Link your GitHub repository to Railway

2. **Create Services**: Create separate Railway services for each module:
   - umbra (main agent)
   - finance
   - concierge (deploy to Railway, not VPS - VPS is only for n8n instances)
   - business
   - production
   - creator

3. **Configure Build**: Each service has a `railway.json` file with build configuration

4. **Deploy**: Railway will automatically deploy from your main branch

### Step 3: Set Up Service URLs

Update environment variables with the Railway service URLs:

```bash
# In Umbra service
FINANCE_URL=https://finance-production.railway.app
BUSINESS_URL=https://business-production.railway.app
PRODUCTION_URL=https://production-production.railway.app
CREATOR_URL=https://creator-production.railway.app
```

### Step 4: Configure Telegram Webhook

Set your Telegram webhook to point to the Umbra service:

```bash
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://umbra-production.railway.app/webhook/telegram",
    "allowed_updates": ["message", "callback_query"]
  }'
```

## VPS Purpose and Setup

**Important**: The VPS is only used for:
- n8n workflow instances (staging and production)
- Database server (optional, eventually)

All other services, including **Concierge**, deploy to Railway.

### Step 1: Prepare VPS for n8n

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Docker
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker $USER

# Install PM2 for process management
sudo npm install -g pm2
```

### Step 2: Deploy n8n Instances

```bash
# Create docker-compose.yml for n8n staging and production
mkdir -p ~/n8n-deployment
cd ~/n8n-deployment

# Create docker-compose configuration for n8n instances
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  n8n-staging:
    image: n8nio/n8n
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=your_secure_password
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
    volumes:
      - n8n_data_staging:/home/node/.n8n
    restart: unless-stopped

  n8n-production:
    image: n8nio/n8n
    ports:
      - "5679:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=your_secure_password
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
    volumes:
      - n8n_data_production:/home/node/.n8n
    restart: unless-stopped

volumes:
  n8n_data_staging:
  n8n_data_production:
EOF

# Start n8n instances
docker-compose up -d
```

### Step 3: Configure Firewall

```bash
# Allow SSH, HTTP, HTTPS, and n8n ports
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443  
sudo ufw allow 5678  # n8n staging
sudo ufw allow 5679  # n8n production
sudo ufw enable
```


## Database Setup (Optional)

For production scale, consider adding a database:

### PostgreSQL on Railway

1. **Add PostgreSQL**: Add a PostgreSQL service in Railway
2. **Get Connection String**: Copy the connection string
3. **Update Services**: Add database configuration to services that need it

```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

### Database Migration

```typescript
// Example database client setup
import { Pool } from 'pg';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
});
```

## Storage Configuration

### Cloudflare R2 Setup

1. **Create R2 Bucket**:
   - Go to Cloudflare Dashboard → R2
   - Create a new bucket: `umbra-production`

2. **Create API Token**:
   - Go to My Profile → API Tokens
   - Create token with R2 permissions

3. **Configure CORS**:
```json
[
  {
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3000
  }
]
```

### Lifecycle Policies

Set up lifecycle policies for automatic cleanup:

- **Temp files**: Delete after 7 days
- **Financial documents**: Delete after 90 days  
- **Media files**: Delete after 30 days

## Monitoring and Alerts

### Railway Monitoring

1. **Enable Metrics**: Turn on metrics in Railway dashboard
2. **Set Alerts**: Configure alerts for downtime and errors
3. **Resource Limits**: Set memory and CPU limits

### Custom Monitoring

```typescript
// Health check endpoint for monitoring
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    version: process.env.npm_package_version
  });
});
```

### External Monitoring

Set up external monitoring with services like:
- **UptimeRobot**: Free uptime monitoring
- **Pingdom**: Advanced monitoring and alerts  
- **DataDog**: Comprehensive APM (paid)

## Security Configuration

### Environment Variables

Never commit secrets to Git. Use Railway's environment variable management:

1. **Rotate Keys**: Regularly rotate API keys
2. **Least Privilege**: Give each service only necessary permissions
3. **Secure Storage**: Use Railway's built-in secret management

### API Security

```typescript
// Rate limiting
app.use(rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
}));

// CORS configuration
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || [],
  credentials: true
}));
```

### Network Security

1. **Private Networking**: Use Railway's private networking for service-to-service communication
2. **Webhook Validation**: Validate Telegram webhook signatures
3. **API Authentication**: Require API keys for all internal calls

## Backup and Recovery

### Database Backups

```bash
# Automated PostgreSQL backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Upload to R2
aws s3 cp backup_*.sql s3://umbra-backups/ --endpoint-url=https://your-account.r2.cloudflarestorage.com
```

### Configuration Backups

1. **Environment Variables**: Export and backup safely
2. **Service Configuration**: Keep `railway.json` in version control
3. **SSL Certificates**: Backup if using custom domains

## Scaling Considerations

### Horizontal Scaling

```json
// railway.json
{
  "deploy": {
    "numReplicas": 3,
    "restartPolicyType": "ON_FAILURE"
  }
}
```

### Load Balancing

Railway provides automatic load balancing for multiple replicas.

### Cache Layer

Add Redis for caching frequent requests:

```bash
# Add Redis service in Railway
REDIS_URL=redis://user:password@host:port
```

## Cost Optimization

### Railway Costs

- **Optimize Resources**: Right-size memory and CPU
- **Sleep Unused Services**: Enable sleep for dev environments
- **Monitor Usage**: Track resource consumption

### External API Costs

- **OpenRouter**: Monitor token usage
- **Storage**: Implement lifecycle policies
- **Bandwidth**: Use CDN for media files

### Cost Alerts

Set up billing alerts in Railway and external services.

## Troubleshooting

### Common Issues

1. **Service Communication**: Check API keys and service URLs
2. **Memory Limits**: Increase memory allocation if needed
3. **Build Failures**: Check Docker build logs
4. **Webhook Issues**: Verify Telegram webhook configuration

### Debugging Tools

```bash
# Railway CLI
railway logs --service umbra

# Local debugging
docker-compose logs -f umbra
```

### Performance Issues

1. **Monitor Response Times**: Set up APM monitoring
2. **Database Optimization**: Add indexes for frequent queries
3. **Caching**: Implement Redis caching for expensive operations

## Maintenance

### Regular Tasks

1. **Update Dependencies**: Monthly security updates
2. **Rotate Secrets**: Quarterly API key rotation
3. **Review Logs**: Weekly log analysis for issues
4. **Performance Review**: Monthly performance assessment

### Version Management

```bash
# Tag releases
git tag -a v1.0.0 -m "Production release v1.0.0"
git push origin v1.0.0

# Deploy specific version
railway deploy --service umbra --from-tag v1.0.0
```

## Support and Documentation

- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **Telegram Bot API**: [core.telegram.org/bots/api](https://core.telegram.org/bots/api)
- **OpenRouter API**: [openrouter.ai/docs](https://openrouter.ai/docs)

For technical support, create an issue in the repository with:
- Service logs
- Environment configuration (without secrets)
- Steps to reproduce the issue