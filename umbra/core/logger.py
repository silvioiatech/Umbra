"""Structured JSON logging configuration for Umbra bot."""
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

# Context variables for request tracking
request_id_context: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_context: ContextVar[Optional[int]] = ContextVar('user_id', default=None)


def add_request_context(logger, method_name, event_dict):
    """Add request context to log events."""
    request_id = request_id_context.get()
    if request_id:
        event_dict['request_id'] = request_id
    
    user_id = user_id_context.get()
    if user_id:
        event_dict['user_id'] = user_id
    
    return event_dict


def add_timestamp(logger, method_name, event_dict):
    """Add ISO timestamp to log events."""
    event_dict['ts'] = time.time()
    return event_dict


def add_module_info(logger, method_name, event_dict):
    """Add module and action information."""
    if 'module' not in event_dict:
        event_dict['module'] = logger.name
    return event_dict


def json_serializer(obj, **kwargs):
    """Custom JSON serializer for log events."""
    import json
    
    def default_serializer(o):
        if isinstance(o, (set, frozenset)):
            return list(o)
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")
    
    return json.dumps(obj, default=default_serializer, **kwargs)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None, json_format: bool = True) -> None:
    """Setup structured logging configuration."""
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    if json_format:
        # Configure structlog for JSON output
        timestamper = structlog.processors.TimeStamper(fmt="ISO")
        
        structlog.configure(
            processors=[
                add_request_context,
                add_timestamp,
                add_module_info,
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                timestamper,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    else:
        # Configure traditional logging format
        structlog.configure(
            processors=[
                add_request_context,
                add_module_info,
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(numeric_level)
        root_logger.addHandler(file_handler)
    
    # Reduce noise from external libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    
    # Log setup completion
    logger = get_logger(__name__)
    logger.info("Structured logging configured", level=level, json_format=json_format)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def set_request_context(request_id: Optional[str] = None, user_id: Optional[int] = None) -> None:
    """Set request context for logging."""
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    request_id_context.set(request_id)
    if user_id is not None:
        user_id_context.set(user_id)


def clear_request_context() -> None:
    """Clear request context."""
    request_id_context.set(None)
    user_id_context.set(None)


def get_request_id() -> Optional[str]:
    """Get current request ID."""
    return request_id_context.get()


def sanitize_log_data(data: Any) -> Any:
    """Sanitize sensitive data from logs."""
    if isinstance(data, str):
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
                break
        return sanitized
    elif isinstance(data, dict):
        return {k: sanitize_log_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_log_data(item) for item in data]
    return data
