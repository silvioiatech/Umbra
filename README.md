# Umbra Complete - Monolithic Python Telegram Bot

A complete, all-in-one Telegram bot system implemented in Python with Finance, Business, Production, Creator, Concierge, and Monitoring modules.

> **🚀 NEW: Phase 1 Polling Bot Implementation Available!**
> 
> This repository now includes a new modular polling-based bot implementation in the `umbra/` package. 
> See the [Phase 1 Quick Start](#phase-1-python-bot-quick-start) section below for the new implementation.
> 
> The original FastAPI webhook implementation (`umbra_complete.py`) remains available for production use.

## 🚀 Phase 1 Python Bot - Quick Start

### Running the New Polling-Based Bot

The new `umbra/` package provides a polling-based bot implementation with modular architecture:

```bash
# Clone the repository
git clone https://github.com/silvioiatech/Umbra.git
cd Umbra

# Install Phase 1 dependencies
pip install -r requirements.txt

# Configure required environment variables
export TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"
export ALLOWED_USER_IDS="123456789,987654321"  # Your Telegram user IDs

# Run the new polling bot
python -m umbra.bot
```

### Phase 1 Features

- ✅ **Polling Mode**: No webhook setup required
- ✅ **Modular Architecture**: Clean module loading system
- ✅ **Structured Logging**: JSON-formatted logs with request tracing
- ✅ **Feature Flags**: Runtime feature toggles
- ✅ **Health Monitoring**: System status and metrics
- ✅ **Finance Module**: Document processing structure (Phase 2: full OCR)
- ✅ **Docker Support**: Production-ready containerization

### Phase 1 Available Commands

```
/start          - Welcome and status
/help           - Comprehensive help
health          - System health check  
status          - System information
uptime          - Bot uptime
finance help    - Finance module help
```

### Docker Deployment (Phase 1)

```bash
# Build the Phase 1 image
docker build -t umbra-bot:phase1 .

# Run with environment variables
docker run -e TELEGRAM_BOT_TOKEN=your_token \
           -e ALLOWED_USER_IDS=123456789 \
           -v $(pwd)/data:/app/data \
           umbra-bot:phase1
```

### Environment Configuration

**Required:**
```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ALLOWED_USER_IDS=123456789,987654321
```

**Optional (with sensible defaults):**
```bash
LOG_LEVEL=INFO
FEATURE_FINANCE_OCR=true
FEATURE_METRICS_COLLECTION=true
FINANCE_STORAGE_PATH=./finance_data
```

**Phase 1 Behavior:** Missing optional configuration produces warnings but doesn't stop the bot. Only missing required variables prevent startup.

---

## 🚀 Original FastAPI Implementation - Quick Start

### 1. Railway Deployment (Recommended)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template/umbra-complete)

1. **Click the Railway button above** or deploy manually
2. **Set environment variables** (see `.env.example`)
3. **Configure your Telegram bot token**
4. **Deploy automatically**

### 2. Local Development

```bash
# Clone the repository
git clone https://github.com/silvioiatech/Umbra.git
cd Umbra

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env

# Run the application
python umbra_complete.py
```

## 🤖 Features

### Core Modules

- **💬 Telegram Bot** - Multi-language support (EN/FR/PT) with intelligent intent routing
- **💰 Finance Module** - OCR document processing, expense categorization, financial reports
- **🏢 Business Module** - Client lifecycle management, project tracking
- **⚙️ Production Module** - AI-powered workflow creation and n8n integration  
- **🎨 Creator Module** - Multi-provider media generation (images, videos, audio)
- **📊 Concierge Module** - VPS management via SSH, container orchestration
- **📈 Monitoring Module** - System health checks, performance monitoring

### Key Capabilities

- **🧠 AI-Powered** - OpenRouter integration for intelligent responses
- **📄 OCR Processing** - Extract data from receipts, invoices, documents
- **🌍 Multi-Language** - Automatic language detection (English, French, Portuguese)
- **⚡ FastAPI Backend** - High-performance async web framework
- **📱 Telegram Integration** - Webhook-based bot with rich interactions
- **🔒 Secure** - Environment-based configuration, input validation
- **📊 Comprehensive Logging** - Structured JSON logging with audit trails

## ⚙️ Configuration

### Required Environment Variables

```bash
# Telegram Configuration
BOT_TOKEN=your_telegram_bot_token_here
WEBHOOK_URL=https://your-app.railway.app/webhook/telegram

# AI Configuration (Optional but recommended)
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### Optional Configuration

```bash
# Storage (S3/R2 Compatible)
STORAGE_ENDPOINT=https://your-s3-endpoint.com
STORAGE_ACCESS_KEY=your_access_key
STORAGE_SECRET_KEY=your_secret_key

# VPS Management (Concierge Module)
VPS_HOST=your_vps_ip
VPS_USERNAME=your_ssh_user
VPS_PRIVATE_KEY=your_ssh_private_key

# Media Generation (Creator Module)
RUNWAY_API_KEY=your_runway_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
```

See `.env.example` for complete configuration options.

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Start the application
python umbra_complete.py

# In another terminal, run tests
python test_umbra.py

# Or test a remote instance
python test_umbra.py https://your-app.railway.app
```

## 📱 Bot Commands

### General Commands
- `help` or `/start` - Show welcome message and available features
- `system status` - Check system health and uptime

### Finance Module
- Send receipts/invoices (images or PDFs) for automatic processing
- `budget report` - Generate expense analysis
- `finance help` - Show finance module capabilities

### Business Module  
- `create client [name]` - Create new client with VPS resources
- `list clients` - Show all active clients
- `project status` - Check project progress

### Production Module
- `create workflow [description]` - Generate automated workflow
- `list workflows` - Show active workflows
- `deploy workflow [name]` - Deploy to production

### Creator Module
- `generate image [description]` - Create AI-generated images
- `create video [description]` - Generate video content
- `make audio [description]` - Produce audio/voiceovers

## 🏗️ Architecture

### Monolithic Design
- **Single Python file** (`umbra_complete.py`) with all modules
- **FastAPI framework** for high-performance async web serving
- **Modular functions** organized by business capability
- **Shared utilities** for logging, AI, storage, and communication

### Module Structure
```
Umbra Complete
├── Telegram Handler (Intent Classification & Routing)
├── Finance Module (OCR, Categorization, Reporting)
├── Business Module (Client Management, Delegation)  
├── Production Module (Workflow Generation, n8n)
├── Creator Module (Media Generation, Multi-provider)
├── Concierge Module (VPS Management, SSH Operations)
└── Monitoring Module (Health Checks, System Status)
```

### API Endpoints
- `GET /` - Service information
- `GET /health` - Health check
- `POST /webhook/telegram` - Telegram webhook
- `POST /api/finance/process` - Document processing
- `POST /api/concierge/container` - Container management
- `GET /api/monitoring/status` - System monitoring

## 🚀 Deployment

### Railway (Recommended)
1. Connect your GitHub repository to Railway
2. Set environment variables from `.env.example`
3. Railway automatically detects and deploys Python apps
4. Configure Telegram webhook to point to your Railway URL

### Manual Deployment
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export BOT_TOKEN=your_token
export WEBHOOK_URL=https://yourdomain.com/webhook/telegram

# Run with production server
python umbra_complete.py
```

### Docker (Alternative)
```bash
# Build image
docker build -t umbra-complete .

# Run container
docker run -p 8080:8080 --env-file .env umbra-complete
```

## 🔧 Development

### Project Structure
```
Umbra/
├── umbra_complete.py    # Main application (all modules)
├── requirements.txt     # Python dependencies
├── test_umbra.py       # Comprehensive test suite
├── .env.example        # Environment template
├── Procfile           # Railway deployment config
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

### Adding Features
1. Extend the relevant module function in `umbra_complete.py`
2. Add intent classification keywords if needed
3. Update test cases in `test_umbra.py`
4. Test locally before deploying

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## 📊 Monitoring & Logging

### Health Monitoring
- `/health` endpoint for uptime monitoring
- Component status checks (Telegram, AI, Storage)
- System resource monitoring

### Logging
- Structured JSON logging
- Request/response audit trails
- Error tracking with context
- Performance metrics

### Observability
```bash
# Check application logs
python umbra_complete.py 2>&1 | jq

# Monitor health endpoint
curl https://your-app.railway.app/health | jq
```

## 🔐 Security

- **Environment-based configuration** - No secrets in code
- **Input validation** - Pydantic models for all data
- **Error handling** - Graceful degradation
- **Rate limiting** - Configurable request throttling
- **Audit logging** - All operations tracked

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: Create an issue in this repository
- **Documentation**: Check the inline code documentation
- **Community**: Telegram group (link in bot's /help command)

---

**Built with ❤️ using Python, FastAPI, and OpenRouter AI**