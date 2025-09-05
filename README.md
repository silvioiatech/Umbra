# UMBRA - AI Assistant with MCP Integration

**Claude Desktop-style AI agent with specialized MCP-like modules and enterprise-grade security & observability.**

## Features

- 🤖 **Natural Language Interface** - Chat naturally, AI selects appropriate modules
- 🛠️ **MCP-like Modules** - Specialized tools for VPS, Finance, Business, Production, Content
- 🔐 **Enterprise Security** - RBAC, audit logging, structured observability
- 📊 **Prometheus Metrics** - Real-time monitoring and alerting
- 🔍 **Comprehensive Audit** - Tamper-proof logs with data redaction

## Quick Start

1. **Clone and Setup**
   ```bash
   git clone https://github.com/silvioiatech/UMBRA.git
   cd UMBRA
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Run**
   ```bash
   python main.py
   ```

## Security & Observability

UMBRA implements enterprise-grade security and observability features for production deployments.

### Role-Based Access Control (RBAC)

UMBRA uses a granular RBAC system that controls access to modules and actions:

**Available Roles:**
- `guest` - No access (default)
- `user` - Basic module access  
- `moderator` - Advanced module operations
- `admin` - System management, user administration
- `super_admin` - Full system access

**RBAC Matrix Example:**
```python
# Finance module permissions
finance_permissions = {
    "read": "user",           # View financial data
    "write": "user",          # Add transactions
    "manage_finances": "user", # Full finance operations
    "delete": "moderator",    # Delete records
    "audit_view": "admin"     # View audit logs
}

# System module permissions  
system_permissions = {
    "read": "moderator",          # View system info
    "write": "admin",             # Modify system
    "user_management": "admin",   # Manage users
    "audit_view": "admin",        # View audit logs
    "delete": "super_admin"       # Delete system data
}
```

**Setting User Roles:**
```python
from umbra.core import rbac_manager, Role

# Assign roles to users
rbac_manager.set_user_role(user_id=123456, role=Role.USER)
rbac_manager.set_user_role(user_id=789012, role=Role.ADMIN)
```

**Checking Permissions:**
```python
from umbra.core import rbac_manager, Module, Action

# Check if user can read finance data
can_read = rbac_manager.check_permission(
    user_id=123456,
    module=Module.FINANCE, 
    action=Action.READ
)
```

### Structured JSON Logging

All operations are logged in structured JSON format with request correlation:

**Log Format:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "umbra.bot",
  "message": "Request completed: finance/read",
  "request_id": "req_abc123",
  "user_id": 123456,
  "module": "finance",
  "action": "read",
  "latency_seconds": 0.045,
  "status": "success"
}
```

**Request Tracking:**
```python
from umbra.core import logging_middleware

# Automatic request tracking in handlers
with logging_middleware.log_request(user_id, "finance", "read"):
    # Your code here - automatically logged with context
    result = process_finance_request()
```

**Sensitive Data Redaction:**
- API keys, tokens: `sk-1234****5678`
- Emails: `u***r@example.com`  
- Phone numbers: `[REDACTED_PHONE]`
- Credit cards: `[REDACTED_CC]`

### Prometheus Metrics

UMBRA exposes Prometheus-compatible metrics for monitoring:

**Metrics Endpoint:** `http://localhost:8080/metrics`

**Key Metrics:**
```prometheus
# Request metrics
umbra_requests_total{module="finance",action="read",status="success",user_role="user"} 42
umbra_request_duration_seconds{module="finance",action="read",status="success"} 0.045

# Permission metrics  
umbra_permission_checks_total{module="finance",action="read",result="granted"} 38
umbra_permission_checks_total{module="admin",action="delete",result="denied"} 5

# Error metrics
umbra_errors_total{module="finance",error_type="ValidationError"} 2

# System metrics
umbra_bot_uptime_seconds 86400
umbra_memory_usage_bytes 134217728
umbra_active_users{role="user"} 15
umbra_active_users{role="admin"} 3
```

**Using Metrics:**
```python
from umbra.core import metrics

# Record custom metrics
metrics.record_request("finance", "read", "success", 0.15, "user")
metrics.record_error("finance", "ValidationError")
metrics.update_active_users({"user": 15, "admin": 3})
```

**Grafana Dashboard Example:**
```yaml
# Request rate
rate(umbra_requests_total[5m])

# Error rate  
rate(umbra_errors_total[5m]) / rate(umbra_requests_total[5m])

# Response time 95th percentile
histogram_quantile(0.95, umbra_request_duration_seconds_bucket)
```

### Audit Logging

Tamper-proof audit trail for compliance and security:

**Audit Log Location:** `data/audit/audit-YYYY-MM-DD.jsonl`

**Event Types:**
- Access attempts (granted/denied)
- Data operations (create/read/update/delete)
- Administrative actions
- System events (startup/shutdown)

**Audit Record Format:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "event_id": "evt_abc123",
  "user_id": 123456,
  "module": "finance",
  "action": "create_transaction",
  "status": "success",
  "resource": "transaction:12345",
  "details": {
    "amount": 50.00,
    "category": "groceries"
  },
  "ip_address": "192.168.1.100",
  "request_id": "req_abc123"
}
```

**Creating Audit Events:**
```python
from umbra.core import audit_logger

# Log data access
audit_logger.log_data_access(
    user_id=123456,
    resource_type="transaction",
    resource_id="12345", 
    operation="create"
)

# Log admin action
audit_logger.log_admin_action(
    admin_id=789012,
    action="user_role_change",
    target_user=123456,
    details={"old_role": "user", "new_role": "moderator"}
)
```

**Querying Audit Logs:**
```python
# Get user activity
events = audit_logger.query_events(
    user_id=123456,
    start_date="2024-01-01",
    end_date="2024-01-31",
    module="finance"
)

# Get activity summary
summary = audit_logger.get_user_activity_summary(
    user_id=123456, 
    days=30
)
```

### Admin Endpoints

**Health Check:** `GET /health`
```json
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "components": {
    "audit_logger": "healthy",
    "metrics_collector": "healthy", 
    "rbac_system": "healthy"
  }
}
```

**Metrics Dashboard:** `GET /admin/metrics`
```json
{
  "total_requests": 1234,
  "error_rate": 0.02,
  "avg_response_time": 0.045,
  "active_users": 18,
  "module_usage": {
    "finance": 456,
    "concierge": 234
  }
}
```

**Audit Query:** `GET /admin/audit?user_id=123&days=7`
```json
{
  "events": [...],
  "total": 42,
  "filters": {
    "user_id": 123,
    "days": 7
  }
}
```

## Environment Variables

### Security Configuration
```bash
# RBAC
DEFAULT_USER_ROLE=user
ADMIN_OVERRIDE_ENABLED=false

# Audit
AUDIT_RETENTION_DAYS=90
AUDIT_ENCRYPTION_KEY=your-encryption-key

# Metrics
METRICS_PORT=8080
METRICS_ENABLED=true
```

### Monitoring Setup

1. **Prometheus Configuration:**
   ```yaml
   # prometheus.yml
   scrape_configs:
     - job_name: 'umbra'
       static_configs:
         - targets: ['localhost:8080']
       scrape_interval: 15s
       metrics_path: /metrics
   ```

2. **Grafana Alerts:**
   ```yaml
   # High error rate
   rate(umbra_errors_total[5m]) > 0.1
   
   # Permission denials spike
   increase(umbra_permission_checks_total{result="denied"}[5m]) > 10
   
   # High response time
   histogram_quantile(0.95, umbra_request_duration_seconds_bucket) > 1.0
   ```

## Module Permissions

Each module has specific permission requirements:

| Module | Action | Min Role | Description |
|--------|--------|----------|-------------|
| concierge | read | user | View system status |
| concierge | execute | user | Run system commands |
| concierge | system_monitor | moderator | Access monitoring |
| finance | read | user | View financial data |
| finance | write | user | Add transactions |
| finance | audit_view | admin | View audit logs |
| business | read | user | View business data |
| business | write | moderator | Manage clients |
| system | user_management | admin | Manage users |
| system | audit_view | admin | View system audits |

## Compliance Features

- **GDPR**: Automatic PII redaction in logs
- **SOX**: Immutable audit trail with retention
- **HIPAA**: Encryption at rest and in transit
- **ISO 27001**: Role-based access controls

## Development

See `DEVELOPMENT.md` for development setup and module creation guidelines.

## License

MIT License - see LICENSE file for details.