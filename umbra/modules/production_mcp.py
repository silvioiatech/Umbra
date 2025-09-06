"""
Production Module - MCP-powered n8n Creator + Orchestrator

Implements prompt → plan → build → validate → test → import workflow creation
with multi-LLM routing, sticky notes, and comprehensive workflow management.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict

from ..ai.agent import UmbraAIAgent
from ..core.config import UmbraConfig
from ..storage.r2_client import R2Client
from .production.planner import WorkflowPlanner
from .production.catalog import CatalogManager
from .production.selector import NodeSelector
from .production.builder import WorkflowBuilder
from .production.controller import ProductionController
from .production.validator import WorkflowValidator
from .production.tester import WorkflowTester
from .production.importer import WorkflowImporter
from .production.exporter import WorkflowExporter
from .production.stickies import StickyNotesManager
from .production.redact import ProductionRedactor
from .production.costs import CostManager
from .production.n8n_client import N8nClient

logger = logging.getLogger(__name__)

@dataclass
class ProductionCapabilities:
    """Production module capabilities"""
    name: str = "production"
    description: str = "n8n workflow creator and orchestrator"
    version: str = "0.1.0"
    
    actions: List[str] = None
    
    def __post_init__(self):
        if self.actions is None:
            self.actions = [
                "plan_from_prompt",
                "scrape_catalog", 
                "select_nodes",
                "build_workflow",
                "validate_workflow",
                "patch_workflow",
                "test_run_workflow",
                "import_workflow",
                "activate_workflow",
                "generate_sticky_notes",
                "list_workflows",
                "get_workflow",
                "enable_workflow",
                "run_workflow",
                "execution_status",
                "export_workflow",
                "import_workflow_file"
            ]

class ProductionModule:
    """Production MCP Module for n8n workflow management"""
    
    def __init__(self, ai_agent: UmbraAIAgent, config: UmbraConfig, r2_client: Optional[R2Client] = None):
        self.ai_agent = ai_agent
        self.config = config
        self.r2_client = r2_client
        
        # Initialize components
        self.n8n_client = N8nClient(config)
        self.planner = WorkflowPlanner(ai_agent, config)
        self.catalog = CatalogManager(self.n8n_client, config)
        self.selector = NodeSelector(ai_agent, config)
        self.builder = WorkflowBuilder(ai_agent, config)
        self.controller = ProductionController(ai_agent, config)
        self.validator = WorkflowValidator(self.n8n_client, config)
        self.tester = WorkflowTester(self.n8n_client, config)
        self.importer = WorkflowImporter(self.n8n_client, config)
        self.exporter = WorkflowExporter(self.n8n_client, config)
        self.stickies = StickyNotesManager(ai_agent, config)
        self.redactor = ProductionRedactor(config)
        self.costs = CostManager(config)
        
        logger.info("Production module initialized")
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return module capabilities"""
        capabilities = ProductionCapabilities()
        return asdict(capabilities)
    
    async def execute(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a production action"""
        if params is None:
            params = {}
            
        try:
            # Route to appropriate handler
            if action == "plan_from_prompt":
                return await self._plan_from_prompt(params)
            elif action == "scrape_catalog":
                return await self._scrape_catalog(params)
            elif action == "select_nodes":
                return await self._select_nodes(params)
            elif action == "build_workflow":
                return await self._build_workflow(params)
            elif action == "validate_workflow":
                return await self._validate_workflow(params)
            elif action == "patch_workflow":
                return await self._patch_workflow(params)
            elif action == "test_run_workflow":
                return await self._test_run_workflow(params)
            elif action == "import_workflow":
                return await self._import_workflow(params)
            elif action == "activate_workflow":
                return await self._activate_workflow(params)
            elif action == "generate_sticky_notes":
                return await self._generate_sticky_notes(params)
            elif action == "list_workflows":
                return await self._list_workflows(params)
            elif action == "get_workflow":
                return await self._get_workflow(params)
            elif action == "enable_workflow":
                return await self._enable_workflow(params)
            elif action == "run_workflow":
                return await self._run_workflow(params)
            elif action == "execution_status":
                return await self._execution_status(params)
            elif action == "export_workflow":
                return await self._export_workflow(params)
            elif action == "import_workflow_file":
                return await self._import_workflow_file(params)
            else:
                return {"error": f"Unknown action: {action}"}
                
        except Exception as e:
            logger.error(f"Error executing {action}: {e}")
            return {"error": str(e)}
    
    async def _plan_from_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create execution plan from user prompt"""
        prompt = params.get("prompt")
        if not prompt:
            return {"error": "prompt is required"}
        
        try:
            plan = await self.planner.plan_from_prompt(prompt)
            
            # Log cost
            await self.costs.log_step_cost("planning", plan.get("tokens_used", 0))
            
            return {"plan": plan, "status": "success"}
        except Exception as e:
            return {"error": f"Planning failed: {e}"}
    
    async def _scrape_catalog(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape node catalog for given steps"""
        steps = params.get("steps", [])
        k = params.get("k", 7)
        budget_tokens = params.get("budget_tokens")
        
        try:
            catalog = await self.catalog.scrape_catalog(steps, k, budget_tokens)
            return {"catalog": catalog, "status": "success"}
        except Exception as e:
            return {"error": f"Catalog scraping failed: {e}"}
    
    async def _select_nodes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Select nodes from catalog based on plan"""
        plan = params.get("plan")
        catalog = params.get("catalog")
        
        if not plan or not catalog:
            return {"error": "plan and catalog are required"}
        
        try:
            mapping = await self.selector.select_nodes(plan, catalog)
            
            # Log cost
            await self.costs.log_step_cost("selection", mapping.get("tokens_used", 0))
            
            return {"mapping": mapping, "status": "success"}
        except Exception as e:
            return {"error": f"Node selection failed: {e}"}
    
    async def _build_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build n8n workflow from node mapping"""
        mapping = params.get("mapping")
        if not mapping:
            return {"error": "mapping is required"}
        
        try:
            workflow = await self.builder.build_workflow(mapping)
            
            # Log cost
            await self.costs.log_step_cost("building", workflow.get("tokens_used", 0))
            
            return {"workflow": workflow, "status": "success"}
        except Exception as e:
            return {"error": f"Workflow building failed: {e}"}
    
    async def _validate_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate workflow structure and schema"""
        workflow_json = params.get("workflow_json")
        if not workflow_json:
            return {"error": "workflow_json is required"}
        
        try:
            result = await self.validator.validate_workflow(workflow_json)
            return result
        except Exception as e:
            return {"error": f"Validation failed: {e}"}
    
    async def _patch_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply patch to workflow"""
        workflow_json = params.get("workflow_json")
        patch = params.get("patch")
        
        if not workflow_json or not patch:
            return {"error": "workflow_json and patch are required"}
        
        try:
            patched = await self.builder.patch_workflow(workflow_json, patch)
            return {"workflow": patched, "status": "success"}
        except Exception as e:
            return {"error": f"Patching failed: {e}"}
    
    async def _test_run_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Test run workflow with sample payload"""
        workflow_json = params.get("workflow_json")
        payload = params.get("payload")
        timeout_s = params.get("timeout_s", 60)
        
        if not workflow_json:
            return {"error": "workflow_json is required"}
        
        try:
            result = await self.tester.test_run_workflow(workflow_json, payload, timeout_s)
            
            # Redact sensitive information
            result = self.redactor.redact_test_result(result)
            
            return result
        except Exception as e:
            return {"error": f"Test run failed: {e}"}
    
    async def _import_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Import workflow to n8n"""
        workflow_json = params.get("workflow_json")
        mode = params.get("mode", "draft")
        dry_run = params.get("dry_run", False)
        
        if not workflow_json:
            return {"error": "workflow_json is required"}
        
        try:
            result = await self.importer.import_workflow(workflow_json, mode, dry_run)
            return result
        except Exception as e:
            return {"error": f"Import failed: {e}"}
    
    async def _activate_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Activate workflow (draft → active)"""
        workflow_id = params.get("id")
        if not workflow_id:
            return {"error": "id is required"}
        
        try:
            result = await self.importer.activate_workflow(workflow_id)
            return result
        except Exception as e:
            return {"error": f"Activation failed: {e}"}
    
    async def _generate_sticky_notes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate sticky notes for workflow"""
        workflow_id = params.get("workflow_id")
        workflow_json = params.get("workflow_json")
        
        if not workflow_id and not workflow_json:
            return {"error": "workflow_id or workflow_json is required"}
        
        try:
            result = await self.stickies.generate_sticky_notes(workflow_id, workflow_json)
            return {"workflow": result, "status": "success"}
        except Exception as e:
            return {"error": f"Sticky notes generation failed: {e}"}
    
    async def _list_workflows(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List workflows with optional filtering"""
        query = params.get("q")
        tag = params.get("tag")
        limit = params.get("limit", 50)
        
        try:
            workflows = await self.n8n_client.list_workflows(query, tag, limit)
            
            # Redact sensitive information
            workflows = self.redactor.redact_workflow_list(workflows)
            
            return {"workflows": workflows, "status": "success"}
        except Exception as e:
            return {"error": f"List workflows failed: {e}"}
    
    async def _get_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get specific workflow"""
        workflow_id = params.get("id")
        workflow_name = params.get("name")
        
        if not workflow_id and not workflow_name:
            return {"error": "id or name is required"}
        
        try:
            workflow = await self.n8n_client.get_workflow(workflow_id, workflow_name)
            
            # Redact sensitive information
            workflow = self.redactor.redact_workflow(workflow)
            
            return {"workflow": workflow, "status": "success"}
        except Exception as e:
            return {"error": f"Get workflow failed: {e}"}
    
    async def _enable_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Enable/disable workflow"""
        workflow_id = params.get("id")
        active = params.get("active", True)
        
        if not workflow_id:
            return {"error": "id is required"}
        
        try:
            result = await self.n8n_client.enable_workflow(workflow_id, active)
            return {"result": result, "status": "success"}
        except Exception as e:
            return {"error": f"Enable/disable failed: {e}"}
    
    async def _run_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run workflow with payload"""
        workflow_id = params.get("id")
        payload = params.get("payload")
        timeout_s = params.get("timeout_s", 60)
        
        if not workflow_id:
            return {"error": "id is required"}
        
        try:
            result = await self.n8n_client.run_workflow(workflow_id, payload, timeout_s)
            
            # Redact sensitive information
            result = self.redactor.redact_execution_result(result)
            
            return result
        except Exception as e:
            return {"error": f"Run workflow failed: {e}"}
    
    async def _execution_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get execution status"""
        exec_id = params.get("exec_id")
        if not exec_id:
            return {"error": "exec_id is required"}
        
        try:
            status = await self.n8n_client.execution_status(exec_id)
            
            # Redact sensitive information
            status = self.redactor.redact_execution_status(status)
            
            return {"status": status}
        except Exception as e:
            return {"error": f"Get execution status failed: {e}"}
    
    async def _export_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export workflow as file"""
        workflow_id = params.get("id")
        if not workflow_id:
            return {"error": "id is required"}
        
        try:
            file_data = await self.exporter.export_workflow(workflow_id)
            return {"file": file_data, "status": "success"}
        except Exception as e:
            return {"error": f"Export failed: {e}"}
    
    async def _import_workflow_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Import workflow from file"""
        file_data = params.get("file")
        mode = params.get("mode", "upsert")
        dry_run = params.get("dry_run", True)
        
        if not file_data:
            return {"error": "file is required"}
        
        try:
            result = await self.importer.import_workflow_file(file_data, mode, dry_run)
            return result
        except Exception as e:
            return {"error": f"Import from file failed: {e}"}

# Module registration
async def get_capabilities() -> Dict[str, Any]:
    """Get production module capabilities"""
    capabilities = ProductionCapabilities()
    return asdict(capabilities)

async def execute(action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute production action with context"""
    ai_agent = context.get("ai_agent")
    config = context.get("config") 
    r2_client = context.get("r2_client")
    
    if not ai_agent or not config:
        return {"error": "Missing required context (ai_agent, config)"}
    
    module = ProductionModule(ai_agent, config, r2_client)
    return await module.execute(action, params)
