"""
Concierge client for Business module.
Provides a thin client layer that calls Concierge module locally.
"""
import logging
from typing import Any, Dict, Optional

# Import from parent modules - adjust path if needed
try:
    from ...core.envelope import InternalEnvelope
except ImportError:
    # Alternative import path
    from umbra.core.envelope import InternalEnvelope


class ConciergeClient:
    """Thin client that calls Concierge module locally."""
    
    def __init__(self, concierge_module):
        """Initialize with reference to Concierge module."""
        self.concierge = concierge_module
        self.logger = logging.getLogger(__name__)
    
    async def call_concierge(self, action: str, params: Dict[str, Any], *, require_admin: bool = False) -> Dict[str, Any]:
        """Call Concierge action and return result."""
        try:
            # Create envelope for internal communication
            envelope = InternalEnvelope(
                action=action,
                data=params,
                user_id=params.get('user_id'),
                module='business'
            )
            
            # TODO: Add admin permission check if require_admin=True
            # This would check against the config's ALLOWED_ADMIN_IDS
            if require_admin:
                user_id = params.get('user_id')
                if user_id and hasattr(self.concierge, 'config'):
                    admin_ids = getattr(self.concierge.config, 'ALLOWED_ADMIN_IDS', [])
                    if user_id not in admin_ids:
                        return {
                            "ok": False,
                            "error": "Admin permission required for this operation"
                        }
            
            # Call Concierge process_envelope
            result = await self.concierge.process_envelope(envelope)
            
            # Parse result based on action type
            if action.startswith('instances.'):
                # Instance actions return dict results
                if isinstance(result, dict):
                    return result
                else:
                    # If string result, parse as error
                    return {
                        "ok": False,
                        "error": result or "Unknown error from Concierge"
                    }
            else:
                # Other actions return string results
                return {
                    "ok": True,
                    "message": result or "Action completed"
                }
                
        except Exception as e:
            self.logger.error(f"Concierge call failed for {action}: {e}")
            return {
                "ok": False,
                "error": f"Internal error: {str(e)}"
            }
    
    async def create_instance(self, client: str, name: Optional[str] = None, port: Optional[int] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a new client instance."""
        params = {
            "client": client,
            "user_id": user_id
        }
        if name is not None:
            params["name"] = name
        if port is not None:
            params["port"] = port
            
        return await self.call_concierge("instances.create", params)
    
    async def list_instances(self, client: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        """List instances or get single client details."""
        params = {"user_id": user_id}
        if client is not None:
            params["client"] = client
            
        return await self.call_concierge("instances.list", params)
    
    async def delete_instance(self, client: str, mode: str = "keep", user_id: Optional[int] = None) -> Dict[str, Any]:
        """Delete instance with admin permission check."""
        params = {
            "client": client,
            "mode": mode,
            "user_id": user_id
        }
        
        return await self.call_concierge("instances.delete", params, require_admin=True)