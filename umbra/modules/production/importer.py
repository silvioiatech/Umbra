"""
Workflow Importer for Production Module

Handles importing workflows to n8n with draft-first approach, 
dry-run capabilities, and conflict resolution.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import difflib
import uuid

from ...core.config import UmbraConfig
from .n8n_client import N8nClient

logger = logging.getLogger(__name__)

@dataclass
class ImportConflict:
    """Represents a conflict during import"""
    type: str  # "name_exists", "id_conflict", "credential_missing"
    message: str
    current_value: Optional[str]
    new_value: Optional[str]
    resolution: Optional[str] = None

@dataclass
class ImportDiff:
    """Represents differences between current and new workflow"""
    field: str
    operation: str  # "add", "remove", "modify"
    old_value: Optional[Any]
    new_value: Optional[Any]
    location: str

@dataclass
class ImportResult:
    """Complete import operation result"""
    success: bool
    workflow_id: Optional[str]
    mode: str
    conflicts: List[ImportConflict]
    diffs: List[ImportDiff]
    dry_run: bool
    warnings: List[str]
    metadata: Dict[str, Any]

class WorkflowImporter:
    """Imports workflows to n8n with advanced conflict handling"""
    
    def __init__(self, n8n_client: N8nClient, config: UmbraConfig):
        self.n8n_client = n8n_client
        self.config = config
        
        # Import settings
        self.draft_prefix = config.get("PROD_DRAFT_PREFIX", "DRAFT")
        self.backup_enabled = config.get("PROD_BACKUP_ON_IMPORT", True)
        self.max_draft_versions = config.get("PROD_MAX_DRAFT_VERSIONS", 10)
        
        logger.info("Workflow importer initialized")
    
    async def import_workflow(self, workflow_json: Dict[str, Any], mode: str = "draft", dry_run: bool = False) -> Dict[str, Any]:
        """Import workflow with specified mode"""
        try:
            # Validate input
            if not workflow_json or "name" not in workflow_json:
                raise Exception("Invalid workflow data: missing name")
            
            # Prepare workflow for import
            prepared_workflow = await self._prepare_workflow_for_import(workflow_json, mode)
            
            # Check for conflicts
            conflicts = await self._detect_conflicts(prepared_workflow, mode)
            
            # Generate diff if updating existing workflow
            diffs = await self._generate_diffs(prepared_workflow, mode)
            
            # Execute import or return dry-run results
            if dry_run:
                result = ImportResult(
                    success=True,
                    workflow_id=None,
                    mode=mode,
                    conflicts=conflicts,
                    diffs=diffs,
                    dry_run=True,
                    warnings=self._generate_warnings(conflicts, diffs),
                    metadata={"prepared_workflow": prepared_workflow}
                )
            else:
                # Perform actual import
                result = await self._execute_import(prepared_workflow, mode, conflicts, diffs)
            
            return {
                "success": result.success,
                "workflow_id": result.workflow_id,
                "mode": result.mode,
                "dry_run": result.dry_run,
                "conflicts": [c.__dict__ for c in result.conflicts],
                "diffs": [d.__dict__ for d in result.diffs],
                "warnings": result.warnings,
                "metadata": result.metadata
            }
            
        except Exception as e:
            logger.error(f"Workflow import failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "mode": mode,
                "dry_run": dry_run
            }
    
    async def _prepare_workflow_for_import(self, workflow_json: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Prepare workflow data for import"""
        prepared = workflow_json.copy()
        
        # Clean up fields that shouldn't be imported
        fields_to_remove = ["id", "createdAt", "updatedAt", "versionId"]
        for field in fields_to_remove:
            prepared.pop(field, None)
        
        # Ensure workflow is inactive for draft imports
        if mode == "draft":
            prepared["active"] = False
            
            # Add draft prefix to name
            original_name = prepared["name"]
            if not original_name.startswith(f"{self.draft_prefix} "):
                # Find next available draft number
                draft_number = await self._find_next_draft_number(original_name)
                prepared["name"] = f"{self.draft_prefix} {original_name} v{draft_number}"
        
        # Ensure required fields exist
        prepared.setdefault("active", False)
        prepared.setdefault("settings", {"executionOrder": "v1"})
        prepared.setdefault("staticData", {})
        prepared.setdefault("meta", {})
        
        # Add import metadata
        prepared["meta"]["x_imported"] = True
        prepared["meta"]["x_import_time"] = time.time()
        prepared["meta"]["x_import_mode"] = mode
        prepared["meta"]["x_original_name"] = workflow_json.get("name")
        
        return prepared
    
    async def _find_next_draft_number(self, base_name: str) -> int:
        """Find next available draft version number"""
        try:
            # List existing workflows with similar names
            workflows = await self.n8n_client.list_workflows(query=base_name)
            
            # Find existing draft numbers
            draft_numbers = []
            prefix = f"{self.draft_prefix} {base_name} v"
            
            for workflow in workflows:
                name = workflow.get("name", "")
                if name.startswith(prefix):
                    try:
                        # Extract version number
                        version_part = name[len(prefix):]
                        version_num = int(version_part.split()[0])  # Take first number
                        draft_numbers.append(version_num)
                    except (ValueError, IndexError):
                        continue
            
            # Return next available number
            if draft_numbers:
                return max(draft_numbers) + 1
            else:
                return 1
                
        except Exception as e:
            logger.warning(f"Failed to find draft number: {e}")
            return 1
    
    async def _detect_conflicts(self, prepared_workflow: Dict[str, Any], mode: str) -> List[ImportConflict]:
        """Detect potential conflicts during import"""
        conflicts = []
        workflow_name = prepared_workflow["name"]
        
        try:
            # Check for name conflicts
            existing_workflows = await self.n8n_client.list_workflows(query=workflow_name)
            name_matches = [w for w in existing_workflows if w.get("name") == workflow_name]
            
            if name_matches and mode == "create":
                conflicts.append(ImportConflict(
                    type="name_exists",
                    message=f"Workflow with name '{workflow_name}' already exists",
                    current_value=workflow_name,
                    new_value=workflow_name,
                    resolution="Use 'upsert' mode or choose different name"
                ))
            
            # Check for credential conflicts
            credential_conflicts = await self._check_credential_conflicts(prepared_workflow)
            conflicts.extend(credential_conflicts)
            
            # Check for node type availability
            node_conflicts = await self._check_node_availability(prepared_workflow)
            conflicts.extend(node_conflicts)
            
        except Exception as e:
            logger.warning(f"Conflict detection failed: {e}")
        
        return conflicts
    
    async def _check_credential_conflicts(self, workflow: Dict[str, Any]) -> List[ImportConflict]:
        """Check for missing or conflicting credentials"""
        conflicts = []
        nodes = workflow.get("nodes", [])
        
        # Extract required credentials
        required_credentials = set()
        for node in nodes:
            credentials = node.get("credentials", {})
            for cred_type, cred_info in credentials.items():
                if isinstance(cred_info, dict) and "name" in cred_info:
                    required_credentials.add((cred_type, cred_info["name"]))
        
        # Check if credentials exist (this would require n8n credentials API)
        for cred_type, cred_name in required_credentials:
            # Note: n8n credentials API might not be available in all setups
            conflicts.append(ImportConflict(
                type="credential_missing",
                message=f"Credential '{cred_name}' of type '{cred_type}' may not exist",
                current_value=None,
                new_value=f"{cred_type}:{cred_name}",
                resolution="Verify credential exists or create it before activation"
            ))
        
        return conflicts
    
    async def _check_node_availability(self, workflow: Dict[str, Any]) -> List[ImportConflict]:
        """Check if all node types are available in target n8n instance"""
        conflicts = []
        nodes = workflow.get("nodes", [])
        
        try:
            # Get available node types
            node_types_response = await self.n8n_client.get_node_types()
            available_types = set(node_types_response.get("data", {}).keys())
            
            # Check each node type
            for node in nodes:
                node_type = node.get("type")
                if node_type and node_type not in available_types:
                    conflicts.append(ImportConflict(
                        type="node_unavailable",
                        message=f"Node type '{node_type}' is not available",
                        current_value=None,
                        new_value=node_type,
                        resolution="Install required node package or replace with alternative"
                    ))
                    
        except Exception as e:
            logger.debug(f"Node availability check failed: {e}")
        
        return conflicts
    
    async def _generate_diffs(self, prepared_workflow: Dict[str, Any], mode: str) -> List[ImportDiff]:
        """Generate diffs if updating existing workflow"""
        diffs = []
        
        if mode in ["upsert", "update"]:
            try:
                # Try to find existing workflow
                workflow_name = prepared_workflow["name"]
                existing_workflows = await self.n8n_client.list_workflows(query=workflow_name)
                name_matches = [w for w in existing_workflows if w.get("name") == workflow_name]
                
                if name_matches:
                    existing_workflow = await self.n8n_client.get_workflow(name_matches[0]["id"])
                    diffs = self._compute_workflow_diffs(existing_workflow, prepared_workflow)
                    
            except Exception as e:
                logger.debug(f"Diff generation failed: {e}")
        
        return diffs
    
    def _compute_workflow_diffs(self, old_workflow: Dict[str, Any], new_workflow: Dict[str, Any]) -> List[ImportDiff]:
        """Compute detailed differences between workflows"""
        diffs = []
        
        # Compare top-level fields
        for field in ["name", "active", "settings"]:
            old_value = old_workflow.get(field)
            new_value = new_workflow.get(field)
            
            if old_value != new_value:
                diffs.append(ImportDiff(
                    field=field,
                    operation="modify" if old_value is not None else "add",
                    old_value=old_value,
                    new_value=new_value,
                    location=f"workflow.{field}"
                ))
        
        # Compare nodes
        old_nodes = {node.get("id"): node for node in old_workflow.get("nodes", [])}
        new_nodes = {node.get("id"): node for node in new_workflow.get("nodes", [])}
        
        # Find added nodes
        for node_id, node in new_nodes.items():
            if node_id not in old_nodes:
                diffs.append(ImportDiff(
                    field="nodes",
                    operation="add",
                    old_value=None,
                    new_value=node.get("name", node_id),
                    location=f"nodes.{node_id}"
                ))
        
        # Find removed nodes
        for node_id, node in old_nodes.items():
            if node_id not in new_nodes:
                diffs.append(ImportDiff(
                    field="nodes",
                    operation="remove",
                    old_value=node.get("name", node_id),
                    new_value=None,
                    location=f"nodes.{node_id}"
                ))
        
        # Find modified nodes
        for node_id in set(old_nodes.keys()) & set(new_nodes.keys()):
            old_node = old_nodes[node_id]
            new_node = new_nodes[node_id]
            
            # Compare node parameters
            old_params = old_node.get("parameters", {})
            new_params = new_node.get("parameters", {})
            
            if old_params != new_params:
                diffs.append(ImportDiff(
                    field="node_parameters",
                    operation="modify",
                    old_value=old_params,
                    new_value=new_params,
                    location=f"nodes.{node_id}.parameters"
                ))
        
        # Compare connections
        old_connections = old_workflow.get("connections", {})
        new_connections = new_workflow.get("connections", {})
        
        if old_connections != new_connections:
            diffs.append(ImportDiff(
                field="connections",
                operation="modify",
                old_value=old_connections,
                new_value=new_connections,
                location="workflow.connections"
            ))
        
        return diffs
    
    def _generate_warnings(self, conflicts: List[ImportConflict], diffs: List[ImportDiff]) -> List[str]:
        """Generate user-friendly warnings"""
        warnings = []
        
        # Conflict-based warnings
        error_conflicts = [c for c in conflicts if c.type in ["name_exists", "node_unavailable"]]
        if error_conflicts:
            warnings.append(f"Found {len(error_conflicts)} blocking conflicts that must be resolved")
        
        credential_conflicts = [c for c in conflicts if c.type == "credential_missing"]
        if credential_conflicts:
            warnings.append(f"Found {len(credential_conflicts)} missing credentials - workflow may fail until configured")
        
        # Diff-based warnings
        node_changes = [d for d in diffs if d.field in ["nodes", "node_parameters"]]
        if node_changes:
            warnings.append(f"Workflow structure will be modified ({len(node_changes)} node changes)")
        
        connection_changes = [d for d in diffs if d.field == "connections"]
        if connection_changes:
            warnings.append("Workflow connections will be updated - verify execution flow")
        
        return warnings
    
    async def _execute_import(self, prepared_workflow: Dict[str, Any], mode: str, conflicts: List[ImportConflict], diffs: List[ImportDiff]) -> ImportResult:
        """Execute the actual import operation"""
        
        # Check for blocking conflicts
        blocking_conflicts = [c for c in conflicts if c.type in ["name_exists", "node_unavailable"]]
        if blocking_conflicts and mode == "create":
            return ImportResult(
                success=False,
                workflow_id=None,
                mode=mode,
                conflicts=conflicts,
                diffs=diffs,
                dry_run=False,
                warnings=["Import blocked by conflicts"],
                metadata={"blocking_conflicts": len(blocking_conflicts)}
            )
        
        try:
            workflow_id = None
            
            if mode == "create" or mode == "draft":
                # Create new workflow
                created_workflow = await self.n8n_client.create_workflow(prepared_workflow)
                workflow_id = created_workflow.get("id")
                
            elif mode == "upsert":
                # Try to update existing, create if not found
                try:
                    existing_workflow = await self.n8n_client.get_workflow(workflow_name=prepared_workflow["name"])
                    # Backup if enabled
                    if self.backup_enabled:
                        await self._backup_workflow(existing_workflow)
                    
                    # Update existing
                    updated_workflow = await self.n8n_client.update_workflow(existing_workflow["id"], prepared_workflow)
                    workflow_id = updated_workflow.get("id")
                    
                except Exception:
                    # Create new if update failed
                    created_workflow = await self.n8n_client.create_workflow(prepared_workflow)
                    workflow_id = created_workflow.get("id")
            
            elif mode == "update":
                # Update existing workflow only
                existing_workflow = await self.n8n_client.get_workflow(workflow_name=prepared_workflow["name"])
                
                # Backup if enabled
                if self.backup_enabled:
                    await self._backup_workflow(existing_workflow)
                
                updated_workflow = await self.n8n_client.update_workflow(existing_workflow["id"], prepared_workflow)
                workflow_id = updated_workflow.get("id")
            
            else:
                raise Exception(f"Unknown import mode: {mode}")
            
            # Clean up old drafts if necessary
            if mode == "draft":
                await self._cleanup_old_drafts(prepared_workflow.get("meta", {}).get("x_original_name"))
            
            return ImportResult(
                success=True,
                workflow_id=workflow_id,
                mode=mode,
                conflicts=conflicts,
                diffs=diffs,
                dry_run=False,
                warnings=self._generate_warnings(conflicts, diffs),
                metadata={"imported_at": time.time()}
            )
            
        except Exception as e:
            logger.error(f"Import execution failed: {e}")
            return ImportResult(
                success=False,
                workflow_id=None,
                mode=mode,
                conflicts=conflicts,
                diffs=diffs,
                dry_run=False,
                warnings=[f"Import failed: {e}"],
                metadata={"error": str(e)}
            )
    
    async def _backup_workflow(self, workflow: Dict[str, Any]):
        """Create backup of workflow before update"""
        try:
            backup_name = f"BACKUP_{workflow.get('name', 'Unknown')}_{int(time.time())}"
            backup_workflow = workflow.copy()
            backup_workflow["name"] = backup_name
            backup_workflow["active"] = False
            
            # Remove ID so it creates a new workflow
            backup_workflow.pop("id", None)
            
            await self.n8n_client.create_workflow(backup_workflow)
            logger.info(f"Created backup workflow: {backup_name}")
            
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
    
    async def _cleanup_old_drafts(self, original_name: Optional[str]):
        """Clean up old draft versions"""
        if not original_name:
            return
        
        try:
            # Find all drafts for this workflow
            workflows = await self.n8n_client.list_workflows(query=original_name)
            draft_prefix = f"{self.draft_prefix} {original_name} v"
            
            draft_workflows = []
            for workflow in workflows:
                name = workflow.get("name", "")
                if name.startswith(draft_prefix):
                    try:
                        version_part = name[len(draft_prefix):]
                        version_num = int(version_part.split()[0])
                        draft_workflows.append((version_num, workflow))
                    except (ValueError, IndexError):
                        continue
            
            # Sort by version number and keep only latest versions
            draft_workflows.sort(key=lambda x: x[0], reverse=True)
            
            if len(draft_workflows) > self.max_draft_versions:
                # Delete old drafts
                to_delete = draft_workflows[self.max_draft_versions:]
                for _, workflow in to_delete:
                    try:
                        await self.n8n_client.delete_workflow(workflow["id"])
                        logger.info(f"Deleted old draft: {workflow['name']}")
                    except Exception as e:
                        logger.warning(f"Failed to delete draft {workflow['name']}: {e}")
                        
        except Exception as e:
            logger.warning(f"Draft cleanup failed: {e}")
    
    async def activate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Activate workflow (draft → active)"""
        try:
            # Get workflow details
            workflow = await self.n8n_client.get_workflow(workflow_id)
            
            # Check if it's a draft
            workflow_name = workflow.get("name", "")
            is_draft = workflow_name.startswith(f"{self.draft_prefix} ")
            
            if is_draft:
                # Remove draft prefix and update name
                original_name = workflow.get("meta", {}).get("x_original_name")
                if original_name:
                    # Check if original name workflow exists and handle conflict
                    try:
                        existing = await self.n8n_client.get_workflow(workflow_name=original_name)
                        # Archive existing workflow
                        archive_name = f"ARCHIVED_{original_name}_{int(time.time())}"
                        existing["name"] = archive_name
                        existing["active"] = False
                        await self.n8n_client.update_workflow(existing["id"], existing)
                        logger.info(f"Archived existing workflow as: {archive_name}")
                    except Exception:
                        # No existing workflow with original name
                        pass
                    
                    # Update draft to use original name and activate
                    workflow["name"] = original_name
                    workflow["active"] = True
                    
                    # Update metadata
                    workflow.setdefault("meta", {})
                    workflow["meta"]["x_activated_from_draft"] = True
                    workflow["meta"]["x_activation_time"] = time.time()
                    
                    # Remove draft-specific metadata
                    workflow["meta"].pop("x_draft", None)
                    
                    updated_workflow = await self.n8n_client.update_workflow(workflow_id, workflow)
                    
                    return {
                        "success": True,
                        "workflow_id": workflow_id,
                        "original_name": original_name,
                        "activated": True,
                        "message": f"Draft activated as '{original_name}'"
                    }
            else:
                # Just activate existing workflow
                await self.n8n_client.enable_workflow(workflow_id, True)
                
                return {
                    "success": True,
                    "workflow_id": workflow_id,
                    "activated": True,
                    "message": "Workflow activated"
                }
                
        except Exception as e:
            logger.error(f"Workflow activation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_id": workflow_id
            }
    
    async def import_workflow_file(self, file_data: Dict[str, Any], mode: str = "upsert", dry_run: bool = True) -> Dict[str, Any]:
        """Import workflow from file data"""
        try:
            # Parse file data
            if isinstance(file_data, str):
                workflow_data = json.loads(file_data)
            elif isinstance(file_data, dict):
                workflow_data = file_data
            else:
                raise Exception("Invalid file data format")
            
            # Validate workflow data
            if "name" not in workflow_data or "nodes" not in workflow_data:
                raise Exception("Invalid workflow file: missing required fields")
            
            # Import using standard process
            return await self.import_workflow(workflow_data, mode, dry_run)
            
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON format: {e}",
                "mode": mode,
                "dry_run": dry_run
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "mode": mode,
                "dry_run": dry_run
            }
    
    def generate_import_summary(self, import_result: Dict[str, Any]) -> str:
        """Generate human-readable import summary"""
        if not import_result.get("success"):
            return f"❌ Import failed: {import_result.get('error', 'Unknown error')}"
        
        summary_parts = []
        
        # Basic info
        mode = import_result.get("mode", "unknown")
        workflow_id = import_result.get("workflow_id")
        dry_run = import_result.get("dry_run", False)
        
        if dry_run:
            summary_parts.append(f"🔍 DRY RUN - {mode.upper()} import preview")
        else:
            summary_parts.append(f"✅ {mode.upper()} import successful")
            if workflow_id:
                summary_parts.append(f"Workflow ID: {workflow_id}")
        
        # Conflicts
        conflicts = import_result.get("conflicts", [])
        if conflicts:
            summary_parts.append(f"⚠️ {len(conflicts)} conflicts detected")
        
        # Diffs
        diffs = import_result.get("diffs", [])
        if diffs:
            summary_parts.append(f"📝 {len(diffs)} changes identified")
        
        # Warnings
        warnings = import_result.get("warnings", [])
        if warnings:
            summary_parts.append(f"⚠️ {len(warnings)} warnings")
        
        return "\n".join(summary_parts)
