"""Core infrastructure for Umbra bot."""

from .config import UmbraConfig
from .permissions import PermissionManager
from .logger import setup_logging, get_logger

# Lazy import for config instance to avoid initialization during tests
def get_config():
    """Get the global config instance."""
    from .config import config
    return config

__all__ = ["UmbraConfig", "PermissionManager", "setup_logging", "get_logger", "get_config"]
