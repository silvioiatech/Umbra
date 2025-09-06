"""
Base class for all Umbra MCP modules.

Provides common functionality and interface for all modules.
"""
import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from .logger import get_context_logger
from .envelope import InternalEnvelope


class ModuleBase(ABC):
    """Base class for all Umbra MCP modules."""
    
    def __init__(self, module_name: str):
        """Initialize the module with a name."""
        self.module_name = module_name
        self.logger = get_context_logger(f"modules.{module_name}")
        self._capabilities = []
        
        self.logger.info(f"Initialized {module_name} module")
    
    @property
    def capabilities(self) -> list:
        """Get module capabilities."""
        return self._capabilities
    
    def add_capability(self, capability: str):
        """Add a capability to this module."""
        if capability not in self._capabilities:
            self._capabilities.append(capability)
    
    async def process_envelope(self, envelope: InternalEnvelope) -> str | None:
        """
        Process an internal envelope.
        
        This is the main entry point for legacy module interface.
        Override this method in your module.
        """
        self.logger.warning(
            f"process_envelope not implemented in {self.module_name}",
            extra={
                "action": envelope.action,
                "user_id": envelope.user_id
            }
        )
        return f"Module {self.module_name} received: {envelope.action}"
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an action with parameters.
        
        This is the new F3 interface. Override this method in your module.
        """
        self.logger.info(
            f"Executing action in {self.module_name}",
            extra={
                "action": action,
                "params_count": len(params)
            }
        )
        
        # Default implementation returns success
        return {
            "success": True,
            "message": f"Action {action} executed by {self.module_name}",
            "data": params
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get module status information."""
        return {
            "module_name": self.module_name,
            "capabilities": self._capabilities,
            "status": "active"
        }
    
    def shutdown(self):
        """Shutdown the module and clean up resources."""
        self.logger.info(f"Shutting down {self.module_name} module")
        # Override in subclasses for cleanup