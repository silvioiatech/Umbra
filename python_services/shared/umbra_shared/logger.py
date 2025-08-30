"""Structured logging utility for Umbra services."""

import structlog
import logging
import sys
from typing import Any, Dict, Optional
from datetime import datetime


class UmbraLogger:
    """Structured logger for Umbra services."""
    
    def __init__(self, service_name: str, log_level: str = "INFO"):
        self.service_name = service_name
        
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            context_class=structlog.threadlocal.wrap_dict(dict),
            cache_logger_on_first_use=True,
        )
        
        # Configure stdlib logging
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, log_level.upper()),
        )
        
        self.logger = structlog.get_logger(service_name)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, **kwargs)
    
    def warn(self, message: str, **kwargs):
        """Alias for warning."""
        self.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.logger.critical(message, **kwargs)
    
    def audit(self, message: str, user_id: str, **kwargs):
        """Log audit message with user context."""
        self.logger.info(
            message,
            audit=True,
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat(),
            **kwargs
        )
    
    def with_context(self, **kwargs) -> 'UmbraLogger':
        """Create logger with additional context."""
        new_logger = UmbraLogger(self.service_name)
        new_logger.logger = self.logger.bind(**kwargs)
        return new_logger


# Global logger instance
_global_logger: Optional[UmbraLogger] = None


def get_logger(service_name: str = "umbra") -> UmbraLogger:
    """Get or create global logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = UmbraLogger(service_name)
    return _global_logger


def setup_logger(service_name: str, log_level: str = "INFO") -> UmbraLogger:
    """Setup and return logger for a service."""
    return UmbraLogger(service_name, log_level)