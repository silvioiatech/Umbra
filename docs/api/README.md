# Umbra Bot System API Documentation

## Overview

The Umbra Bot System provides a comprehensive set of REST APIs for inter-service communication using the envelope pattern. All services communicate through standardized message contracts.

## Base URL

- **Development**: `http://localhost:PORT`
- **Production**: `https://your-service.railway.app`

## Authentication

All internal API calls require service authentication:

```bash
curl -H "X-API-Key: your-service-api-key" \
     -H "X-Service-Name: calling-service-name" \
     -H "Content-Type: application/json"
```

## Envelope Format

All requests use the standardized envelope format:

```json
{
  "reqId": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "123456789",
  "lang": "EN",
  "timestamp": "2024-01-01T00:00:00.000Z",
  "payload": {
    "action": "specific_action",
    "data": "action_specific_data"
  },
  "meta": {
    "priority": "normal",
    "costCapUsd": 10.0,
    "retryCount": 0
  }
}
```

## Services

### 1. Umbra Main Agent (Port 8080)

#### Health Check
```http
GET /health
```

#### Route Request
```http
POST /api/v1/route
```

**Request Body:**
```json
{
  "reqId": "uuid",
  "userId": "telegram_user_id",
  "lang": "EN|FR|PT",
  "timestamp": "ISO_date",
  "payload": {
    "action": "classify|route|execute|clarify",
    "message": "user_message",
    "intent": "detected_intent",
    "targetModule": "destination_service"
  }
}
```

**Response:**
```json
{
  "reqId": "uuid",
  "status": "success|error|needs_validation",
  "data": {
    "intent": "classified_intent",
    "confidence": 0.95,
    "targetModule": "finance",
    "response": "processed_response"
  },
  "audit": {
    "module": "umbra-classifier",
    "durationMs": 150
  }
}
```

#### Telegram Webhook
```http
POST /webhook/telegram
```

Used by Telegram to send updates. Requires webhook secret validation.

### 2. Finance Module (Port 8081)

#### OCR Processing
```http
POST /api/v1/ocr
Content-Type: multipart/form-data
```

**Request:**
- Envelope as JSON in body
- File as multipart form data

**Envelope Payload:**
```json
{
  "action": "ocr",
  "documentType": "invoice|receipt|statement|payroll",
  "documentUrl": "optional_url_instead_of_file"
}
```

**Response:**
```json
{
  "reqId": "uuid",
  "status": "success|needs_validation",
  "data": {
    "extractedData": {
      "vendor": "Company Name",
      "amount": 125.50,
      "currency": "USD",
      "date": "2024-01-01",
      "category": "Office Supplies",
      "confidence": 0.92
    },
    "storageKey": "s3_object_key",
    "documentUrl": "signed_s3_url"
  }
}
```

#### Document Extraction
```http
POST /api/v1/extract
```

**Envelope Payload:**
```json
{
  "action": "extract",
  "documentUrl": "https://example.com/document.pdf",
  "documentType": "invoice"
}
```

#### Financial Categorization
```http
POST /api/v1/categorize
```

**Envelope Payload:**
```json
{
  "action": "categorize",
  "transactionData": {
    "vendor": "Amazon",
    "amount": 50.00,
    "description": "Office supplies"
  }
}
```

#### Report Generation
```http
POST /api/v1/report
```

**Envelope Payload:**
```json
{
  "action": "report",
  "reportType": "budget|vat|tax",
  "dateRange": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  }
}
```

### 3. VPS Concierge (Port 9090)

#### System Monitoring
```http
POST /api/v1/monitor
```

**Envelope Payload:**
```json
{
  "action": "monitor",
  "metrics": ["cpu", "memory", "disk", "containers"]
}
```

**Response:**
```json
{
  "reqId": "uuid",
  "status": "success",
  "data": {
    "systemStatus": {
      "cpu": 25.5,
      "memory": 67.2,
      "disk": 45.0,
      "uptime": 86400
    },
    "containers": [
      {
        "name": "client-1",
        "status": "running",
        "port": 3001
      }
    ]
  }
}
```

#### Command Execution
```http
POST /api/v1/execute
X-Validation-Token: required_for_dangerous_commands
```

**Envelope Payload:**
```json
{
  "action": "execute",
  "command": "docker ps",
  "validationToken": "required_for_critical_ops"
}
```

#### Client Management
```http
POST /api/v1/execute
```

**Envelope Payload:**
```json
{
  "action": "client_management",
  "clientAction": "create|delete|list",
  "clientName": "client-name",
  "clientPort": 3001
}
```

## Error Handling

### Error Response Format
```json
{
  "reqId": "uuid",
  "status": "error",
  "error": {
    "type": "functional|technical|conflict|auth",
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "retryable": true
  },
  "audit": {
    "module": "service-name",
    "durationMs": 100
  }
}
```

### Error Types

- **functional**: Invalid input, business logic errors
- **technical**: Network issues, service unavailable
- **conflict**: Resource conflicts, duplicate operations  
- **auth**: Authentication or authorization failures

### HTTP Status Codes

- `200` - Success
- `400` - Bad Request (functional errors)
- `401` - Unauthorized (missing/invalid auth)
- `403` - Forbidden (validation required)
- `404` - Not Found
- `429` - Rate Limited
- `500` - Internal Server Error
- `503` - Service Unavailable

## Rate Limiting

- **Umbra**: 200 requests/minute
- **Finance**: 100 requests/minute  
- **Concierge**: 50 requests/minute (stricter due to VPS access)

Rate limit headers:
```
X-RateLimit-Limit: 200
X-RateLimit-Remaining: 199
X-RateLimit-Reset: 1640995200
```

## Validation Gates

Critical operations require validation tokens:

1. **Request validation token:**
```http
POST /api/v1/request-validation
{
  "action": "delete_client",
  "userId": "123456789"
}
```

2. **Use validation token:**
```http
POST /api/v1/execute
X-Validation-Token: token_from_step_1
```

## Health Checks

All services provide health endpoints:

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "service-name",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00.000Z",
  "uptime": 3600,
  "dependencies": {
    "database": true,
    "external_api": true
  }
}
```

## Testing

### Example cURL Commands

```bash
# Health check
curl http://localhost:8080/health

# OCR processing
curl -X POST http://localhost:8081/api/v1/ocr \
  -H "X-API-Key: finance-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "reqId": "test-123",
    "userId": "123456789",
    "lang": "EN",
    "timestamp": "2024-01-01T00:00:00.000Z",
    "payload": {
      "action": "ocr",
      "documentUrl": "https://example.com/receipt.jpg"
    }
  }'

# System monitoring
curl -X POST http://localhost:9090/api/v1/monitor \
  -H "X-API-Key: concierge-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "reqId": "monitor-123",
    "userId": "123456789", 
    "lang": "EN",
    "timestamp": "2024-01-01T00:00:00.000Z",
    "payload": {
      "action": "monitor"
    }
  }'
```

## SDKs and Libraries

TypeScript types are available in the shared package:

```typescript
import { 
  Envelope, 
  FinancePayload, 
  ConciergePayload,
  ModuleResult 
} from '@umbra/shared';

// Type-safe API calls
const envelope: Envelope<FinancePayload> = {
  reqId: uuidv4(),
  userId: '123456789',
  lang: 'EN',
  timestamp: new Date().toISOString(),
  payload: {
    action: 'ocr',
    documentType: 'invoice'
  }
};
```

## Monitoring and Observability

All API calls include audit logging:

```json
{
  "timestamp": "2024-01-01T00:00:00.000Z",
  "level": "INFO",
  "service": "finance",
  "message": "AUDIT: OCR processing",
  "meta": {
    "userId": "123456789",
    "reqId": "uuid",
    "durationMs": 1500,
    "provider": "openrouter",
    "costUsd": 0.05
  }
}
```