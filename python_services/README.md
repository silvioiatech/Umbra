# Umbra Bot System - Python Implementation

Complete Python conversion of the Umbra bot system, maintaining all functionality from the original Node.js/TypeScript implementation while providing improved performance and maintainability.

## 🐍 Python Implementation Highlights

### Technology Stack
- **FastAPI** - High-performance async web framework
- **Pydantic** - Robust data validation and serialization
- **Structlog** - Structured JSON logging
- **httpx** - Modern async HTTP client
- **pytesseract** - OCR processing
- **OpenCV** - Image preprocessing
- **boto3** - S3/R2 storage integration
- **paramiko** - SSH operations

### Architecture Overview

The Python implementation mirrors the original 6-service architecture:

1. **Umbra Main Agent** (Port 8080) - Entry point with Telegram integration
2. **Finance Module** (Port 8081) - OCR processing and financial document extraction  
3. **Concierge Module** (Port 9090) - VPS management via SSH
4. **Business Module** (Port 8082) - Client lifecycle management
5. **Production Module** (Port 8083) - Workflow creation using AI pipeline
6. **Creator Module** (Port 8084) - Multi-provider media generation

## 🚀 Quick Start

### Local Development

1. **Clone and setup**:
```bash
cd python_services
```

2. **Install shared package**:
```bash
cd shared
pip install -e .
cd ..
```

3. **Install and run each service**:
```bash
# Umbra Main Agent
cd umbra
pip install -e .
cp ../../.env.python.example .env
# Edit .env with your configuration
uvicorn umbra_service.main:app --host 0.0.0.0 --port 8080 --reload

# Finance Module  
cd ../finance
pip install -e .
uvicorn finance_service.main:app --host 0.0.0.0 --port 8081 --reload
```

### Railway Deployment

1. **Use Python railway configuration**:
```bash
cp railway-python.json railway.json
```

2. **Set environment variables** in Railway dashboard:
```bash
# Use .env.python.example as reference
# Set all required variables for each service
```

3. **Deploy**:
```bash
# Railway will automatically detect railway.json and deploy all 6 Python services
```

## 📋 Service Details

### Umbra Main Agent (Port 8080)
- **Intent Classification**: Pattern matching + OpenRouter AI fallback
- **Module Routing**: Health checks, failover, load balancing
- **Task Execution**: Math, translations, help, general queries
- **Telegram Integration**: Webhook handling, multi-language support
- **Authentication**: Internal service auth, webhook validation

**Key Features**:
- Multi-language support (EN/FR/PT)
- Intelligent intent classification with confidence scoring
- Automatic module health monitoring
- Comprehensive error handling and retry logic

### Finance Module (Port 8081)
- **Advanced OCR**: pytesseract with OpenCV preprocessing
- **AI Enhancement**: OpenRouter vision models for data extraction
- **Financial Intelligence**: Automatic categorization, VAT calculation
- **Report Generation**: Budget, VAT, tax, expense analysis
- **Data Validation**: Anomaly detection, confidence scoring

**Supported Formats**:
- Images: PNG, JPG, GIF, BMP, TIFF, WebP
- PDFs: Text extraction + OCR fallback for scanned documents

**OCR Pipeline**:
1. Image preprocessing (grayscale, blur, threshold, morphology)
2. Tesseract OCR with optimized configuration
3. AI-enhanced structured data extraction
4. Financial categorization and validation
5. Anomaly detection and confidence scoring

### Shared Package (umbra-shared)
- **Type System**: Pydantic models for all envelopes and payloads
- **Clients**: OpenRouter, Telegram, Storage (S3/R2)
- **Middleware**: Authentication, validation, audit logging
- **Utilities**: Retry logic, structured logging, error handling

## 🛠️ Development

### Project Structure
```
python_services/
├── shared/                    # Shared utilities and types
│   └── umbra_shared/
│       ├── types.py          # Pydantic models
│       ├── openrouter_client.py
│       ├── telegram_client.py
│       ├── storage_client.py
│       ├── middleware.py
│       ├── logger.py
│       └── retry.py
├── umbra/                    # Main agent service
│   └── umbra_service/
│       ├── routing/          # Intent classification & module routing
│       ├── handlers/         # Task execution
│       ├── telegram/         # Telegram bot handling
│       └── main.py
├── finance/                  # Finance module
│   └── finance_service/
│       ├── ocr/             # OCR processing
│       ├── extraction/      # Data extraction & categorization
│       ├── reports/         # Report generation
│       └── main.py
└── [other services]/
```

### Running Tests
```bash
# Install test dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run with coverage
pytest --cov=umbra_service tests/
```

### Code Quality
```bash
# Format code
black .

# Lint code  
ruff check .

# Type checking
mypy .
```

## 🔧 Configuration

### Environment Variables

Copy `.env.python.example` to `.env` and configure:

**Required for all services**:
- `OPENROUTER_API_KEY` - OpenRouter AI API key
- `BOT_TOKEN` - Telegram bot token (for Umbra service)

**Optional but recommended**:
- `STORAGE_ENDPOINT` - S3/R2 compatible storage endpoint
- `STORAGE_ACCESS_KEY` - Storage access key
- `STORAGE_SECRET_KEY` - Storage secret key

**Service-specific**:
- See `.env.python.example` for complete configuration options

### API Keys and Authentication

1. **Internal Service Authentication**: Each service validates requests using API keys
2. **Telegram Webhook**: Validates webhook secret token
3. **OpenRouter**: Requires valid API key for AI processing
4. **Storage**: S3/R2 compatible storage for document and report storage

## 📊 Monitoring and Logging

### Structured Logging
All services use structured JSON logging with:
- Request tracing via `req_id`
- User context tracking
- Performance metrics
- Error tracking with full context

### Health Checks
- `/health` and `/healthz` endpoints on all services
- Service dependency health monitoring
- Automatic failover and retry logic

### Metrics
- Request duration tracking
- AI token usage monitoring
- OCR processing statistics
- Error rates and patterns

## 🔄 Migration from Node.js

### Feature Parity
✅ **Complete feature parity** with Node.js implementation:
- All 6 services converted
- Same API contracts and envelope system
- Identical functionality and behavior
- Multi-language support maintained

### Performance Improvements
- **Async Processing**: Full async/await throughout
- **Better Resource Management**: Automatic connection pooling
- **Optimized OCR**: Enhanced image preprocessing
- **Improved Error Handling**: Comprehensive retry logic

### Deployment Compatibility
- **Same Railway Configuration**: Drop-in replacement
- **Environment Variables**: Compatible with existing setup
- **API Compatibility**: Maintains all existing endpoints

## 🛡️ Security

### Authentication & Authorization
- Service-to-service authentication via API keys
- Telegram webhook signature validation
- User access control with allow-lists

### Data Protection
- PII minimization in logs
- Secure storage with encryption
- Audit trails for all operations
- GDPR compliance features

### Network Security
- CORS configuration
- Rate limiting
- Input validation and sanitization
- Secure headers middleware

## 📈 Performance

### Optimizations
- **Connection Pooling**: Reused HTTP connections
- **Image Processing**: Optimized OpenCV pipeline
- **AI Caching**: Reduced redundant API calls
- **Async Operations**: Non-blocking I/O throughout

### Scaling
- **Horizontal Scaling**: Stateless service design
- **Resource Efficiency**: Lower memory footprint
- **Auto-scaling**: Railway auto-scaling support
- **Load Balancing**: Built-in health checks

## 🆘 Troubleshooting

### Common Issues

1. **OCR Not Working**:
   - Ensure tesseract is installed in container
   - Check language packs (eng, fra, por)
   - Verify image preprocessing pipeline

2. **AI Requests Failing**:
   - Validate OpenRouter API key
   - Check rate limits and quotas
   - Verify model availability

3. **Storage Issues**:
   - Confirm S3/R2 credentials
   - Check bucket permissions
   - Verify endpoint configuration

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with detailed logging
uvicorn main:app --log-level debug
```

## 📞 Support

- **Issues**: Create an issue in the repository
- **Documentation**: Check `/docs` directory  
- **API Specs**: Available at `/docs` endpoint on each service

---

**Built with ❤️ using Python, FastAPI, and modern async technologies**