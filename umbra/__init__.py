"""
Umbra Bot - Monolithic Python Implementation
=============================================

A modular monolithic Telegram bot with finance, monitoring, and extensible module system.
Phase 1 implementation focusing on core infrastructure and basic functionality.
"""

__version__ = "1.0.0"
__author__ = "Umbra Development Team"

from .bot import UmbraBot
from .core.envelope import InternalEnvelope
from .core.module_base import ModuleBase
from .core.config import UmbraConfig
from .core.feature_flags import is_enabled

__all__ = [
    "UmbraBot",
    "InternalEnvelope", 
    "ModuleBase",
    "UmbraConfig",
    "is_enabled"
]