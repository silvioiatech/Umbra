"""
JSON logging configuration for Umbra bot with request tracking.
Provides structured logs with request_id, user_id, module, action for Railway deployment.
"""
import logging
import json
import uuid
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from contextvars import ContextVar

# Context variables for tracking request context
request_id_context: ContextVar[str] = ContextVar('request_id', default='')
user_id_context: ContextVar[int] = ContextVar('user_id', default=0)
module_context: ContextVar[str] = ContextVar('module', default='')
action_context: ContextVar[str] = ContextVar('action', default='')

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter with structured fields for Railway logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with required fields."""
        
        # Base log structure
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name
        }
        
        # Add context fields
        request_id = request_id_context.get('')
        user_id = user_id_context.get(0)
        module_name = module_context.get('')
        action = action_context.get('')
        
        if request_id:
            log_entry["request_id"] = request_id
        if user_id:
            log_entry["user_id"] = user_id
        if module_name:
            log_entry["umbra_module"] = module_name  # Renamed to avoid conflict
        if action:
            log_entry["action"] = action
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in {'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'message', 'exc_info',
                          'exc_text', 'stack_info'}:
                log_entry[key] = value
        
        return json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'))

def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Setup structured JSON logging configuration for production."""
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create JSON formatter
    json_formatter = JSONFormatter()
    
    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional) - also JSON formatted
    if log_file:
        from pathlib import Path
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)
    
    # Reduce noise from external libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger('umbra.core.logger')
    logger.info("JSON logging configured", extra={"level": level})

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)

# Context management utilities
def set_request_context(request_id: Optional[str] = None, user_id: Optional[int] = None, 
                       module: Optional[str] = None, action: Optional[str] = None) -> str:
    """Set request context for logging. Returns the request_id."""
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    request_id_context.set(request_id)
    if user_id is not None:
        user_id_context.set(user_id)
    if module is not None:
        module_context.set(module)
    if action is not None:
        action_context.set(action)
    
    return request_id

def clear_request_context():
    """Clear all request context variables."""
    request_id_context.set('')
    user_id_context.set(0)
    module_context.set('')
    action_context.set('')

def get_current_request_id() -> str:
    """Get current request ID from context."""
    return request_id_context.get('')

class RequestContextLogger:
    """Logger wrapper that automatically includes request context."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def _log_with_context(self, level: int, msg: str, **kwargs):
        """Log with automatic context inclusion."""
        extra = kwargs.get('extra', {})
        
        # Add current context if not already specified
        if not extra.get('request_id'):
            extra['request_id'] = request_id_context.get('')
        if not extra.get('user_id'):
            user_id = user_id_context.get(0)
            if user_id:
                extra['user_id'] = user_id
        if not extra.get('umbra_module'):
            module = module_context.get('')
            if module:
                extra['umbra_module'] = module
        if not extra.get('action'):
            action = action_context.get('')
            if action:
                extra['action'] = action
        
        kwargs['extra'] = extra
        self.logger._log(level, msg, (), **kwargs)
    
    def debug(self, msg: str, **kwargs):
        self._log_with_context(logging.DEBUG, msg, **kwargs)
    
    def info(self, msg: str, **kwargs):
        self._log_with_context(logging.INFO, msg, **kwargs)
    
    def warning(self, msg: str, **kwargs):
        self._log_with_context(logging.WARNING, msg, **kwargs)
    
    def error(self, msg: str, **kwargs):
        self._log_with_context(logging.ERROR, msg, **kwargs)
    
    def critical(self, msg: str, **kwargs):
        self._log_with_context(logging.CRITICAL, msg, **kwargs)

def get_context_logger(name: str) -> RequestContextLogger:
    """Get a context-aware logger that automatically includes request context."""
    return RequestContextLogger(logging.getLogger(name))

def sanitize_log_data(data: str) -> str:
    """Sanitize sensitive data from logs."""
    sensitive_patterns = [
        'token', 'key', 'secret', 'password', 'auth'
    ]
    
    sanitized = data
    for pattern in sensitive_patterns:
        if pattern.lower() in sanitized.lower():
            # Replace with asterisks, keeping first and last 4 characters
            if len(sanitized) > 8:
                sanitized = sanitized[:4] + '*' * (len(sanitized) - 8) + sanitized[-4:]
            else:
                sanitized = '*' * len(sanitized)
    
    return sanitized

def log_api_request(logger: logging.Logger, method: str, url: str, 
                   status_code: Optional[int] = None, 
                   duration_ms: Optional[float] = None,
                   error: Optional[str] = None):
    """Log API request with structured data."""
    log_data = {
        "event": "api_request",
        "method": method,
        "url": sanitize_log_data(url),
        "status_code": status_code,
        "duration_ms": duration_ms
    }
    
    if error:
        log_data["error"] = error
        logger.error("API request failed", extra=log_data)
    else:
        logger.info("API request completed", extra=log_data)

def log_user_action(logger: logging.Logger, user_id: int, action: str, 
                   module: str, success: bool = True, 
                   details: Optional[Dict[str, Any]] = None):
    """Log user action with structured data."""
    log_data = {
        "event": "user_action",
        "user_id": user_id,
        "action": action,
        "module": module,
        "success": success
    }
    
    if details:
        log_data.update(details)
    
    if success:
        logger.info("User action completed", extra=log_data)
    else:
        logger.warning("User action failed", extra=log_data)

# Export all public functions
__all__ = [
    "setup_logging", 
    "get_logger", 
    "get_context_logger",
    "set_request_context", 
    "clear_request_context", 
    "get_current_request_id",
    "RequestContextLogger",
    "sanitize_log_data",
    "log_api_request",
    "log_user_action"
]
