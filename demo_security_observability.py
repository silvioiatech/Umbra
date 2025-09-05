#!/usr/bin/env python3
"""
UMBRA Security & Observability Demo

Demonstrates the comprehensive security and observability features
implemented in UMBRA:
- Role-Based Access Control (RBAC)
- Structured JSON logging with request correlation
- Prometheus-ready metrics
- Comprehensive audit logging with redaction
"""

import sys
import os
import asyncio
import tempfile
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, '.')

# Set environment to skip validation for demo
os.environ['UMBRA_SKIP_VALIDATION'] = '1'

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_section(title):
    print(f"\n{'-'*40}")
    print(f"  {title}")
    print(f"{'-'*40}")

async def demo_rbac():
    """Demonstrate Role-Based Access Control."""
    print_header("RBAC (Role-Based Access Control) Demo")
    
    from umbra.core.rbac import RBACManager, Role, Module, Action
    
    rbac = RBACManager()
    
    # Demo users
    users = {
        "guest_user": 111111,
        "regular_user": 222222, 
        "moderator": 333333,
        "admin": 444444,
        "super_admin": 555555
    }
    
    # Assign roles
    rbac.set_user_role(users["guest_user"], Role.GUEST)
    rbac.set_user_role(users["regular_user"], Role.USER)
    rbac.set_user_role(users["moderator"], Role.MODERATOR)
    rbac.set_user_role(users["admin"], Role.ADMIN)
    rbac.set_user_role(users["super_admin"], Role.SUPER_ADMIN)
    
    print("✅ User roles assigned:")
    for name, user_id in users.items():
        role = rbac.get_user_role(user_id)
        print(f"   {name}: {role.value}")
    
    print_section("Permission Matrix Test")
    
    # Test various permissions
    tests = [
        (Module.FINANCE, Action.READ, "View financial data"),
        (Module.FINANCE, Action.AUDIT_VIEW, "View finance audit logs"),
        (Module.SYSTEM, Action.USER_MANAGEMENT, "Manage system users"),
        (Module.SYSTEM, Action.DELETE, "Delete system data"),
        (Module.PRODUCTION, Action.CREATE_WORKFLOW, "Create workflows"),
    ]
    
    for module, action, description in tests:
        print(f"\n{description} ({module.value}/{action.value}):")
        for name, user_id in users.items():
            can_access = rbac.check_permission(user_id, module, action)
            status = "✅ GRANTED" if can_access else "❌ DENIED"
            print(f"   {name:12}: {status}")

def demo_structured_logging():
    """Demonstrate structured JSON logging with redaction."""
    print_header("Structured Logging & Redaction Demo")
    
    from umbra.core.logging_mw import (
        StructuredLogger, LogRedactor, RequestTracker
    )
    
    logger = StructuredLogger("demo")
    redactor = LogRedactor()
    
    print_section("Request Tracking")
    
    # Demonstrate request context tracking
    with RequestTracker.track_request(123456, "finance", "transaction") as context:
        print(f"✅ Request ID: {context['request_id']}")
        print(f"✅ User ID: {context['user_id']}")
        print(f"✅ Module: {context['module']}")
        print(f"✅ Action: {context['action']}")
    
    print_section("Sensitive Data Redaction")
    
    # Test data redaction
    sensitive_examples = [
        ("API Key", "sk-1234567890abcdefghijklmnopqrstuvwxyz"),
        ("Email", "john.doe@company.com"),
        ("Phone", "555-123-4567"),
        ("Credit Card", "4532-1234-5678-9012"),
        ("Token", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"),
    ]
    
    for data_type, original in sensitive_examples:
        redacted = redactor._redact_string("test_field", original)
        print(f"✅ {data_type}:")
        print(f"   Original: {original}")
        print(f"   Redacted: {redacted}")

def demo_metrics():
    """Demonstrate Prometheus-ready metrics collection."""
    print_header("Metrics Collection Demo")
    
    from umbra.core.metrics import UmbraMetrics
    
    metrics = UmbraMetrics()
    
    print_section("Recording Metrics")
    
    # Simulate various operations
    operations = [
        ("finance", "read", "success", 0.045, "user"),
        ("finance", "write", "success", 0.089, "user"),
        ("concierge", "system_check", "success", 0.156, "admin"),
        ("business", "create_client", "error", 0.234, "moderator"),
        ("production", "deploy_workflow", "success", 1.567, "admin"),
    ]
    
    for module, action, status, duration, role in operations:
        metrics.record_request(module, action, status, duration, role)
        metrics.record_permission_check(module, action, "granted")
        print(f"✅ Recorded: {module}/{action} - {status} ({duration}s) by {role}")
    
    # Record some errors
    errors = [
        ("finance", "ValidationError"),
        ("business", "DatabaseError"),
        ("production", "TimeoutError"),
    ]
    
    for module, error_type in errors:
        metrics.record_error(module, error_type)
        print(f"✅ Error recorded: {module} - {error_type}")
    
    # Update system metrics
    metrics.update_active_users({"user": 15, "moderator": 5, "admin": 3})
    metrics.update_system_metrics(86400, 134217728)  # 1 day uptime, 128MB memory
    
    print_section("Metrics Summary")
    
    summary = metrics.get_metrics_summary()
    print(f"✅ Total Requests: {summary['total_requests']}")
    print(f"✅ Error Rate: {summary['error_rate']:.2%}")
    print(f"✅ Active Users: {summary['active_users']}")
    
    print_section("Prometheus Format Sample")
    
    prometheus_data = metrics.get_prometheus_metrics()
    lines = [line for line in prometheus_data.split('\n') if line and not line.startswith('#')][:5]
    
    for line in lines:
        print(f"  {line}")
    print(f"  ... ({len(prometheus_data.split())} total lines)")

async def demo_audit_logging():
    """Demonstrate audit logging with querying."""
    print_header("Audit Logging Demo")
    
    from umbra.core.audit import AuditLogger
    
    # Use temporary directory for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        audit = AuditLogger(audit_dir=temp_dir)
        
        print_section("Recording Audit Events")
        
        # Simulate various audit events
        events = [
            ("log_event", {
                "user_id": 123456,
                "module": "finance", 
                "action": "create_transaction",
                "status": "success",
                "details": {"amount": 50.00, "category": "groceries"}
            }),
            ("log_access_attempt", {
                "user_id": 123456,
                "module": "finance",
                "action": "read",
                "granted": True
            }),
            ("log_access_attempt", {
                "user_id": 789012,
                "module": "admin",
                "action": "delete_user",
                "granted": False,
                "reason": "Insufficient permissions"
            }),
            ("log_admin_action", {
                "admin_id": 999999,
                "action": "user_role_change",
                "target_user": 123456,
                "details": {"old_role": "user", "new_role": "moderator"}
            }),
            ("log_error", {
                "user_id": 123456,
                "module": "finance",
                "action": "import_transactions",
                "error_type": "ValidationError",
                "error_message": "Invalid CSV format"
            }),
        ]
        
        event_ids = []
        for method_name, kwargs in events:
            method = getattr(audit, method_name)
            event_id = method(**kwargs)
            event_ids.append(event_id)
            
            if method_name == "log_event":
                print(f"✅ Event logged: {kwargs['module']}/{kwargs['action']} - {kwargs['status']}")
            elif method_name == "log_access_attempt":
                status = "GRANTED" if kwargs["granted"] else "DENIED"
                print(f"✅ Access attempt: {kwargs['module']}/{kwargs['action']} - {status}")
            elif method_name == "log_admin_action":
                print(f"✅ Admin action: {kwargs['action']} by {kwargs['admin_id']}")
            elif method_name == "log_error":
                print(f"✅ Error logged: {kwargs['module']} - {kwargs['error_type']}")
        
        print_section("Querying Audit Events")
        
        # Query all events
        all_events = audit.query_events()
        print(f"✅ Total events: {len(all_events)}")
        
        # Query by user
        user_events = audit.query_events(user_id=123456)
        print(f"✅ Events for user 123456: {len(user_events)}")
        
        # Query by module
        finance_events = audit.query_events(module="finance")
        print(f"✅ Finance module events: {len(finance_events)}")
        
        # Query by status
        error_events = audit.query_events(status="error")
        denied_events = audit.query_events(status="denied")
        print(f"✅ Error events: {len(error_events)}")
        print(f"✅ Denied access events: {len(denied_events)}")
        
        print_section("User Activity Summary")
        
        summary = audit.get_user_activity_summary(123456, days=1)
        print(f"✅ User 123456 activity summary:")
        print(f"   Total events: {summary['total_events']}")
        print(f"   Modules used: {', '.join(summary['modules_used'])}")
        print(f"   Success rate: {summary['success_rate']:.2%}")
        print(f"   Error count: {summary['error_count']}")
        print(f"   Denied count: {summary['denied_count']}")

async def demo_integration():
    """Demonstrate all features working together."""
    print_header("Integration Demo - All Features Together")
    
    from umbra.core import (
        rbac_manager, Role, Module, Action,
        audit_logger, metrics, logging_middleware
    )
    
    # Setup user
    user_id = 123456
    rbac_manager.set_user_role(user_id, Role.USER)
    
    print_section("Complete Request Flow")
    
    # Simulate complete request with all observability features
    with logging_middleware.log_request(user_id, "finance", "read", account="checking"):
        print("🔄 Processing request with full observability...")
        
        # Check permissions
        can_access = rbac_manager.check_permission(user_id, Module.FINANCE, Action.READ)
        
        if can_access:
            # Record granted access
            metrics.record_permission_check("finance", "read", "granted")
            audit_logger.log_access_attempt(user_id, "finance", "read", granted=True)
            
            # Simulate successful operation
            audit_logger.log_event(
                user_id=user_id,
                module="finance",
                action="read",
                status="success",
                details={"account": "checking", "balance": 1250.00}
            )
            
            metrics.record_request("finance", "read", "success", 0.034, "user")
            print("✅ Request completed successfully")
            
        else:
            # Record denied access
            metrics.record_permission_check("finance", "read", "denied")
            audit_logger.log_access_attempt(
                user_id, "finance", "read", 
                granted=False, reason="Insufficient role"
            )
            print("❌ Request denied due to insufficient permissions")
    
    print_section("Final Summary")
    
    # Show final state
    permissions = rbac_manager.get_user_permissions(user_id)
    metrics_summary = metrics.get_metrics_summary()
    recent_events = audit_logger.query_events(user_id=user_id, limit=5)
    
    print(f"✅ User permissions: {len([p for perms in permissions.values() for p in perms.values() if p])} granted")
    print(f"✅ Total requests processed: {metrics_summary['total_requests']}")
    print(f"✅ Recent audit events: {len(recent_events)}")
    print(f"✅ System error rate: {metrics_summary['error_rate']:.2%}")

async def main():
    """Run the complete demo."""
    print("🚀 UMBRA Security & Observability Demo")
    print("   Demonstrating enterprise-grade security and monitoring features")
    
    try:
        await demo_rbac()
        demo_structured_logging()
        demo_metrics()
        await demo_audit_logging()
        await demo_integration()
        
        print_header("Demo Complete! 🎉")
        print("""
Features demonstrated:
✅ Role-Based Access Control (RBAC) with 5-tier hierarchy
✅ Structured JSON logging with request correlation
✅ Sensitive data redaction (API keys, emails, phones, etc.)
✅ Prometheus-ready metrics collection
✅ Comprehensive audit logging with querying
✅ Complete integration of all security & observability features

The UMBRA bot is now hardened with enterprise-grade:
- 🔐 Security: RBAC, audit trails, data redaction
- 📊 Observability: Structured logs, metrics, monitoring
- 🛡️ Compliance: Tamper-proof logs, retention, access controls
        """)
        
    except Exception as e:
        print(f"❌ Demo error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())