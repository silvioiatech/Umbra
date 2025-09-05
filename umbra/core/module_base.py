"""Base class for all MCP modules."""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict


class ModuleBase(ABC):
    """Abstract base class for all MCP modules."""
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.logger = logging.getLogger(f"{__name__}.{module_name}")
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the module. Return True if successful."""
        pass
    
    @abstractmethod
    async def register_handlers(self) -> Dict[str, Any]:
        """Register command handlers for the module."""
        pass
    
    @abstractmethod
    async def process_envelope(self, envelope: 'InternalEnvelope') -> str | None:
        """Process an internal envelope."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the module."""
        pass
    
    async def shutdown(self):
        """Gracefully shutdown the module."""
        self.logger.info(f"{self.module_name} module shutting down")