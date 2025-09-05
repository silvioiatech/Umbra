"""
Business MCP - Thin Telegram → Concierge Gateway
Manages VPS client n8n instances via Concierge APIs.
Business itself stores nothing; all operations forwarded to Concierge.
"""
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..core.envelope import InternalEnvelope
from ..core.module_base import ModuleBase
from .business.concierge_client import ConciergeClient
from .business.formatters import (
    format_instance_summary, format_instance_details, format_instances_list,
    format_creation_result, format_deletion_result, format_error, format_help
)


class BusinessMCP(ModuleBase):
    """Thin Telegram → Concierge gateway for VPS client n8n instances."""

    def __init__(self, config, db_manager):
        super().__init__("business")
        self.config = config
        self.db = db_manager
        
        # Port validation configuration
        self.client_port_range = self._parse_port_range(
            getattr(config, 'CLIENT_PORT_RANGE', '20000-21000')
        )
        
        # Will be set when Concierge module is available
        self.concierge_client = None

    async def initialize(self) -> bool:
        """Initialize the Business module."""
        try:
            self.logger.info("Business module initialized as Concierge gateway")
            return True
        except Exception as e:
            self.logger.error(f"Business initialization failed: {e}")
            return False

    def set_concierge_module(self, concierge_module):
        """Set reference to Concierge module for client operations."""
        self.concierge_client = ConciergeClient(concierge_module)
        self.logger.info("Business gateway connected to Concierge module")

    async def register_handlers(self) -> dict[str, Any]:
        """Register command handlers for the Business module."""
        return {
            "inst help": self.show_help,
            "create instance": self.create_instance,
            "list instances": self.list_instances,
            "show instance": self.show_instance,
            "delete instance": self.delete_instance
        }

    async def process_envelope(self, envelope: InternalEnvelope) -> str | None:
        """Process envelope for Business gateway operations."""
        action = envelope.action.lower()
        data = envelope.data

        # Route to execute method for MCP-style handling
        if action in ["create_instance", "list_instances", "delete_instance"]:
            result = await self.execute(action, data)
            if isinstance(result, dict):
                # Format result based on action
                if action == "create_instance":
                    return format_creation_result(result)
                elif action == "list_instances":
                    if result.get('ok') and 'instances' in result:
                        return format_instances_list(result['instances'])
                    elif result.get('ok'):
                        return format_instance_details(result)
                    else:
                        return format_error(result.get('error', 'Unknown error'))
                elif action == "delete_instance":
                    return format_deletion_result(result)
            
            return format_error("Unexpected result format")

        # Direct command handlers
        handlers = {
            "inst help": lambda: self.show_help(),
            "create instance": lambda: self.create_instance_command(data),
            "list instances": lambda: self.list_instances_command(data),
            "show instance": lambda: self.show_instance_command(data),
            "delete instance": lambda: self.delete_instance_command(data)
        }

        handler = handlers.get(action)
        return await handler() if handler else None

    # MCP-style API methods
    def get_capabilities(self) -> List[str]:
        """Return list of available capabilities."""
        return [
            "create_instance",
            "list_instances", 
            "delete_instance"
        ]

    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action with parameters (MCP-style)."""
        if not self.concierge_client:
            return {
                "ok": False,
                "error": "Concierge gateway not available"
            }

        try:
            if action == "create_instance":
                return await self._execute_create_instance(params)
            elif action == "list_instances":
                return await self._execute_list_instances(params)
            elif action == "delete_instance":
                return await self._execute_delete_instance(params)
            else:
                return {
                    "ok": False,
                    "error": f"Unknown action: {action}"
                }
        except Exception as e:
            self.logger.error(f"Execute action {action} failed: {e}")
            return {
                "ok": False,
                "error": f"Action execution failed: {str(e)}"
            }

    # Command handlers for Telegram
    async def show_help(self) -> str:
        """Show help for instance commands."""
        return format_help()

    async def create_instance_command(self, data: Dict[str, Any]) -> str:
        """Handle create instance command from Telegram."""
        client = data.get("client_name", data.get("client", ""))
        name = data.get("name")
        port = data.get("port")
        user_id = data.get("user_id")

        result = await self.execute("create_instance", {
            "client": client,
            "name": name,
            "port": port,
            "user_id": user_id
        })

        return format_creation_result(result)

    async def list_instances_command(self, data: Dict[str, Any]) -> str:
        """Handle list instances command from Telegram."""
        user_id = data.get("user_id")
        
        result = await self.execute("list_instances", {
            "user_id": user_id
        })

        if result.get('ok') and 'instances' in result:
            return format_instances_list(result['instances'])
        else:
            return format_error(result.get('error', 'Failed to list instances'))

    async def show_instance_command(self, data: Dict[str, Any]) -> str:
        """Handle show instance command from Telegram."""
        client = data.get("client_name", data.get("client", ""))
        user_id = data.get("user_id")

        if not client:
            return format_error("Client name required")

        result = await self.execute("list_instances", {
            "client": client,
            "user_id": user_id
        })

        if result.get('ok') and 'instances' not in result:
            # Single instance details
            return format_instance_details(result)
        else:
            return format_error(result.get('error', 'Instance not found'))

    async def delete_instance_command(self, data: Dict[str, Any]) -> str:
        """Handle delete instance command from Telegram."""
        client = data.get("client_name", data.get("client", ""))
        mode = data.get("mode", "keep")
        user_id = data.get("user_id")

        if not client:
            return format_error("Client name required")

        result = await self.execute("delete_instance", {
            "client": client,
            "mode": mode,
            "user_id": user_id
        })

        return format_deletion_result(result)

    # Internal execute methods (validation + Concierge forwarding)
    async def _execute_create_instance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute create instance with validation."""
        client = params.get("client", "")
        name = params.get("name")
        port = params.get("port")
        user_id = params.get("user_id")

        # Validate client slug
        if not self._validate_client_slug(client):
            return {
                "ok": False,
                "error": "Invalid client slug. Must be [a-z0-9-] max 32 chars."
            }

        # Validate port if provided
        if port is not None:
            try:
                port = int(port)
                if not self._validate_port(port):
                    start, end = self.client_port_range
                    return {
                        "ok": False,
                        "error": f"Port {port} outside allowed range {start}-{end}"
                    }
            except (ValueError, TypeError):
                return {
                    "ok": False,
                    "error": "Invalid port number"
                }

        # Forward to Concierge
        return await self.concierge_client.create_instance(client, name, port, user_id)

    async def _execute_list_instances(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute list instances with validation."""
        client = params.get("client")
        user_id = params.get("user_id")

        # Validate client slug if provided
        if client is not None and not self._validate_client_slug(client):
            return {
                "ok": False,
                "error": "Invalid client slug"
            }

        # Forward to Concierge
        return await self.concierge_client.list_instances(client, user_id)

    async def _execute_delete_instance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute delete instance with validation."""
        client = params.get("client", "")
        mode = params.get("mode", "keep")
        user_id = params.get("user_id")

        # Validate client slug
        if not self._validate_client_slug(client):
            return {
                "ok": False,
                "error": "Invalid client slug"
            }

        # Validate mode
        if mode not in ["keep", "wipe"]:
            return {
                "ok": False,
                "error": "Mode must be 'keep' or 'wipe'"
            }

        # Forward to Concierge (with admin check)
        return await self.concierge_client.delete_instance(client, mode, user_id)

    # Validation helpers
    def _validate_client_slug(self, client: str) -> bool:
        """Validate client slug format: [a-z0-9-]{1,32}."""
        if not client or len(client) > 32:
            return False
        return bool(re.match(r'^[a-z0-9\-]+$', client))

    def _validate_port(self, port: int) -> bool:
        """Validate port is within allowed range."""
        start, end = self.client_port_range
        return start <= port <= end

    def _parse_port_range(self, port_range_str: str) -> tuple[int, int]:
        """Parse port range string like '20000-21000'."""
        try:
            start, end = port_range_str.split('-')
            return (int(start.strip()), int(end.strip()))
        except (ValueError, AttributeError):
            self.logger.warning(f"Invalid port range '{port_range_str}', using default 20000-21000")
            return (20000, 21000)

    async def health_check(self) -> dict[str, Any]:
        """Perform health check of the Business gateway."""
        try:
            # Check if Concierge client is available
            if not self.concierge_client:
                return {
                    "status": "unhealthy",
                    "error": "Concierge client not initialized"
                }

            # Test connection to Concierge by listing instances
            test_result = await self.concierge_client.list_instances()
            
            return {
                "status": "healthy",
                "message": "Business gateway operational",
                "details": {
                    "concierge_connected": test_result.get('ok', False),
                    "port_range": f"{self.client_port_range[0]}-{self.client_port_range[1]}",
                    "capabilities": self.get_capabilities()
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def shutdown(self):
        """Gracefully shutdown the Business module."""
        try:
            self.logger.info("Business gateway shutdown complete")
        except Exception as e:
            self.logger.error(f"Business shutdown error: {e}")