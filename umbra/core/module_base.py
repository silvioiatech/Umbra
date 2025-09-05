"""
Base class for Umbra MCP modules.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict


class ModuleBase(ABC):
    """Base class for all Umbra MCP modules."""
    
    def __init__(self, module_name: str):
        """Initialize module with name."""
        self.module_name = module_name
        self.logger = logging.getLogger(f"umbra.modules.{module_name}")
    
    async def initialize(self) -> bool:
        """Initialize the module. Override in subclasses."""
        return True
    
    async def shutdown(self):
        """Shutdown the module. Override in subclasses."""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check. Override in subclasses."""
        return {
            "status": "healthy",
            "module": self.module_name
        }
    
    async def register_handlers(self) -> Dict[str, Any]:
        """Register command handlers. Override in subclasses."""
        return {}
    
    async def process_envelope(self, envelope: 'InternalEnvelope') -> str | None:
        """Process envelope. Override in subclasses."""
        return None