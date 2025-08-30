# Umbra Bot System - Complete Multi-Module Implementation

A comprehensive, production-ready Telegram bot ecosystem with 6 Railway-deployed services for workflow creation and media generation.

## Architecture Overview

Umbra is a modular system with 6 Railway-deployed services:

1. **Umbra (Main Agent)** - Entry point, NLU routing (EN/FR/PT), simple task execution
2. **Finance Module** - OCR processing, financial document extraction, reporting with PII minimization
3. **Concierge Module** - VPS management via Railway deployment (manages external VPS for n8n)
4. **Business Module** - Client lifecycle management via Concierge delegation
5. **Production Module** - Workflow creation using Claude→GPT pipeline with retry logic
6. **Creator Module** - Multi-provider media generation (OpenRouter primary, Runway/Shotstack/ElevenLabs for gaps)

## Features

### ✅ Complete Implementation - Production Ready

- **All 6 Railway services implemented** with full functionality and one-click deployment ready
- **Complete envelope communication system** with standardized contracts
- **Umbra Main Agent** with Telegram integration, multi-language support (EN/FR/PT)
- **Intent classification** using both pattern matching and AI (OpenRouter)
- **Module routing** with fallback mechanisms and health checks
- **Finance Module** with full OCR capabilities using Tesseract.js and OpenRouter vision
- **Document processing** for invoices, receipts, statements with structured data extraction
- **Financial categorization** and report generation (budget, VAT, tax)
- **PII minimization** and secure storage integration with S3/R2
- **VPS Concierge** with complete system monitoring, SSH management, and validation gates
- **Business Module** with client lifecycle management delegating to Concierge and Production
- **Production Module** with Claude→GPT pipeline, retry logic, and circuit breakers
- **Creator Module** with multi-provider media generation (OpenRouter, Runway, Shotstack, ElevenLabs)
- **Comprehensive error handling** and retry logic with circuit breakers
- **Audit logging** and observability across all services
- **Railway deployment** configuration for production hosting

### 🏗️ Architecture Highlights

- **Envelope Pattern**: Standardized inter-service communication
- **Security Constraints**: Only Concierge has VPS access, validation gates for critical operations  
- **Retry Strategies**: Different retry configs for functional/technical/network errors
- **Circuit Breakers**: Automatic fallback on provider failures
- **Cost Controls**: Per-request and per-module budget caps
- **Multi-Environment**: Staging and production environment support

## Quick Start

### Local Development

1. **Clone and install dependencies:**
```bash
git clone <repository-url>
cd Umbra
npm install
```

2. **Build shared components:**
```bash
# Build shared package first (required for all services)
cd shared
npm install
npm run build:clean
cd ..

# Or use the automated build script
./scripts/build.sh
```

3. **Configure environment variables:**
```bash
cp services/umbra/.env.example services/umbra/.env
# Edit .env files with your API keys
```

4. **Start with Docker Compose:**
```bash
docker-compose up --build
```

### Railway Deployment

**One-Click Deployment**: Connect your repository to Railway and all 6 services will be automatically deployed.

**Build Process**: The multi-stage Docker builds automatically handle the correct build order:
1. Build `@umbra/shared` module first with all dependencies  
2. Copy built shared module to each service
3. Build individual services with shared module available

```bash
# Railway automatically deploys these services:
# - umbra (main agent)
# - finance (document processing)  
# - concierge (VPS management)
# - business (client lifecycle)
# - production (workflow creation)
# - creator (media generation)
```

**Important Notes**:
- **Concierge deploys to Railway** - it manages the external VPS remotely
- **VPS is only for n8n instances** and eventually database
- See `docs/deployment.md` for complete setup instructions

## Service Details

### Umbra Main Agent (Port 8080)
- **Telegram Bot Integration** with webhook support
- **Multi-language support** (English, French, Portuguese)
- **Intent Classification** using pattern matching + OpenRouter AI
- **Module Routing** with health checks and fallbacks
- **Simple Task Execution** (calculations, translations)
- **Document Processing** (photos, PDFs via Finance module)

### Finance Module (Port 8081)
- **OCR Processing** with Tesseract.js for images and pdf-parse for PDFs
- **AI-Enhanced Extraction** using OpenRouter vision models
- **Financial Categorization** with confidence scoring
- **Report Generation** (budget, VAT, tax reports)
- **Data Deduplication** and anomaly detection
- **PII Minimization** for GDPR compliance
- **S3 Storage Integration** with lifecycle management

### VPS Concierge (Port 9090)
- **Exclusive VPS Access** - only service with SSH credentials
- **Validation Gates** for critical operations (delete, restart, etc.)
- **System Monitoring** with real-time metrics
- **Container Management** via Docker commands
- **Client Management Scripts** execution
- **Comprehensive Audit Logging** for security compliance

## API Documentation

### Envelope Communication Pattern

All inter-service communication uses standardized envelopes:

```typescript
interface Envelope<TPayload> {
  reqId: string;            // uuid
  userId: string;           // telegram id  
  lang: 'EN' | 'FR' | 'PT';
  timestamp: string;        // ISO
  payload: TPayload;
  meta?: {
    costCapUsd?: number;
    priority?: 'normal' | 'urgent';
    retryCount?: number;
  };
}
```

### Service Endpoints

- **Umbra**: `POST /api/v1/route` - Route requests to appropriate modules
- **Finance**: `POST /api/v1/ocr` - Process documents with OCR
- **Concierge**: `POST /api/v1/execute` - Execute VPS commands (validation required)
- **All Services**: `GET /health` - Health check endpoint

## Security & Compliance

### Trust Boundaries
- **Public**: Telegram Bot (bot token only)
- **Orchestration**: Internal services with API key authentication
- **VPS Access**: Concierge only (exclusive SSH access)
- **External APIs**: OpenRouter, Runway, Shotstack, ElevenLabs
- **Storage**: S3/R2 with signed URLs and lifecycle policies

### Validation Gates
Critical operations require validation tokens:
- VPS command execution
- Container deletion/restart
- Client management operations
- Production workflow deployment

### Audit Logging
- All requests logged with sanitized data
- PII minimization for financial documents
- Critical operation tracking
- Performance monitoring

## Environment Configuration

### Required Environment Variables

**Umbra Service:**
```bash
BOT_TOKEN=your_telegram_bot_token
OPENROUTER_API_KEY=your_openrouter_key
STORAGE_ENDPOINT=your_s3_endpoint
STORAGE_ACCESS_KEY=your_access_key
STORAGE_SECRET_KEY=your_secret_key
STORAGE_BUCKET=your_bucket_name
```

**Finance Service:**
```bash
OPENROUTER_API_KEY=your_openrouter_key
STORAGE_ENDPOINT=your_s3_endpoint
STORAGE_ACCESS_KEY=your_access_key
STORAGE_SECRET_KEY=your_secret_key
STORAGE_BUCKET=your_bucket_name
```

**VPS Concierge:**
```bash
VPS_HOST=your_vps_ip
VPS_USERNAME=your_ssh_user
VPS_PRIVATE_KEY=your_ssh_private_key
VPS_PORT=22
```

## Testing

### Running Tests
```bash
# Run all tests
npm test

# Run service-specific tests  
cd services/umbra && npm test
cd services/finance && npm test
```

### Manual Testing

1. **Telegram Bot Testing:**
   - Send `/start` to get welcome message
   - Upload a receipt/invoice for OCR processing
   - Try different languages (EN/FR/PT)

2. **API Testing:**
   ```bash
   # Health check
   curl http://localhost:8080/health
   
   # Test finance OCR
   curl -X POST http://localhost:8081/api/v1/ocr \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     -d '{"reqId":"test-123","userId":"123","lang":"EN","timestamp":"2024-01-01T00:00:00Z","payload":{"action":"ocr","documentUrl":"https://example.com/receipt.jpg"}}'
   ```

## Architecture Decisions

### Why Envelope Pattern?
- **Standardized Communication**: All services use the same message format
- **Audit Trail**: Every request has a unique ID and user context
- **Multi-language Support**: Built into every message
- **Retry Logic**: Embedded retry count and error handling
- **Cost Control**: Optional cost caps for expensive operations

### Why TypeScript?
- **Type Safety**: Catch errors at compile time
- **Better Tooling**: IDE support and refactoring
- **Shared Types**: Consistent interfaces across services
- **Documentation**: Self-documenting code with interfaces

### Why Microservices?
- **Scalability**: Scale individual services independently
- **Technology Diversity**: Use best tool for each job
- **Fault Isolation**: One service failure doesn't bring down the system
- **Team Autonomy**: Different teams can own different services
- **Deployment Independence**: Deploy services separately

## Production Considerations

### Monitoring
- Health checks on all services
- Performance metrics and alerting
- Error rate monitoring
- Cost tracking for external APIs

### Scaling
- Horizontal scaling via Railway/Docker
- Database connections pooling
- CDN for media files
- Caching for frequent requests

### Security
- API key rotation
- Secret management
- Network isolation
- Regular security audits

## Contributing

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/new-feature`
3. **Make changes** following the existing patterns
4. **Add tests** for new functionality
5. **Update documentation** if needed
6. **Submit pull request**

### Development Guidelines

- Follow existing code structure and naming conventions
- Add comprehensive error handling with appropriate error types
- Include audit logging for important operations
- Write tests for critical functionality
- Update environment examples for new configuration

## License

MIT License - see LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the documentation in `/docs`
- Review the API specifications in `/docs/api`

---

**Built with ❤️ using Node.js, TypeScript, Express.js, and OpenRouter AI**