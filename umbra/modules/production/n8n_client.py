"""
N8n REST Client for Production Module

Handles all HTTP interactions with the n8n instance including
workflow management, execution, and API communication.
"""

import aiohttp
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from urllib.parse import urljoin

from ...core.config import UmbraConfig

logger = logging.getLogger(__name__)

@dataclass
class N8nCredentials:
    """N8n authentication credentials"""
    api_key: Optional[str] = None
    username: Optional[str] = None  
    password: Optional[str] = None
    auth_type: str = "api_key"  # api_key, basic, none

class N8nClient:
    """REST client for n8n instance communication"""
    
    def __init__(self, config: UmbraConfig):
        self.config = config
        self.base_url = self._resolve_n8n_url()
        self.credentials = self._load_credentials()
        self.session = None
        
        # API endpoints
        self.endpoints = {
            "workflows": "/api/v1/workflows",
            "executions": "/api/v1/executions", 
            "nodes": "/api/v1/nodes",
            "credentials": "/api/v1/credentials",
            "health": "/healthz"
        }
        
        logger.info(f"N8n client initialized for {self.base_url}")
    
    def _resolve_n8n_url(self) -> str:
        """Resolve n8n instance URL"""
        # Try main n8n URL from config
        url = self.config.get("MAIN_N8N_URL")
        if url:
            return url.rstrip("/")
        
        # Try to resolve via Concierge if available
        # TODO: Add Concierge integration for instance resolution
        
        # Default fallback
        return "http://localhost:5678"
    
    def _load_credentials(self) -> N8nCredentials:
        """Load n8n authentication credentials"""
        api_key = self.config.get("N8N_API_KEY")
        username = self.config.get("N8N_USERNAME")
        password = self.config.get("N8N_PASSWORD")
        
        if api_key:
            return N8nCredentials(api_key=api_key, auth_type="api_key")
        elif username and password:
            return N8nCredentials(username=username, password=password, auth_type="basic")
        else:
            return N8nCredentials(auth_type="none")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with auth"""
        if self.session is None:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Add authentication
            auth = None
            if self.credentials.auth_type == "api_key" and self.credentials.api_key:
                headers["X-N8N-API-KEY"] = self.credentials.api_key
            elif self.credentials.auth_type == "basic":
                auth = aiohttp.BasicAuth(self.credentials.username, self.credentials.password)
            
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                headers=headers,
                auth=auth,
                timeout=timeout
            )
        
        return self.session
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated HTTP request"""
        session = await self._get_session()
        url = urljoin(self.base_url, endpoint)
        
        try:
            async with session.request(method, url, **kwargs) as response:
                if response.content_type == "application/json":
                    data = await response.json()
                else:
                    text = await response.text()
                    data = {"text": text}
                
                if response.status >= 400:
                    error_msg = data.get("message", f"HTTP {response.status}")
                    raise Exception(f"N8n API error: {error_msg}")
                
                return data
                
        except aiohttp.ClientError as e:
            logger.error(f"N8n request failed: {e}")
            raise Exception(f"N8n connection error: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check n8n instance health"""
        try:
            result = await self._request("GET", self.endpoints["health"])
            return {"status": "healthy", "data": result}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def list_workflows(self, query: Optional[str] = None, tag: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List workflows with optional filtering"""
        params = {"limit": limit}
        if query:
            params["filter"] = query
        if tag:
            params["tags"] = tag
        
        result = await self._request("GET", self.endpoints["workflows"], params=params)
        return result.get("data", [])
    
    async def get_workflow(self, workflow_id: Optional[str] = None, workflow_name: Optional[str] = None) -> Dict[str, Any]:
        """Get workflow by ID or name"""
        if workflow_id:
            endpoint = f"{self.endpoints['workflows']}/{workflow_id}"
        elif workflow_name:
            # Search by name
            workflows = await self.list_workflows(query=workflow_name)
            matching = [w for w in workflows if w.get("name") == workflow_name]
            if not matching:
                raise Exception(f"Workflow '{workflow_name}' not found")
            workflow_id = matching[0]["id"]
            endpoint = f"{self.endpoints['workflows']}/{workflow_id}"
        else:
            raise Exception("Either workflow_id or workflow_name must be provided")
        
        return await self._request("GET", endpoint)
    
    async def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new workflow"""
        return await self._request("POST", self.endpoints["workflows"], json=workflow_data)
    
    async def update_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing workflow"""
        endpoint = f"{self.endpoints['workflows']}/{workflow_id}"
        return await self._request("PUT", endpoint, json=workflow_data)
    
    async def delete_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Delete workflow"""
        endpoint = f"{self.endpoints['workflows']}/{workflow_id}"
        return await self._request("DELETE", endpoint)
    
    async def enable_workflow(self, workflow_id: str, active: bool = True) -> Dict[str, Any]:
        """Enable or disable workflow"""
        endpoint = f"{self.endpoints['workflows']}/{workflow_id}/activate"
        data = {"active": active}
        return await self._request("POST", endpoint, json=data)
    
    async def run_workflow(self, workflow_id: str, payload: Optional[Dict[str, Any]] = None, timeout_s: int = 60) -> Dict[str, Any]:
        """Execute workflow with optional payload"""
        endpoint = f"{self.endpoints['workflows']}/{workflow_id}/execute"
        data = {}
        if payload:
            data["data"] = payload
        
        # Start execution
        result = await self._request("POST", endpoint, json=data)
        execution_id = result.get("data", {}).get("executionId")
        
        if not execution_id:
            return {"status": "failed", "error": "No execution ID returned"}
        
        # Wait for completion or timeout
        start_time = asyncio.get_event_loop().time()
        while True:
            status = await self.execution_status(execution_id)
            
            if status.get("finished"):
                return {
                    "exec_id": execution_id,
                    "status": "success" if not status.get("stoppedAt") else "stopped",
                    "data": status
                }
            
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout_s:
                return {
                    "exec_id": execution_id,
                    "status": "timeout",
                    "error": f"Execution timeout after {timeout_s}s"
                }
            
            await asyncio.sleep(1)
    
    async def execution_status(self, execution_id: str) -> Dict[str, Any]:
        """Get execution status and results"""
        endpoint = f"{self.endpoints['executions']}/{execution_id}"
        return await self._request("GET", endpoint)
    
    async def list_executions(self, workflow_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List workflow executions"""
        params = {"limit": limit}
        if workflow_id:
            params["workflowId"] = workflow_id
        
        result = await self._request("GET", self.endpoints["executions"], params=params)
        return result.get("data", [])
    
    async def get_node_types(self) -> Dict[str, Any]:
        """Get available node types and their parameters"""
        return await self._request("GET", self.endpoints["nodes"])
    
    async def validate_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate workflow structure (if n8n supports it)"""
        # Some n8n instances have validation endpoints
        try:
            endpoint = "/api/v1/workflows/validate"
            return await self._request("POST", endpoint, json=workflow_data)
        except Exception:
            # Fallback to basic JSON schema validation
            return await self._basic_validate(workflow_data)
    
    async def _basic_validate(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Basic workflow validation"""
        errors = []
        
        # Check required fields
        required_fields = ["name", "nodes", "connections"]
        for field in required_fields:
            if field not in workflow_data:
                errors.append(f"Missing required field: {field}")
        
        # Check nodes structure
        nodes = workflow_data.get("nodes", [])
        if not isinstance(nodes, list):
            errors.append("Nodes must be a list")
        else:
            for i, node in enumerate(nodes):
                if not isinstance(node, dict):
                    errors.append(f"Node {i} must be an object")
                    continue
                
                # Check required node fields
                node_required = ["id", "type", "typeVersion", "position"]
                for field in node_required:
                    if field not in node:
                        errors.append(f"Node {i} missing required field: {field}")
        
        return {
            "ok": len(errors) == 0,
            "errors": errors
        }
    
    async def test_workflow(self, workflow_data: Dict[str, Any], test_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test workflow execution without saving"""
        # Create temporary workflow for testing
        temp_workflow = workflow_data.copy()
        temp_workflow["name"] = f"TEST_{temp_workflow.get('name', 'workflow')}"
        temp_workflow["active"] = False
        
        try:
            # Create temporary workflow
            created = await self.create_workflow(temp_workflow)
            workflow_id = created["id"]
            
            # Run test
            result = await self.run_workflow(workflow_id, test_data)
            
            # Clean up
            await self.delete_workflow(workflow_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Workflow test failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    async def export_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Export workflow as JSON"""
        workflow = await self.get_workflow(workflow_id)
        
        # Clean up for export (remove runtime fields)
        export_data = {
            "name": workflow.get("name"),
            "nodes": workflow.get("nodes", []),
            "connections": workflow.get("connections", {}),
            "settings": workflow.get("settings", {}),
            "staticData": workflow.get("staticData"),
            "tags": workflow.get("tags", []),
            "meta": workflow.get("meta", {})
        }
        
        # Remove None values
        export_data = {k: v for k, v in export_data.items() if v is not None}
        
        return export_data
    
    async def import_workflow(self, workflow_data: Dict[str, Any], mode: str = "create") -> Dict[str, Any]:
        """Import workflow JSON"""
        if mode == "create":
            return await self.create_workflow(workflow_data)
        elif mode == "upsert":
            # Try to find existing workflow by name
            try:
                existing = await self.get_workflow(workflow_name=workflow_data.get("name"))
                return await self.update_workflow(existing["id"], workflow_data)
            except Exception:
                # Create new if not found
                return await self.create_workflow(workflow_data)
        else:
            raise Exception(f"Unknown import mode: {mode}")
