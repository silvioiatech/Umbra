"""
Base class for MCP modules.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ModuleBase(ABC):
    """Base class for all MCP modules."""
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.logger = logging.getLogger(f"umbra.modules.{module_name}")
        
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the module."""
        pass
        
    @abstractmethod
    async def register_handlers(self) -> Dict[str, Any]:
        """Register command handlers for the module."""
        pass
        
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the module."""
        pass
        
    @abstractmethod
    async def shutdown(self):
        """Gracefully shutdown the module."""
        pass