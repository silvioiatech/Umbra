"""Test structured logging functionality."""
import pytest
import json
from io import StringIO
import logging
from unittest.mock import patch
from umbra.core.logging_mw import (
    StructuredLogger, 
    StructuredJSONFormatter, 
    LogRedactor, 
    RequestTracker
)

class TestLogRedactor:
    """Test log redaction functionality."""
    
    def test_token_redaction(self):
        """Test that long tokens get redacted."""
        redactor = LogRedactor()
        
        test_string = "API key: sk-1234567890abcdefghij"
        redacted = redactor._redact_string("message", test_string)
        
        # Token should be partially masked
        assert "sk-1234567890abcdefghij" not in redacted
        assert "*" in redacted
    
    def test_email_redaction(self):
        """Test email redaction."""
        redactor = LogRedactor()
        
        test_string = "User email: john.doe@example.com"
        redacted = redactor._redact_string("message", test_string)
        
        # Email should be masked
        assert "john.doe@example.com" not in redacted
        assert "@example.com" in redacted  # Domain should remain
        assert "j*e@example.com" in redacted or "[REDACTED_EMAIL]" in redacted
    
    def test_phone_redaction(self):
        """Test phone number redaction."""
        redactor = LogRedactor()
        
        test_string = "Phone: 555-123-4567"
        redacted = redactor._redact_string("message", test_string)
        
        assert "555-123-4567" not in redacted
        assert "[REDACTED_PHONE]" in redacted
    
    def test_sensitive_field_redaction(self):
        """Test that sensitive field names trigger redaction."""
        redactor = LogRedactor()
        
        # Test various sensitive field names
        sensitive_fields = ["password", "token", "api_key", "secret"]
        
        for field in sensitive_fields:
            redacted = redactor._redact_string(field, "sensitive_value")
            assert "sensitive_value" not in redacted
            assert "*" in redacted
    
    def test_log_entry_redaction(self):
        """Test redaction of complex log entries."""
        redactor = LogRedactor()
        
        log_entry = {
            "message": "User logged in",
            "user": {
                "email": "test@example.com",
                "password": "secret123"
            },
            "api_key": "sk-abcdef123456",
            "metadata": {
                "phone": "555-987-6543",
                "safe_data": "this should not be redacted"
            }
        }
        
        redacted_entry = redactor.redact_log_entry(log_entry)
        
        # Check redaction worked
        assert "test@example.com" not in str(redacted_entry)
        assert "secret123" not in str(redacted_entry)
        assert "sk-abcdef123456" not in str(redacted_entry)
        assert "555-987-6543" not in str(redacted_entry)
        
        # Safe data should remain
        assert "this should not be redacted" in str(redacted_entry)

class TestStructuredJSONFormatter:
    """Test JSON log formatting."""
    
    def test_basic_formatting(self):
        """Test basic log record formatting."""
        formatter = StructuredJSONFormatter()
        
        # Create a test log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # Should be valid JSON
        log_data = json.loads(formatted)
        
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test_logger"
        assert log_data["message"] == "Test message"
        assert "timestamp" in log_data
    
    def test_structured_data_inclusion(self):
        """Test that structured data gets included in logs."""
        formatter = StructuredJSONFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Add structured data
        record.structured_data = {
            "request_id": "req123",
            "user_id": 456,
            "module": "finance"
        }
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data["request_id"] == "req123"
        assert log_data["user_id"] == 456
        assert log_data["module"] == "finance"

class TestRequestTracker:
    """Test request tracking context manager."""
    
    def test_request_id_generation(self):
        """Test request ID generation."""
        request_id1 = RequestTracker.generate_request_id()
        request_id2 = RequestTracker.generate_request_id()
        
        assert len(request_id1) == 8
        assert len(request_id2) == 8
        assert request_id1 != request_id2
    
    def test_context_tracking(self):
        """Test request context tracking."""
        with RequestTracker.track_request(
            user_id=123, 
            module="test", 
            action="test_action"
        ) as context:
            assert context["user_id"] == 123
            assert context["module"] == "test"
            assert context["action"] == "test_action"
            assert "request_id" in context
            assert "start_time" in context

class TestStructuredLogger:
    """Test structured logger functionality."""
    
    def test_logger_creation(self):
        """Test structured logger creation."""
        logger = StructuredLogger("test_logger")
        assert logger is not None
        assert logger.logger.name == "test_logger"
    
    @patch('umbra.core.logging_mw.request_id_var')
    @patch('umbra.core.logging_mw.user_id_var')
    def test_context_data_retrieval(self, mock_user_id, mock_request_id):
        """Test context data retrieval from context vars."""
        mock_request_id.get.return_value = "test123"
        mock_user_id.get.return_value = 456
        
        logger = StructuredLogger("test_logger")
        context_data = logger._get_context_data()
        
        assert context_data["request_id"] == "test123"
        assert context_data["user_id"] == 456
        assert "timestamp" in context_data

if __name__ == "__main__":
    pytest.main([__file__])