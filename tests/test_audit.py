"""Test audit logging functionality."""
import pytest
import tempfile
import os
import json
from pathlib import Path
from umbra.core.audit import AuditLogger, AuditEvent

class TestAuditLogger:
    """Test audit logging system."""
    
    def test_audit_logger_initialization(self):
        """Test audit logger initializes correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_logger = AuditLogger(audit_dir=temp_dir)
            assert audit_logger is not None
            assert Path(temp_dir).exists()
    
    def test_log_event(self):
        """Test basic event logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_logger = AuditLogger(audit_dir=temp_dir)
            
            event_id = audit_logger.log_event(
                user_id=12345,
                module="test",
                action="test_action",
                status="success"
            )
            
            assert event_id is not None
            assert len(event_id) > 0
            
            # Check file was created
            audit_files = list(Path(temp_dir).glob("audit-*.jsonl"))
            assert len(audit_files) > 0
    
    def test_log_access_attempt(self):
        """Test access attempt logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_logger = AuditLogger(audit_dir=temp_dir)
            
            # Test granted access
            event_id = audit_logger.log_access_attempt(
                user_id=12345,
                module="finance",
                action="read",
                granted=True
            )
            assert event_id is not None
            
            # Test denied access
            event_id = audit_logger.log_access_attempt(
                user_id=12345,
                module="admin",
                action="user_management",
                granted=False,
                reason="Insufficient permissions"
            )
            assert event_id is not None
    
    def test_query_events(self):
        """Test querying audit events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_logger = AuditLogger(audit_dir=temp_dir)
            
            # Log some events
            audit_logger.log_event(
                user_id=12345,
                module="finance",
                action="read",
                status="success"
            )
            
            audit_logger.log_event(
                user_id=12345,
                module="finance",
                action="write", 
                status="error"
            )
            
            audit_logger.log_event(
                user_id=67890,
                module="system",
                action="read",
                status="success"
            )
            
            # Query all events
            events = audit_logger.query_events()
            assert len(events) >= 3
            
            # Query by user
            user_events = audit_logger.query_events(user_id=12345)
            assert len(user_events) >= 2
            
            # Query by module
            finance_events = audit_logger.query_events(module="finance")
            assert len(finance_events) >= 2
            
            # Query by status
            error_events = audit_logger.query_events(status="error")
            assert len(error_events) >= 1
    
    def test_user_activity_summary(self):
        """Test user activity summary generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_logger = AuditLogger(audit_dir=temp_dir)
            
            user_id = 12345
            
            # Log various events for the user
            audit_logger.log_event(user_id, "finance", "read", "success")
            audit_logger.log_event(user_id, "finance", "write", "success")
            audit_logger.log_event(user_id, "system", "read", "error")
            audit_logger.log_event(user_id, "admin", "user_management", "denied")
            
            summary = audit_logger.get_user_activity_summary(user_id, days=1)
            
            assert summary["user_id"] == user_id
            assert summary["total_events"] >= 4
            assert "finance" in summary["modules_used"]
            assert "system" in summary["modules_used"]
            assert summary["error_count"] >= 1
            assert summary["denied_count"] >= 1
            assert summary["success_rate"] > 0
    
    def test_redaction(self):
        """Test that sensitive data gets redacted in audit logs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_logger = AuditLogger(audit_dir=temp_dir)
            
            # Log event with sensitive data
            sensitive_details = {
                "api_key": "sk-1234567890abcdef",
                "email": "user@example.com",
                "phone": "555-123-4567",
                "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9"
            }
            
            audit_logger.log_event(
                user_id=12345,
                module="test",
                action="sensitive_test",
                details=sensitive_details
            )
            
            # Read the actual file to verify redaction
            audit_files = list(Path(temp_dir).glob("audit-*.jsonl"))
            assert len(audit_files) > 0
            
            with open(audit_files[0], 'r') as f:
                content = f.read()
                
                # Check that sensitive data is redacted
                assert "sk-1234567890abcdef" not in content  # API key should be redacted
                assert "[REDACTED_PHONE]" in content or "555-" not in content  # Phone redacted
                assert "user@example.com" not in content or "*" in content  # Email redacted

if __name__ == "__main__":
    pytest.main([__file__])