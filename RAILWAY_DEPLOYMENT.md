# Railway Deployment Setup

## Quick Start

Deploy to Railway with these environment variables:

### Required
```
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
ALLOWED_USER_IDS=123,456,789
ALLOWED_ADMIN_IDS=999,888
```

### Optional  
```
PORT=8000
LOCALE_TZ=UTC
PRIVACY_MODE=true
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_DEFAULT_MODEL=anthropic/claude-3-haiku
R2_ACCOUNT_ID=your_cloudflare_r2_account
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET=umbra-storage
REDIS_URL=redis://localhost:6379
RATE_LIMIT_PER_MIN=30
```

## Health Endpoints

- `GET /health` - Health check with status, timestamp, request_id
- `GET /` - Service information

## Features

✅ **Structured JSON Logging** - All logs in JSON format with request_id, user_id, module, action, timestamp  
✅ **Request ID Tracking** - Unique request IDs for tracing  
✅ **Latency Monitoring** - Request latency tracking in milliseconds  
✅ **Security Headers** - X-Content-Type-Options, X-Frame-Options, X-XSS-Protection  
✅ **Graceful Shutdown** - SIGTERM/SIGINT handling  
✅ **Configuration Validation** - Fails fast on missing required config  
✅ **Docker Health Checks** - Built-in health endpoint for container orchestration  
✅ **Comprehensive Tests** - 20 pytest tests covering config, permissions, health endpoints  

## Testing

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set required environment variables
export TELEGRAM_BOT_TOKEN=your_token
export ALLOWED_USER_IDS=123,456
export ALLOWED_ADMIN_IDS=789

# Run locally
python main.py
```

Server will start on PORT (default: 8000) with structured JSON logging.