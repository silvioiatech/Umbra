"""Core abstractions for the Umbra Bot system."""

from .envelope import InternalEnvelope
from .module_base import ModuleBase
from .config import UmbraConfig
from .feature_flags import is_enabled
from .logger import get_logger

__all__ = [
    "InternalEnvelope",
    "ModuleBase", 
    "UmbraConfig",
    "is_enabled",
    "get_logger"
]