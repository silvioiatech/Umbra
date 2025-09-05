"""
Base class for UMBRA modules.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .envelope import InternalEnvelope


class ModuleBase(ABC):
    """Base class for all UMBRA modules."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"umbra.modules.{name}")
        self.enabled = True
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the module."""
        pass
    
    @abstractmethod
    async def register_handlers(self) -> Dict[str, Any]:
        """Register command handlers for the module."""
        pass
    
    @abstractmethod
    async def process_envelope(self, envelope: InternalEnvelope) -> Optional[str]:
        """Process envelope for module operations."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the module."""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Gracefully shutdown the module."""
        pass