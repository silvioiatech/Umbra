"""
Base class for MCP-style modules.
Provides standard interface for module discovery and execution.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .envelope import InternalEnvelope


class ModuleBase(ABC):
    """Base class for all MCP-style modules."""
    
    def __init__(self, module_id: str):
        self.module_id = module_id
        self.logger = logging.getLogger(f"umbra.modules.{module_id}")
        self._capabilities = []
        self._handlers = {}
    
    async def initialize(self) -> bool:
        """Initialize the module. Override in subclasses."""
        return True
    
    @abstractmethod
    async def register_handlers(self) -> Dict[str, Any]:
        """Register command handlers. Must be implemented by subclasses."""
        pass
    
    def get_capabilities(self) -> List[str]:
        """Get list of capabilities/actions this module can perform."""
        if not self._capabilities:
            # Fallback to handler keys if capabilities not explicitly set
            return list(self._handlers.keys())
        return self._capabilities
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action with parameters. Standard MCP interface."""
        try:
            # Get handlers if not cached
            if not self._handlers:
                self._handlers = await self.register_handlers()
            
            # Find handler for action
            handler = None
            action_lower = action.lower()
            
            # Try exact match first
            if action_lower in self._handlers:
                handler = self._handlers[action_lower]
            else:
                # Try partial matches
                for key, func in self._handlers.items():
                    if action_lower in key.lower() or key.lower() in action_lower:
                        handler = func
                        break
            
            if handler:
                # Call handler with parameters
                if callable(handler):
                    result = await handler(**params) if hasattr(handler, '__await__') else handler(**params)
                    return {
                        "success": True,
                        "data": result,
                        "action": action,
                        "module": self.module_id
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Handler for '{action}' is not callable",
                        "action": action,
                        "module": self.module_id
                    }
            else:
                return {
                    "success": False,
                    "error": f"Action '{action}' not supported by {self.module_id}",
                    "available_actions": list(self._handlers.keys()),
                    "action": action,
                    "module": self.module_id
                }
                
        except Exception as e:
            self.logger.error(f"Error executing {action}: {e}")
            return {
                "success": False,
                "error": str(e),
                "action": action,
                "module": self.module_id
            }
    
    async def process_envelope(self, envelope: InternalEnvelope) -> Optional[str]:
        """Process internal envelope. Legacy interface for existing modules."""
        return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the module."""
        return {
            "module": self.module_id,
            "status": "healthy",
            "capabilities": self.get_capabilities()
        }