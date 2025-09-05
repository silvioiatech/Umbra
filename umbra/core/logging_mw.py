"""Logging middleware for Umbra bot with structured JSON logging and request tracking."""
import json
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, Any, Optional
from datetime import datetime
import re

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar('request_id', default="")
user_id_var: ContextVar[int] = ContextVar('user_id', default=0)
module_var: ContextVar[str] = ContextVar('module', default="")
action_var: ContextVar[str] = ContextVar('action', default="")

class RequestTracker:
    """Tracks request context for structured logging."""
    
    @staticmethod
    def generate_request_id() -> str:
        """Generate a unique request ID."""
        return str(uuid.uuid4())[:8]
    
    @staticmethod
    @contextmanager
    def track_request(user_id: int, module: str = "", action: str = "", request_id: str = None):
        """Context manager to track a request with all relevant metadata."""
        if request_id is None:
            request_id = RequestTracker.generate_request_id()
        
        # Set context variables
        request_id_token = request_id_var.set(request_id)
        user_id_token = user_id_var.set(user_id)
        module_token = module_var.set(module)
        action_token = action_var.set(action)
        
        start_time = time.time()
        
        try:
            yield {
                'request_id': request_id,
                'user_id': user_id,
                'module': module,
                'action': action,
                'start_time': start_time
            }
        finally:
            # Reset context variables
            request_id_var.reset(request_id_token)
            user_id_var.reset(user_id_token)
            module_var.reset(module_token)
            action_var.reset(action_token)

class StructuredLogger:
    """Structured JSON logger with request context."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._setup_json_formatter()
    
    def _setup_json_formatter(self):
        """Setup JSON formatter for structured logging."""
        # Get the root logger's handlers and update their formatters
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if not isinstance(handler.formatter, StructuredJSONFormatter):
                handler.setFormatter(StructuredJSONFormatter())
    
    def _get_context_data(self) -> Dict[str, Any]:
        """Get current request context data."""
        return {
            'request_id': request_id_var.get(""),
            'user_id': user_id_var.get(0) or None,
            'module': module_var.get("") or None,
            'action': action_var.get("") or None,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
    
    def info(self, message: str, **extra):
        """Log info message with structured context."""
        self._log('info', message, **extra)
    
    def warning(self, message: str, **extra):
        """Log warning message with structured context."""
        self._log('warning', message, **extra)
    
    def error(self, message: str, **extra):
        """Log error message with structured context."""
        self._log('error', message, **extra)
    
    def debug(self, message: str, **extra):
        """Log debug message with structured context."""
        self._log('debug', message, **extra)
    
    def _log(self, level: str, message: str, **extra):
        """Internal logging method with context injection."""
        context_data = self._get_context_data()
        
        # Merge context data with extra fields
        log_data = {**context_data, **extra}
        
        # Remove None values to keep logs clean
        log_data = {k: v for k, v in log_data.items() if v is not None}
        
        # Get logger method
        log_method = getattr(self.logger, level)
        log_method(message, extra={'structured_data': log_data})

class StructuredJSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self):
        super().__init__()
        self.redactor = LogRedactor()
    
    def format(self, record):
        """Format log record as JSON."""
        # Base log entry
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add structured data if present
        if hasattr(record, 'structured_data'):
            log_entry.update(record.structured_data)
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Redact sensitive information
        log_entry = self.redactor.redact_log_entry(log_entry)
        
        return json.dumps(log_entry, default=str)

class LogRedactor:
    """Redacts sensitive information from logs."""
    
    def __init__(self):
        # Patterns for sensitive data
        self.token_pattern = re.compile(r'\b[A-Za-z0-9]{20,}\b')
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_pattern = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')
        self.credit_card_pattern = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
        
        # Sensitive field names
        self.sensitive_fields = {
            'password', 'token', 'key', 'secret', 'auth', 'credential',
            'api_key', 'access_token', 'refresh_token', 'session_id'
        }
    
    def redact_log_entry(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from a log entry."""
        redacted_entry = {}
        
        for key, value in log_entry.items():
            if isinstance(value, str):
                redacted_entry[key] = self._redact_string(key, value)
            elif isinstance(value, dict):
                redacted_entry[key] = self.redact_log_entry(value)
            elif isinstance(value, list):
                redacted_entry[key] = [
                    self.redact_log_entry(item) if isinstance(item, dict)
                    else self._redact_string(str(key), str(item)) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                redacted_entry[key] = value
        
        return redacted_entry
    
    def _redact_string(self, field_name: str, value: str) -> str:
        """Redact sensitive information from a string value."""
        # Check if field name indicates sensitive data
        if any(sensitive in field_name.lower() for sensitive in self.sensitive_fields):
            return self._mask_value(value)
        
        # Apply pattern-based redaction
        redacted_value = value
        
        # Redact tokens (long alphanumeric strings)
        redacted_value = self.token_pattern.sub(lambda m: self._mask_value(m.group(0)), redacted_value)
        
        # Redact emails
        redacted_value = self.email_pattern.sub(lambda m: self._mask_email(m.group(0)), redacted_value)
        
        # Redact phone numbers
        redacted_value = self.phone_pattern.sub('[REDACTED_PHONE]', redacted_value)
        
        # Redact credit card numbers
        redacted_value = self.credit_card_pattern.sub('[REDACTED_CC]', redacted_value)
        
        return redacted_value
    
    def _mask_value(self, value: str) -> str:
        """Mask a sensitive value, keeping first and last few characters."""
        if len(value) <= 8:
            return '*' * len(value)
        
        return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"
    
    def _mask_email(self, email: str) -> str:
        """Mask an email address."""
        if '@' not in email:
            return '[REDACTED_EMAIL]'
        
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            masked_local = '*' * len(local)
        else:
            masked_local = f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}"
        
        return f"{masked_local}@{domain}"

class LoggingMiddleware:
    """Middleware for request logging with performance metrics."""
    
    def __init__(self):
        self.logger = StructuredLogger(__name__)
    
    @contextmanager
    def log_request(self, user_id: int, module: str, action: str, **extra_context):
        """Log a request with timing and context."""
        request_id = RequestTracker.generate_request_id()
        start_time = time.time()
        
        with RequestTracker.track_request(user_id, module, action, request_id):
            # Log request start
            self.logger.info(
                f"Request started: {module}/{action}",
                request_phase="start",
                **extra_context
            )
            
            try:
                yield {
                    'request_id': request_id,
                    'start_time': start_time
                }
                
                # Log successful completion
                latency = time.time() - start_time
                self.logger.info(
                    f"Request completed: {module}/{action}",
                    request_phase="complete",
                    latency_seconds=latency,
                    status="success"
                )
                
            except Exception as e:
                # Log error
                latency = time.time() - start_time
                self.logger.error(
                    f"Request failed: {module}/{action}",
                    request_phase="error",
                    latency_seconds=latency,
                    status="error",
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise

# Global instances
logging_middleware = LoggingMiddleware()

def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)