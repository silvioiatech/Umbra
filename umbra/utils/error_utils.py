"""
Error mapping and redaction utilities for Umbra.
Provides standardized error handling and sensitive data redaction.
"""
import re
from typing import Dict, Any, Optional, List
from enum import Enum

from ..core.logger import get_context_logger

logger = get_context_logger(__name__)

class ErrorType(Enum):
    """Standard error types for Umbra."""
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND_ERROR = "not_found_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    TIMEOUT_ERROR = "timeout_error"
    INTERNAL_ERROR = "internal_error"
    CONFIGURATION_ERROR = "configuration_error"
    NETWORK_ERROR = "network_error"

class ErrorMapper:
    """Maps various error types to user-friendly messages."""
    
    def __init__(self):
        self.error_mappings = {
            # Authentication & Authorization
            ErrorType.AUTHENTICATION_ERROR: {
                "user_message": "🔐 Authentication failed. Please check your credentials.",
                "log_level": "warning",
                "expose_details": False
            },
            ErrorType.AUTHORIZATION_ERROR: {
                "user_message": "⛔ Access denied. You don't have permission for this action.",
                "log_level": "warning", 
                "expose_details": False
            },
            
            # Validation
            ErrorType.VALIDATION_ERROR: {
                "user_message": "❌ Invalid input. Please check your parameters and try again.",
                "log_level": "info",
                "expose_details": True
            },
            
            # Resource errors
            ErrorType.NOT_FOUND_ERROR: {
                "user_message": "🔍 Resource not found. Please check if it exists.",
                "log_level": "info",
                "expose_details": True
            },
            
            # Rate limiting
            ErrorType.RATE_LIMIT_ERROR: {
                "user_message": "⏱️ Too many requests. Please wait a moment and try again.",
                "log_level": "warning",
                "expose_details": True
            },
            
            # Service issues
            ErrorType.SERVICE_UNAVAILABLE: {
                "user_message": "🔧 Service temporarily unavailable. Please try again later.",
                "log_level": "error",
                "expose_details": False
            },
            ErrorType.TIMEOUT_ERROR: {
                "user_message": "⏰ Request timed out. Please try again.",
                "log_level": "warning",
                "expose_details": False
            },
            
            # System errors
            ErrorType.INTERNAL_ERROR: {
                "user_message": "🚫 Internal error occurred. The team has been notified.",
                "log_level": "error",
                "expose_details": False
            },
            ErrorType.CONFIGURATION_ERROR: {
                "user_message": "⚙️ Configuration issue. Please contact support.",
                "log_level": "error",
                "expose_details": False
            },
            ErrorType.NETWORK_ERROR: {
                "user_message": "🌐 Network error. Please check your connection and try again.",
                "log_level": "warning",
                "expose_details": False
            }
        }
    
    def map_error(
        self, 
        error_type: ErrorType, 
        original_error: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Map an error to user-friendly response."""
        
        mapping = self.error_mappings.get(error_type, {
            "user_message": "❓ An unexpected error occurred.",
            "log_level": "error",
            "expose_details": False
        })
        
        result = {
            "error_type": error_type.value,
            "user_message": mapping["user_message"],
            "log_level": mapping["log_level"],
            "timestamp": "now"  # Will be filled by logger
        }
        
        # Add details if allowed
        if mapping.get("expose_details") and original_error:
            # Redact sensitive information first
            redacted_error = redact_sensitive_data(original_error)
            result["details"] = redacted_error
        
        # Add context if provided
        if context:
            result["context"] = redact_dict(context)
        
        return result
    
    def classify_exception(self, exception: Exception) -> ErrorType:
        """Classify an exception into an ErrorType."""
        
        exception_name = type(exception).__name__.lower()
        error_message = str(exception).lower()
        
        # Authentication/Authorization
        if any(term in exception_name for term in ['auth', 'permission', 'forbidden']):
            if 'permission' in error_message or 'forbidden' in error_message:
                return ErrorType.AUTHORIZATION_ERROR
            return ErrorType.AUTHENTICATION_ERROR
        
        # Validation
        if any(term in exception_name for term in ['validation', 'value', 'type']):
            return ErrorType.VALIDATION_ERROR
        
        # Not found
        if any(term in exception_name for term in ['notfound', 'missing', 'keyerror']):
            return ErrorType.NOT_FOUND_ERROR
        
        # Rate limiting
        if any(term in error_message for term in ['rate limit', 'too many', 'quota']):
            return ErrorType.RATE_LIMIT_ERROR
        
        # Timeout
        if any(term in exception_name for term in ['timeout', 'asyncio.timeout']):
            return ErrorType.TIMEOUT_ERROR
        
        # Network
        if any(term in exception_name for term in ['connection', 'network', 'http']):
            return ErrorType.NETWORK_ERROR
        
        # Configuration
        if any(term in error_message for term in ['config', 'environment', 'setting']):
            return ErrorType.CONFIGURATION_ERROR
        
        # Default to internal error
        return ErrorType.INTERNAL_ERROR

class DataRedactor:
    """Redacts sensitive data from strings and dictionaries."""
    
    def __init__(self):
        # Patterns for sensitive data
        self.sensitive_patterns = [
            # API Keys and tokens
            (r'(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*["\']?([a-zA-Z0-9_-]{8,})["\']?', 
             r'\1: ***REDACTED***'),
            
            # URLs with credentials
            (r'(https?://)[^:@]+:[^@]+@([^/]+)', r'\1***:***@\2'),
            
            # Email addresses (partial redaction)
            (r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', 
             lambda m: f"{m.group(1)[:2]}***@{m.group(2)}"),
            
            # IP addresses (partial redaction) 
            (r'\b(\d{1,3}\.)(\d{1,3}\.)(\d{1,3}\.)(\d{1,3})\b', r'\1\2\3***'),
            
            # Phone numbers
            (r'\b(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
             r'\1(\2) ***-\4'),
            
            # Credit card numbers
            (r'\b(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})\b', r'****-****-****-\4'),
            
            # SSH keys
            (r'(ssh-[a-z0-9]+\s+)([A-Za-z0-9+/]{20,})(.*)', r'\1***REDACTED***\3'),
            
            # Private keys
            (r'(-----BEGIN [A-Z\s]+ PRIVATE KEY-----)(.+?)(-----END [A-Z\s]+ PRIVATE KEY-----)',
             r'\1\n***REDACTED***\n\3'),
            
            # JWT tokens
            (r'(eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.)([A-Za-z0-9_-]+)', r'\1***REDACTED***'),
            
            # Generic secrets (long alphanumeric strings)
            (r'\b([a-zA-Z0-9]{32,})\b', lambda m: f"{m.group(1)[:4]}***{m.group(1)[-4:]}")
        ]
        
        # Sensitive field names
        self.sensitive_fields = {
            'password', 'secret', 'token', 'key', 'api_key', 'auth', 'credential',
            'private_key', 'ssh_key', 'access_token', 'refresh_token', 'session_id',
            'cookie', 'authorization', 'x-api-key', 'bearer'
        }
    
    def redact_string(self, text: str) -> str:
        """Redact sensitive data from a string."""
        if not isinstance(text, str):
            return str(text)
        
        redacted = text
        
        for pattern, replacement in self.sensitive_patterns:
            if callable(replacement):
                redacted = re.sub(pattern, replacement, redacted)
            else:
                redacted = re.sub(pattern, replacement, redacted)
        
        return redacted
    
    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive data from a dictionary."""
        if not isinstance(data, dict):
            return data
        
        redacted = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if field name is sensitive
            if any(sensitive in key_lower for sensitive in self.sensitive_fields):
                if isinstance(value, str) and len(value) > 4:
                    redacted[key] = f"{value[:2]}***{value[-2:]}"
                else:
                    redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact_dict(item) if isinstance(item, dict)
                    else self.redact_string(str(item)) if isinstance(item, str)
                    else item
                    for item in value
                ]
            elif isinstance(value, str):
                redacted[key] = self.redact_string(value)
            else:
                redacted[key] = value
        
        return redacted

# Global instances
error_mapper = ErrorMapper()
data_redactor = DataRedactor()

# Convenience functions
def map_error(
    error_type: ErrorType, 
    original_error: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Map an error to user-friendly response."""
    return error_mapper.map_error(error_type, original_error, context)

def classify_exception(exception: Exception) -> ErrorType:
    """Classify an exception into an ErrorType."""
    return error_mapper.classify_exception(exception)

def redact_sensitive_data(text: str) -> str:
    """Redact sensitive data from a string."""
    return data_redactor.redact_string(text)

def redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive data from a dictionary."""
    return data_redactor.redact_dict(data)

def create_error_response(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """Create a standardized error response from an exception."""
    
    error_type = classify_exception(exception)
    error_response = map_error(error_type, str(exception), context)
    
    # Log the error appropriately
    logger.log(
        getattr(logger.logger, error_response["log_level"].upper(), logger.error),
        "Error response created",
        extra={
            "error_type": error_type.value,
            "user_id": user_id,
            "original_error": redact_sensitive_data(str(exception)),
            "context": redact_dict(context) if context else None
        }
    )
    
    return error_response

# Export
__all__ = [
    "ErrorType", "ErrorMapper", "DataRedactor",
    "map_error", "classify_exception", 
    "redact_sensitive_data", "redact_dict",
    "create_error_response"
]
