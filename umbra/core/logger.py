"""
Structured JSON logging for the Umbra Bot system.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from .config import get_config


class StructuredJsonFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    
    Each log entry includes: timestamp, level, module, event, and additional fields.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as structured JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "module": record.name,
            "event": record.getMessage()
        }
        
        # Add extra fields from the record
        if hasattr(record, "req_id"):
            log_data["req_id"] = record.req_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "error"):
            log_data["error"] = record.error
        if hasattr(record, "context"):
            log_data["context"] = record.context
            
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data, default=str)


class UmbraLogger:
    """
    Enhanced logger for the Umbra Bot system with structured JSON output.
    """
    
    def __init__(self, name: str):
        """
        Initialize logger.
        
        Args:
            name: Logger name (typically module name)
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with structured JSON formatter."""
        if not self.logger.handlers:
            # Create console handler
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(StructuredJsonFormatter())
            
            # Set log level from config (with fallback)
            try:
                from .config import get_config
                config = get_config()
                log_level = getattr(logging, config.log_level, logging.INFO)
            except Exception:
                # Fallback to INFO if config not available
                log_level = logging.INFO
            
            self.logger.setLevel(log_level)
            handler.setLevel(log_level)
            
            self.logger.addHandler(handler)
            
            # Prevent duplicate logs
            self.logger.propagate = False
    
    def _log(self, level: str, message: str, **kwargs):
        """
        Internal logging method.
        
        Args:
            level: Log level
            message: Log message
            **kwargs: Additional fields to include in log
        """
        log_method = getattr(self.logger, level.lower())
        
        # Create a LogRecord with extra fields
        extra = {}
        for key, value in kwargs.items():
            if key not in ["name", "msg", "args", "levelname", "levelno", "pathname", 
                          "filename", "module", "exc_info", "exc_text", "stack_info", 
                          "lineno", "funcName", "created", "msecs", "relativeCreated", 
                          "thread", "threadName", "processName", "process", "getMessage"]:
                extra[key] = value
        
        log_method(message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        """
        Log debug message.
        
        Args:
            message: Debug message
            **kwargs: Additional fields
        """
        self._log("debug", message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """
        Log info message.
        
        Args:
            message: Info message
            **kwargs: Additional fields
        """
        self._log("info", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """
        Log warning message.
        
        Args:
            message: Warning message
            **kwargs: Additional fields
        """
        self._log("warning", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """
        Log error message.
        
        Args:
            message: Error message
            **kwargs: Additional fields
        """
        self._log("error", message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """
        Log critical message.
        
        Args:
            message: Critical message
            **kwargs: Additional fields
        """
        self._log("critical", message, **kwargs)
    
    def log_request(self, req_id: str, user_id: str, action: str, duration_ms: Optional[int] = None):
        """
        Log a request with structured fields.
        
        Args:
            req_id: Request ID
            user_id: User ID
            action: Action being performed
            duration_ms: Request duration in milliseconds
        """
        kwargs = {
            "req_id": req_id,
            "user_id": user_id,
            "action": action
        }
        
        if duration_ms is not None:
            kwargs["duration_ms"] = duration_ms
            
        self.info("Request processed", **kwargs)
    
    def log_error(self, req_id: str, error: str, context: Optional[Dict[str, Any]] = None):
        """
        Log an error with structured fields.
        
        Args:
            req_id: Request ID where error occurred
            error: Error message
            context: Additional error context
        """
        kwargs = {
            "req_id": req_id,
            "error": error
        }
        
        if context:
            kwargs["context"] = context
            
        self.error("Request failed", **kwargs)


# Cache for logger instances
_loggers: Dict[str, UmbraLogger] = {}


def get_logger(name: str) -> UmbraLogger:
    """
    Get or create a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        UmbraLogger instance
    """
    if name not in _loggers:
        _loggers[name] = UmbraLogger(name)
    return _loggers[name]


def setup_logging():
    """
    Setup global logging configuration.
    
    This should be called once at application startup.
    """
    # Suppress some noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
    
    # Get root logger to ensure JSON formatting is used everywhere
    root_logger = get_logger("umbra.root")
    root_logger.info("Logging system initialized", log_format="json")