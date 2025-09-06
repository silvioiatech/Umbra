"""
Concierge Bridge for Business Module

Provides a clean interface for Business module to communicate with
Concierge instances registry without tight coupling.
"""
from typing import Dict, Any, Optional
import asyncio

from ...core.logger import get_context_logger

class ConciergeBridge:
    """
    Bridge to Concierge module for instance operations.
    
    Handles communication with Concierge's instances registry,
    including error handling, retries, and result formatting.
    """
    
    def __init__(self, concierge_module=None):
        self.concierge_module = concierge_module
        self.logger = get_context_logger(__name__)
        
        self.logger.info(
            "Concierge bridge initialized",
            extra={
                "concierge_available": self.is_available(),
                "mode": "direct_module_call"
            }
        )
    
    def is_available(self) -> bool:
        """Check if Concierge module is available."""
        return (
            self.concierge_module is not None and 
            hasattr(self.concierge_module, 'execute')
        )
    
    async def call_concierge(
        self, 
        action: str, 
        params: Dict[str, Any], 
        user_id: int = 0,
        require_admin: bool = False
    ) -> Dict[str, Any]:
        """
        Call Concierge module action with error handling.
        
        Args:
            action: Concierge action to execute
            params: Parameters for the action
            user_id: User ID for audit trail
            require_admin: Whether admin privileges are required
        
        Returns:
            Result dictionary from Concierge
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "Concierge module not available"
            }
        
        try:
            self.logger.info(
                f"Calling Concierge action: {action}",
                extra={
                    "action": action,
                    "user_id": user_id,
                    "require_admin": require_admin,
                    "params_count": len(params)
                }
            )
            
            # Call Concierge module directly
            result = await self.concierge_module.execute(
                action=action,
                params=params,
                user_id=user_id,
                is_admin=require_admin  # For now, assume admin requirement matches is_admin
            )
            
            # Log result
            success = result.get("success", False)
            self.logger.info(
                f"Concierge call completed: {action}",
                extra={
                    "action": action,
                    "success": success,
                    "user_id": user_id,
                    "has_audit_id": "audit_id" in result
                }
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Concierge call failed: {str(e)}"
            self.logger.error(
                error_msg,
                extra={
                    "action": action,
                    "user_id": user_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            return {
                "success": False,
                "error": error_msg
            }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to Concierge module."""
        if not self.is_available():
            return {
                "success": False,
                "error": "Concierge module not loaded"
            }
        
        try:
            # Try a simple non-destructive call
            result = await self.call_concierge("instances.stats", {}, user_id=0)
            
            return {
                "success": result.get("success", False),
                "message": "Concierge connection test completed",
                "concierge_result": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection test failed: {str(e)}"
            }
    
    def get_supported_actions(self) -> list:
        """Get list of supported Concierge actions for instances."""
        return [
            "instances.create",
            "instances.list", 
            "instances.delete",
            "instances.stats"
        ]
    
    async def validate_action(self, action: str) -> Dict[str, Any]:
        """Validate that an action is supported by Concierge."""
        if not self.is_available():
            return {
                "valid": False,
                "error": "Concierge module not available"
            }
        
        supported_actions = self.get_supported_actions()
        
        if action not in supported_actions:
            return {
                "valid": False,
                "error": f"Action '{action}' not supported. Available: {supported_actions}"
            }
        
        return {
            "valid": True,
            "action": action
        }

# Export
__all__ = ["ConciergeBridge"]
