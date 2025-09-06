# 🤖 UMBRA - Enterprise Telegram Bot Framework

**Modular AI-powered Telegram bot with enterprise features and Swiss precision.**

UMBRA is a comprehensive, modular Telegram bot framework designed for business operations, featuring AI integration, object storage, and specialized modules for various business needs.

## 🌟 Key Features

### 🧠 **AI Integration (F3R1)**
- **OpenRouter Integration**: Access to 200+ AI models including Claude, GPT-4, and more
- **Multi-Role AI System**: Specialized AI agents (Planner, Builder, Controller, Chat)
- **Intelligent Conversations**: Context-aware responses with conversation history
- **Streaming Support**: Real-time AI responses

### 🗄️ **Object Storage (F4R2)**
- **Cloudflare R2 Integration**: S3-compatible object storage with global edge
- **JSONL Manifests**: Real-time data streams with ETag concurrency control
- **Search Capabilities**: Full-text search across stored documents
- **Secure Access**: Presigned URLs with time-limited access

### 🏗️ **Modular Architecture**
- **Business Module**: Client instance management and operations
- **Concierge Module**: System administration and monitoring
- **Finance Module**: Personal finance tracking and analytics
- **Creator Module**: Content generation and management
- **Production Module**: Workflow automation and n8n integration

### 🔒 **Enterprise Features**
- **Role-Based Access Control**: User and admin permission management
- **Rate Limiting**: Protection against abuse and API overuse
- **Comprehensive Logging**: Structured logging with context tracking
- **Health Monitoring**: Built-in health checks and status reporting
- **Multi-User Support**: Secure user management with ID whitelisting

## 🚀 Quick Start

### 1. Installation

```bash
git clone <repository-url>
cd UMBRA
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
# Edit .env with your credentials
```

**Required Configuration:**
```bash
# Telegram Bot (Required)
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
ALLOWED_USER_IDS=123456789,987654321
ALLOWED_ADMIN_IDS=123456789

# Optional Features
OPENROUTER_API_KEY=your_openrouter_api_key  # For AI features
R2_ACCOUNT_ID=your_cloudflare_account_id    # For object storage
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET=your_bucket_name
```

### 3. Testing

```bash
# Run tests to validate setup
python -m pytest tests/ -v

# Or run individual demos
python demos/demo_mvp.py
python demos/f4r2_demo.py
```

### 4. Run the Bot

```bash
python main.py
```

## 📋 Available Commands

### 🤖 **Core Commands**
- `/start` - Initialize bot and show welcome message
- `/help` - Display available commands and features
- `/status` - Show system health and feature availability

### 🧠 **AI Commands (F3R1)**
- `/chat <message>` - Chat with AI assistant
- `/plan <task>` - AI task planning and analysis
- `/generate <description>` - AI content generation

### 💼 **Business Operations**
- `/instance` - Manage client instances
- `/workflow` - Access workflow automation
- `/health` - System health monitoring

### 💰 **Finance Module**
- `/expense <amount> <description>` - Track expenses
- `/budget` - View budget overview
- `/analytics` - Financial analytics

## 🏗️ Project Structure

```
UMBRA/
├── umbra/                  # Main package
│   ├── core/              # Core framework components
│   ├── modules/           # Feature modules
│   ├── storage/           # Object storage integration
│   ├── ai/               # AI integration components
│   ├── providers/        # External service providers
│   └── utils/            # Shared utilities
├── tests/                 # Test suite
├── demos/                 # Example scripts and demos
├── scripts/              # Utility scripts
├── docs/                 # Documentation
├── main.py               # Application entry point
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🔧 Module Overview

### Core Framework
- **Bot**: Main bot orchestrator and message handling
- **Router**: Command routing and middleware
- **Config**: Environment-based configuration management
- **Logger**: Structured logging with context tracking
- **Permissions**: User authorization and access control

### Business Modules
- **ConciergeMCP**: System administration and monitoring
- **BusinessMCP**: Client instance management
- **FinanceMCP**: Personal finance tracking
- **CreatorMCP**: Content generation and brand management
- **ProductionModule**: Workflow automation

### Storage Layer
- **Object Storage**: File storage and retrieval
- **Manifest Manager**: JSONL data streaming
- **Search Index**: Full-text search capabilities
- **R2 Client**: Cloudflare R2 integration

### AI Integration
- **Agent**: AI agent coordination
- **OpenRouter Provider**: Access to multiple AI models
- **Conversation**: Context management and history

## 🚀 Deployment

### Railway (Recommended)
1. Connect your GitHub repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically on push

### Docker
```bash
docker build -t umbra .
docker run -d --env-file .env --name umbra umbra
```

### Manual Server Deployment
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
export TELEGRAM_BOT_TOKEN=your_token
export ALLOWED_USER_IDS=your_user_ids

# Run with systemd or supervisor
python main.py
```

## 🧪 Testing

### Run All Tests
```bash
# Full test suite
python -m pytest tests/ -v

# With coverage
python -m pytest --cov=umbra tests/ -v

# Specific test categories
python -m pytest tests/test_*_integration.py -v
```

### Manual Testing
```bash
# Test AI integration
python demos/f4r2_demo.py

# Test storage features
python demos/demo_r2_storage.py

# Validate configuration
python demos/f4r2_validate.py
```

## 📚 Documentation

- **Module Development**: See individual module documentation in `umbra/modules/`
- **API Reference**: Generated from docstrings using Sphinx
- **Deployment Guide**: Railway and Docker deployment instructions
- **Configuration**: Environment variable reference in `.env.example`

## 🔒 Security Features

### Access Control
- User ID whitelist management
- Admin role separation
- Command-level permissions
- Rate limiting protection

### Data Protection
- Secure credential management
- Encrypted communication channels
- Audit logging for sensitive operations
- Secure file storage with presigned URLs

## 🐛 Troubleshooting

### Common Issues

**Bot not responding:**
```bash
# Check configuration
echo $TELEGRAM_BOT_TOKEN
python -c "import umbra; print('✅ Package imports successfully')"
```

**Import errors:**
```bash
# Install missing dependencies
pip install -r requirements.txt

# Check Python version (3.8+ required)
python --version
```

**Module-specific issues:**
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py
```

### Debug Mode
Set `LOG_LEVEL=DEBUG` in your environment to enable detailed logging for troubleshooting.

## 🤝 Contributing

### Development Setup
```bash
# Clone and setup
git clone <repository-url>
cd UMBRA
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Check code style
python -m flake8 umbra/
```

### Guidelines
1. **Code Quality**: Follow PEP 8 and add type hints
2. **Testing**: Write tests for new features
3. **Documentation**: Update docstrings and README
4. **Modular Design**: Keep modules independent and focused

## 📈 Roadmap

### Completed ✅
- Core bot framework with modular architecture
- AI integration with OpenRouter
- Object storage with Cloudflare R2
- User management and permissions
- Health monitoring and logging

### In Progress 🔄
- Enhanced business module features
- Improved analytics and reporting
- Extended AI capabilities
- Documentation improvements

### Planned 📋
- Web dashboard interface
- Mobile companion app
- Additional AI model integrations
- Advanced workflow automation

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Cloudflare** for R2 object storage
- **OpenRouter** for AI model access  
- **Railway** for deployment platform
- **Python Telegram Bot** for the framework
- **The open source community** for inspiration and tools

---

**Built with Swiss precision for enterprise scale. 🇨🇭**

For detailed documentation on specific features, see the `docs/` directory.