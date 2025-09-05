"""
Base class for all UMBRA modules.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .envelope import InternalEnvelope


class ModuleBase(ABC):
    """Base class for all UMBRA modules."""
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.logger = logging.getLogger(f"umbra.modules.{module_name}")
        self.is_initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the module. Return True if successful."""
        pass
    
    @abstractmethod
    async def register_handlers(self) -> Dict[str, Any]:
        """Register command handlers for the module."""
        pass
    
    @abstractmethod
    async def process_envelope(self, envelope: "InternalEnvelope") -> Optional[str]:
        """Process an internal envelope. Return response string or None."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the module."""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Gracefully shutdown the module."""
        pass
    
    def get_name(self) -> str:
        """Get module name."""
        return self.module_name
    
    def is_ready(self) -> bool:
        """Check if module is initialized and ready."""
        return self.is_initialized