"""
Business MCP v0 - Instance Gateway via Concierge

Thin Telegram gateway for managing client n8n instances through Concierge.
Business module stores nothing - all operations are forwarded to Concierge's
instances registry with pass-through audit trails and permissions.

Key Features:
- Pass-through to Concierge instances registry
- Instance creation, listing, and deletion
- RBAC and approval integration
- Comprehensive error propagation
- Telegram-optimized formatting
"""
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from ..core.logger import get_context_logger
from .business.concierge_client import ConciergeBridge
from .business.formatters import InstanceFormatter

@dataclass
class InstanceSummary:
    """Summary information for instance listing."""
    client_id: str
    display_name: str
    url: str
    port: int
    status: str

@dataclass
class InstanceDetails:
    """Detailed information for single instance view."""
    client_id: str
    display_name: str
    url: str
    port: int
    status: str
    data_dir: str
    reserved: bool
    created_at: str
    updated_at: str

@dataclass
class DeletionResult:
    """Result of instance deletion operation."""
    ok: bool
    mode: str
    audit_id: Optional[str] = None
    message: Optional[str] = None

class BusinessMCP:
    """
    Business MCP v0: Instance gateway via Concierge
    
    Provides a user-friendly interface for managing client n8n instances
    while delegating all actual operations to the Concierge module's
    instances registry.
    """
    
    def __init__(self, config, db_manager, concierge_module=None):
        self.config = config
        self.db = db_manager
        self.logger = get_context_logger(__name__)
        
        # Initialize Concierge bridge
        self.concierge_bridge = ConciergeBridge(concierge_module)
        
        # Initialize formatter
        self.formatter = InstanceFormatter()
        
        # Configuration
        self.client_port_range = self._parse_port_range(
            getattr(config, 'CLIENT_PORT_RANGE', '20000-21000')
        )
        
        # Validation patterns
        self.client_id_pattern = re.compile(r'^[a-z0-9\-]{1,32}$')
        
        self.logger.info(
            "Business MCP v0 initialized",
            extra={
                "mode": "instance_gateway",
                "backend": "concierge_passthrough",
                "port_range": f"{self.client_port_range[0]}-{self.client_port_range[1]}",
                "concierge_available": self.concierge_bridge.is_available()
            }
        )
    
    def _parse_port_range(self, port_range_str: str) -> Tuple[int, int]:
        """Parse port range string like '20000-21000'."""
        try:
            start_str, end_str = port_range_str.split('-')
            start_port = int(start_str.strip())
            end_port = int(end_str.strip())
            
            if start_port >= end_port or start_port < 1024 or end_port > 65535:
                raise ValueError(f"Invalid port range: {port_range_str}")
            
            return (start_port, end_port)
        except Exception as e:
            self.logger.error(f"Failed to parse port range '{port_range_str}': {e}")
            # Fallback to default
            return (20000, 21000)
    
    async def get_capabilities(self) -> Dict[str, Any]:
        """Get capabilities exposed by Business module."""
        return {
            "create_instance": {
                "description": "Create new client n8n instance via Concierge",
                "parameters": {
                    "client": {"type": "string", "description": "Client ID (lowercase alphanumeric, hyphens allowed, max 32 chars)"},
                    "name": {"type": "string", "description": "Display name for instance", "default": None},
                    "port": {"type": "integer", "description": f"Specific port ({self.client_port_range[0]}-{self.client_port_range[1]})", "default": None}
                },
                "admin_only": True,
                "requires_approval": True
            },
            "list_instances": {
                "description": "List client instances or get details for specific client",
                "parameters": {
                    "client": {"type": "string", "description": "Filter by specific client ID", "default": None}
                },
                "admin_only": False
            },
            "delete_instance": {
                "description": "Delete client instance with data preservation options",
                "parameters": {
                    "client": {"type": "string", "description": "Client ID to delete"},
                    "mode": {"type": "string", "description": "Deletion mode", "enum": ["keep", "wipe"], "default": "keep"}
                },
                "admin_only": True,
                "requires_approval": True
            },
            "instance_stats": {
                "description": "Get instance registry statistics",
                "parameters": {},
                "admin_only": False
            }
        }
    
    async def execute(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool = False) -> Dict[str, Any]:
        """
        Execute Business action with validation and pass-through to Concierge.
        
        Args:
            action: Action to execute
            params: Action parameters
            user_id: User requesting the action
            is_admin: Whether user has admin privileges
        
        Returns:
            Execution result with success/error information
        """
        # Check Concierge availability
        if not self.concierge_bridge.is_available():
            return {
                "success": False,
                "error": "Instance management not available (Concierge module not loaded)"
            }
        
        # Get capabilities to check permissions
        capabilities = await self.get_capabilities()
        
        if action not in capabilities:
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "available_actions": list(capabilities.keys())
            }
        
        capability = capabilities[action]
        
        # Check admin requirements
        if capability.get("admin_only", False) and not is_admin:
            return {
                "success": False,
                "error": "Admin access required for this action"
            }
        
        try:
            # Route to appropriate handler
            if action == "create_instance":
                return await self._handle_create_instance(params, user_id, is_admin)
            elif action == "list_instances":
                return await self._handle_list_instances(params, user_id, is_admin)
            elif action == "delete_instance":
                return await self._handle_delete_instance(params, user_id, is_admin)
            elif action == "instance_stats":
                return await self._handle_instance_stats(params, user_id, is_admin)
            else:
                return {
                    "success": False,
                    "error": f"Action handler not implemented: {action}"
                }
                
        except Exception as e:
            self.logger.error(
                f"Business action failed: {action}",
                extra={"error": str(e), "user_id": user_id, "params": params}
            )
            
            return {
                "success": False,
                "error": f"Action execution failed: {str(e)[:200]}"
            }
    
    async def _handle_create_instance(self, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle instance creation with validation."""
        
        client = params.get("client", "").strip().lower()
        name = params.get("name")
        port = params.get("port")
        
        # Validate client ID
        validation_error = self._validate_client_id(client)
        if validation_error:
            return {"success": False, "error": validation_error}
        
        # Validate port if specified
        if port is not None:
            port_validation_error = self._validate_port(port)
            if port_validation_error:
                return {"success": False, "error": port_validation_error}
        
        # Forward to Concierge
        try:
            concierge_params = {
                "client": client,
                "name": name,
                "port": port
            }
            
            result = await self.concierge_bridge.call_concierge(
                "instances.create", 
                concierge_params, 
                user_id=user_id,
                require_admin=True
            )
            
            if result.get("success"):
                # Format response for Business module
                instance_data = result.get("instance", {})
                
                return {
                    "success": True,
                    "instance": InstanceSummary(
                        client_id=instance_data.get("client_id"),
                        display_name=instance_data.get("display_name"),
                        url=instance_data.get("url"),
                        port=instance_data.get("port"),
                        status=instance_data.get("status")
                    ).__dict__,
                    "audit_id": result.get("audit_id"),
                    "message": result.get("message"),
                    "formatted": self.formatter.format_instance_created(instance_data)
                }
            else:
                # Pass through error from Concierge
                return {
                    "success": False,
                    "error": result.get("error"),
                    "audit_id": result.get("audit_id")
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create instance: {str(e)}"
            }
    
    async def _handle_list_instances(self, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle instance listing."""
        
        client_filter = params.get("client")
        
        # Validate client filter if specified
        if client_filter:
            client_filter = client_filter.strip().lower()
            validation_error = self._validate_client_id(client_filter)
            if validation_error:
                return {"success": False, "error": validation_error}
        
        # Forward to Concierge
        try:
            concierge_params = {"client": client_filter} if client_filter else {}
            
            result = await self.concierge_bridge.call_concierge(
                "instances.list",
                concierge_params,
                user_id=user_id
            )
            
            if result.get("success"):
                instances_data = result.get("instances", [])
                
                if client_filter and len(instances_data) == 1:
                    # Single instance - return detailed view
                    instance = instances_data[0]
                    details = InstanceDetails(
                        client_id=instance.get("client_id"),
                        display_name=instance.get("display_name"),
                        url=instance.get("url"),
                        port=instance.get("port"),
                        status=instance.get("status"),
                        data_dir=instance.get("data_dir"),
                        reserved=instance.get("reserved", False),
                        created_at=instance.get("created_at"),
                        updated_at=instance.get("updated_at")
                    )
                    
                    return {
                        "success": True,
                        "instance": details.__dict__,
                        "formatted": self.formatter.format_instance_details(details.__dict__)
                    }
                else:
                    # Multiple instances - return summary list
                    summaries = []
                    for instance in instances_data:
                        summary = InstanceSummary(
                            client_id=instance.get("client_id"),
                            display_name=instance.get("display_name"),
                            url=instance.get("url"),
                            port=instance.get("port"),
                            status=instance.get("status")
                        )
                        summaries.append(summary.__dict__)
                    
                    return {
                        "success": True,
                        "instances": summaries,
                        "count": len(summaries),
                        "formatted": self.formatter.format_instances_list(summaries)
                    }
            else:
                # Pass through error from Concierge
                return {
                    "success": False,
                    "error": result.get("error")
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list instances: {str(e)}"
            }
    
    async def _handle_delete_instance(self, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle instance deletion with validation."""
        
        client = params.get("client", "").strip().lower()
        mode = params.get("mode", "keep").strip().lower()
        
        # Validate client ID
        validation_error = self._validate_client_id(client)
        if validation_error:
            return {"success": False, "error": validation_error}
        
        # Validate mode
        if mode not in ["keep", "wipe"]:
            return {
                "success": False,
                "error": "Mode must be 'keep' (preserve data) or 'wipe' (remove all data)"
            }
        
        # Forward to Concierge
        try:
            concierge_params = {
                "client": client,
                "mode": mode
            }
            
            result = await self.concierge_bridge.call_concierge(
                "instances.delete",
                concierge_params,
                user_id=user_id,
                require_admin=True
            )
            
            if result.get("success"):
                deletion_result = DeletionResult(
                    ok=True,
                    mode=mode,
                    audit_id=result.get("audit_id"),
                    message=result.get("message")
                )
                
                return {
                    "success": True,
                    "result": deletion_result.__dict__,
                    "audit_id": result.get("audit_id"),
                    "message": result.get("message"),
                    "formatted": self.formatter.format_deletion_result(deletion_result.__dict__)
                }
            else:
                # Pass through error from Concierge
                return {
                    "success": False,
                    "error": result.get("error"),
                    "audit_id": result.get("audit_id")
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete instance: {str(e)}"
            }
    
    async def _handle_instance_stats(self, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle instance statistics request."""
        
        # Forward to Concierge
        try:
            result = await self.concierge_bridge.call_concierge(
                "instances.stats",
                {},
                user_id=user_id
            )
            
            if result.get("success"):
                return {
                    "success": True,
                    "stats": result,
                    "formatted": self.formatter.format_instance_stats(result)
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error")
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get instance stats: {str(e)}"
            }
    
    def _validate_client_id(self, client_id: str) -> Optional[str]:
        """Validate client ID format."""
        if not client_id:
            return "Client ID is required"
        
        if not self.client_id_pattern.match(client_id):
            return (
                "Client ID must be lowercase alphanumeric with hyphens, "
                "1-32 characters (e.g., 'client1', 'test-client')"
            )
        
        return None
    
    def _validate_port(self, port: int) -> Optional[str]:
        """Validate port number."""
        start_port, end_port = self.client_port_range
        
        if not isinstance(port, int):
            return "Port must be a number"
        
        if port < start_port or port > end_port:
            return f"Port must be in range {start_port}-{end_port}"
        
        return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of Business module."""
        try:
            checks = {}
            
            # Check Concierge bridge
            if self.concierge_bridge.is_available():
                try:
                    # Try to get instance stats as a connectivity test
                    result = await self.concierge_bridge.call_concierge(
                        "instances.stats", {}, user_id=0
                    )
                    checks["concierge_bridge"] = {
                        "status": "ok" if result.get("success") else "warning",
                        "details": "Concierge instances registry accessible"
                    }
                except Exception as e:
                    checks["concierge_bridge"] = {
                        "status": "error",
                        "details": f"Concierge call failed: {str(e)}"
                    }
            else:
                checks["concierge_bridge"] = {
                    "status": "error",
                    "details": "Concierge module not available"
                }
            
            # Check configuration
            try:
                checks["configuration"] = {
                    "status": "ok",
                    "details": f"Port range: {self.client_port_range[0]}-{self.client_port_range[1]}"
                }
            except Exception as e:
                checks["configuration"] = {
                    "status": "error",
                    "details": f"Configuration error: {str(e)}"
                }
            
            # Overall status
            error_count = len([c for c in checks.values() if c["status"] == "error"])
            
            if error_count == 0:
                overall_status = "healthy"
            elif error_count <= 1:
                overall_status = "degraded"
            else:
                overall_status = "unhealthy"
            
            return {
                "status": overall_status,
                "checks": checks,
                "mode": "instance_gateway",
                "backend": "concierge_passthrough"
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# Export
__all__ = ["BusinessMCP", "InstanceSummary", "InstanceDetails", "DeletionResult"]
