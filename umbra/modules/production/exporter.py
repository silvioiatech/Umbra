"""
Workflow Exporter for Production Module

Exports n8n workflows to various formats with metadata cleaning,
credential masking, and portability optimization.
"""

import json
import logging
import time
import zipfile
import io
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import base64

from ...core.config import UmbraConfig
from .n8n_client import N8nClient

logger = logging.getLogger(__name__)

@dataclass
class ExportOptions:
    """Export configuration options"""
    format: str = "json"  # json, zip, yaml
    include_credentials: bool = False
    include_executions: bool = False
    include_metadata: bool = True
    clean_for_portability: bool = True
    mask_sensitive_data: bool = True
    compress: bool = False

@dataclass
class ExportResult:
    """Export operation result"""
    success: bool
    format: str
    data: Optional[bytes]
    filename: str
    size_bytes: int
    metadata: Dict[str, Any]
    warnings: List[str]

class WorkflowExporter:
    """Exports workflows from n8n with advanced options"""
    
    def __init__(self, n8n_client: N8nClient, config: UmbraConfig):
        self.n8n_client = n8n_client
        self.config = config
        
        # Export settings
        self.default_format = config.get("PROD_EXPORT_FORMAT", "json")
        self.include_metadata = config.get("PROD_EXPORT_METADATA", True)
        self.mask_credentials = config.get("PROD_MASK_CREDENTIALS", True)
        
        # Sensitive field patterns
        self.sensitive_patterns = [
            "password", "token", "key", "secret", "credential",
            "auth", "oauth", "api_key", "private"
        ]
        
        logger.info("Workflow exporter initialized")
    
    async def export_workflow(self, workflow_id: str, options: Optional[ExportOptions] = None) -> Dict[str, Any]:
        """Export single workflow with specified options"""
        if options is None:
            options = ExportOptions()
        
        try:
            # Get workflow data
            workflow = await self.n8n_client.get_workflow(workflow_id)
            
            # Process workflow for export
            processed_workflow = await self._process_workflow_for_export(workflow, options)
            
            # Generate export data
            export_data, filename = await self._generate_export_data(processed_workflow, options)
            
            # Create result
            result = ExportResult(
                success=True,
                format=options.format,
                data=export_data,
                filename=filename,
                size_bytes=len(export_data) if export_data else 0,
                metadata=self._generate_export_metadata(workflow, options),
                warnings=self._generate_export_warnings(workflow, options)
            )
            
            return {
                "success": result.success,
                "format": result.format,
                "filename": result.filename,
                "size_bytes": result.size_bytes,
                "data": base64.b64encode(result.data).decode() if result.data else None,
                "metadata": result.metadata,
                "warnings": result.warnings
            }
            
        except Exception as e:
            logger.error(f"Workflow export failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_id": workflow_id
            }
    
    async def export_multiple_workflows(self, workflow_ids: List[str], options: Optional[ExportOptions] = None) -> Dict[str, Any]:
        """Export multiple workflows as archive"""
        if options is None:
            options = ExportOptions(format="zip", compress=True)
        
        try:
            exported_workflows = {}
            warnings = []
            
            # Export each workflow
            for workflow_id in workflow_ids:
                try:
                    workflow = await self.n8n_client.get_workflow(workflow_id)
                    processed_workflow = await self._process_workflow_for_export(workflow, options)
                    
                    # Use workflow name as key
                    workflow_name = self._sanitize_filename(workflow.get("name", workflow_id))
                    exported_workflows[workflow_name] = processed_workflow
                    
                except Exception as e:
                    warnings.append(f"Failed to export workflow {workflow_id}: {e}")
            
            if not exported_workflows:
                raise Exception("No workflows could be exported")
            
            # Create archive
            archive_data, filename = await self._create_workflow_archive(exported_workflows, options)
            
            return {
                "success": True,
                "format": "zip",
                "filename": filename,
                "size_bytes": len(archive_data),
                "data": base64.b64encode(archive_data).decode(),
                "exported_count": len(exported_workflows),
                "failed_count": len(warnings),
                "warnings": warnings,
                "metadata": {
                    "export_time": time.time(),
                    "workflow_count": len(exported_workflows),
                    "compression": options.compress
                }
            }
            
        except Exception as e:
            logger.error(f"Multiple workflow export failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_ids": workflow_ids
            }
    
    async def _process_workflow_for_export(self, workflow: Dict[str, Any], options: ExportOptions) -> Dict[str, Any]:
        """Process workflow data for export based on options"""
        processed = workflow.copy()
        
        # Clean for portability
        if options.clean_for_portability:
            processed = self._clean_for_portability(processed)
        
        # Mask sensitive data
        if options.mask_sensitive_data:
            processed = self._mask_sensitive_data(processed)
        
        # Handle credentials
        if not options.include_credentials:
            processed = self._remove_credential_details(processed)
        
        # Add export metadata
        if options.include_metadata:
            processed = self._add_export_metadata(processed, options)
        
        return processed
    
    def _clean_for_portability(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Clean workflow for cross-instance portability"""
        cleaned = workflow.copy()
        
        # Remove instance-specific fields
        fields_to_remove = [
            "id", "createdAt", "updatedAt", "versionId",
            "ownedBy", "sharedWith", "homeProject"
        ]
        
        for field in fields_to_remove:
            cleaned.pop(field, None)
        
        # Clean node credentials (keep structure but remove IDs)
        nodes = cleaned.get("nodes", [])
        for node in nodes:
            credentials = node.get("credentials", {})
            for cred_type, cred_info in credentials.items():
                if isinstance(cred_info, dict) and "id" in cred_info:
                    # Keep name but remove instance-specific ID
                    cred_info.pop("id", None)
        
        # Clean settings that might be instance-specific
        settings = cleaned.get("settings", {})
        instance_specific_settings = [
            "timezone", "saveDataErrorExecution", "saveDataSuccessExecution"
        ]
        for setting in instance_specific_settings:
            settings.pop(setting, None)
        
        return cleaned
    
    def _mask_sensitive_data(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data in workflow"""
        masked = workflow.copy()
        
        # Mask in node parameters
        nodes = masked.get("nodes", [])
        for node in nodes:
            parameters = node.get("parameters", {})
            node["parameters"] = self._mask_sensitive_in_dict(parameters)
        
        # Mask in static data
        static_data = masked.get("staticData", {})
        masked["staticData"] = self._mask_sensitive_in_dict(static_data)
        
        return masked
    
    def _mask_sensitive_in_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively mask sensitive data in dictionary"""
        if not isinstance(data, dict):
            return data
        
        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key contains sensitive patterns
            is_sensitive = any(pattern in key_lower for pattern in self.sensitive_patterns)
            
            if is_sensitive and isinstance(value, str) and value:
                # Mask the value
                if len(value) <= 4:
                    masked[key] = "***"
                else:
                    masked[key] = value[:2] + "*" * (len(value) - 4) + value[-2:]
            elif isinstance(value, dict):
                # Recursively process nested dictionaries
                masked[key] = self._mask_sensitive_in_dict(value)
            elif isinstance(value, list):
                # Process lists
                masked[key] = [
                    self._mask_sensitive_in_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = value
        
        return masked
    
    def _remove_credential_details(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Remove credential details from workflow"""
        cleaned = workflow.copy()
        
        nodes = cleaned.get("nodes", [])
        for node in nodes:
            if "credentials" in node:
                # Keep structure but remove sensitive details
                credentials = node["credentials"]
                for cred_type, cred_info in credentials.items():
                    if isinstance(cred_info, dict):
                        # Keep only name for reference
                        name = cred_info.get("name", "")
                        node["credentials"][cred_type] = {
                            "name": name,
                            "note": "Credential details removed for security"
                        }
        
        return cleaned
    
    def _add_export_metadata(self, workflow: Dict[str, Any], options: ExportOptions) -> Dict[str, Any]:
        """Add export metadata to workflow"""
        enhanced = workflow.copy()
        
        # Add export metadata
        enhanced.setdefault("meta", {})
        enhanced["meta"]["x_exported"] = True
        enhanced["meta"]["x_export_time"] = time.time()
        enhanced["meta"]["x_export_format"] = options.format
        enhanced["meta"]["x_exported_by"] = "umbra-production"
        enhanced["meta"]["x_export_options"] = {
            "include_credentials": options.include_credentials,
            "mask_sensitive": options.mask_sensitive_data,
            "clean_for_portability": options.clean_for_portability
        }
        
        # Add original workflow info if available
        if "name" in workflow:
            enhanced["meta"]["x_original_name"] = workflow["name"]
        
        return enhanced
    
    async def _generate_export_data(self, workflow: Dict[str, Any], options: ExportOptions) -> Tuple[bytes, str]:
        """Generate export data in specified format"""
        workflow_name = self._sanitize_filename(workflow.get("name", "workflow"))
        timestamp = int(time.time())
        
        if options.format == "json":
            # JSON export
            json_data = json.dumps(workflow, indent=2, ensure_ascii=False)
            data = json_data.encode("utf-8")
            filename = f"{workflow_name}_{timestamp}.json"
            
            if options.compress:
                # Compress JSON
                data = self._compress_data(data)
                filename = f"{workflow_name}_{timestamp}.json.gz"
            
            return data, filename
        
        elif options.format == "yaml":
            # YAML export (if PyYAML available)
            try:
                import yaml
                yaml_data = yaml.dump(workflow, default_flow_style=False, allow_unicode=True)
                data = yaml_data.encode("utf-8")
                filename = f"{workflow_name}_{timestamp}.yaml"
                
                if options.compress:
                    data = self._compress_data(data)
                    filename = f"{workflow_name}_{timestamp}.yaml.gz"
                
                return data, filename
            except ImportError:
                # Fallback to JSON if YAML not available
                logger.warning("PyYAML not available, falling back to JSON export")
                return await self._generate_export_data(workflow, ExportOptions(format="json", compress=options.compress))
        
        elif options.format == "zip":
            # ZIP export with metadata
            zip_data = await self._create_single_workflow_zip(workflow, options)
            filename = f"{workflow_name}_{timestamp}.zip"
            return zip_data, filename
        
        else:
            raise Exception(f"Unsupported export format: {options.format}")
    
    async def _create_single_workflow_zip(self, workflow: Dict[str, Any], options: ExportOptions) -> bytes:
        """Create ZIP archive for single workflow"""
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED if options.compress else zipfile.ZIP_STORED) as zf:
            # Add workflow JSON
            workflow_json = json.dumps(workflow, indent=2, ensure_ascii=False)
            zf.writestr("workflow.json", workflow_json)
            
            # Add README
            readme_content = self._generate_export_readme(workflow, options)
            zf.writestr("README.md", readme_content)
            
            # Add metadata file
            metadata = self._generate_export_metadata(workflow, options)
            metadata_json = json.dumps(metadata, indent=2)
            zf.writestr("metadata.json", metadata_json)
        
        return zip_buffer.getvalue()
    
    async def _create_workflow_archive(self, workflows: Dict[str, Dict[str, Any]], options: ExportOptions) -> Tuple[bytes, str]:
        """Create archive containing multiple workflows"""
        zip_buffer = io.BytesIO()
        timestamp = int(time.time())
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED if options.compress else zipfile.ZIP_STORED) as zf:
            # Add each workflow
            for name, workflow in workflows.items():
                workflow_json = json.dumps(workflow, indent=2, ensure_ascii=False)
                zf.writestr(f"workflows/{name}.json", workflow_json)
            
            # Add collection README
            readme_content = self._generate_collection_readme(workflows, options)
            zf.writestr("README.md", readme_content)
            
            # Add collection metadata
            collection_metadata = {
                "export_time": time.time(),
                "workflow_count": len(workflows),
                "exported_by": "umbra-production",
                "export_options": {
                    "include_credentials": options.include_credentials,
                    "mask_sensitive": options.mask_sensitive_data,
                    "clean_for_portability": options.clean_for_portability
                },
                "workflows": {
                    name: {
                        "original_name": workflow.get("name", name),
                        "node_count": len(workflow.get("nodes", [])),
                        "has_credentials": any(
                            "credentials" in node for node in workflow.get("nodes", [])
                        )
                    }
                    for name, workflow in workflows.items()
                }
            }
            
            metadata_json = json.dumps(collection_metadata, indent=2)
            zf.writestr("metadata.json", metadata_json)
        
        filename = f"workflows_export_{timestamp}.zip"
        return zip_buffer.getvalue(), filename
    
    def _compress_data(self, data: bytes) -> bytes:
        """Compress data using gzip"""
        import gzip
        return gzip.compress(data)
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for safe file system use"""
        import re
        # Remove or replace unsafe characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        sanitized = re.sub(r'[\s]+', '_', sanitized)
        sanitized = sanitized.strip('._')
        
        # Ensure reasonable length
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        
        return sanitized or "workflow"
    
    def _generate_export_metadata(self, workflow: Dict[str, Any], options: ExportOptions) -> Dict[str, Any]:
        """Generate metadata for export"""
        nodes = workflow.get("nodes", [])
        
        # Count node types
        node_types = {}
        for node in nodes:
            node_type = node.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        # Find credentials used
        credentials_used = set()
        for node in nodes:
            credentials = node.get("credentials", {})
            for cred_type in credentials.keys():
                credentials_used.add(cred_type)
        
        return {
            "workflow_name": workflow.get("name", "Unknown"),
            "export_time": time.time(),
            "export_format": options.format,
            "node_count": len(nodes),
            "node_types": node_types,
            "credentials_used": list(credentials_used),
            "has_active_state": workflow.get("active", False),
            "export_options": {
                "include_credentials": options.include_credentials,
                "mask_sensitive": options.mask_sensitive_data,
                "clean_for_portability": options.clean_for_portability,
                "include_metadata": options.include_metadata
            }
        }
    
    def _generate_export_warnings(self, workflow: Dict[str, Any], options: ExportOptions) -> List[str]:
        """Generate warnings for export"""
        warnings = []
        
        # Check for credentials
        nodes = workflow.get("nodes", [])
        has_credentials = any("credentials" in node for node in nodes)
        
        if has_credentials and not options.include_credentials:
            warnings.append("Workflow uses credentials which were excluded from export")
        
        if options.mask_sensitive_data:
            warnings.append("Sensitive data has been masked in the export")
        
        if options.clean_for_portability:
            warnings.append("Instance-specific data has been removed for portability")
        
        # Check for complex nodes that might not be portable
        complex_nodes = [node for node in nodes if "code" in node.get("type", "").lower()]
        if complex_nodes:
            warnings.append(f"Contains {len(complex_nodes)} code nodes that may need review")
        
        return warnings
    
    def _generate_export_readme(self, workflow: Dict[str, Any], options: ExportOptions) -> str:
        """Generate README for single workflow export"""
        workflow_name = workflow.get("name", "Unknown Workflow")
        nodes = workflow.get("nodes", [])
        
        readme = f"""# {workflow_name}

## Workflow Export

**Exported:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  
**Format:** {options.format.upper()}  
**Exported by:** Umbra Production Module

## Workflow Details

- **Node Count:** {len(nodes)}
- **Active State:** {'Yes' if workflow.get('active') else 'No'}

### Node Types Used

"""
        
        # Add node type breakdown
        node_types = {}
        for node in nodes:
            node_type = node.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        for node_type, count in sorted(node_types.items()):
            readme += f"- {node_type}: {count}\n"
        
        readme += """
## Import Instructions

1. Import the `workflow.json` file into your n8n instance
2. Configure any required credentials before activating
3. Review node parameters for environment-specific settings
4. Test the workflow before using in production

## Notes

"""
        
        if not options.include_credentials:
            readme += "- Credential details were excluded for security\n"
        if options.mask_sensitive_data:
            readme += "- Sensitive data has been masked\n"
        if options.clean_for_portability:
            readme += "- Instance-specific data was removed for portability\n"
        
        return readme
    
    def _generate_collection_readme(self, workflows: Dict[str, Dict[str, Any]], options: ExportOptions) -> str:
        """Generate README for workflow collection"""
        readme = f"""# Workflow Collection Export

**Exported:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  
**Workflow Count:** {len(workflows)}  
**Exported by:** Umbra Production Module

## Workflows Included

"""
        
        for name, workflow in workflows.items():
            nodes = workflow.get("nodes", [])
            readme += f"### {workflow.get('name', name)}\n"
            readme += f"- **File:** `workflows/{name}.json`\n"
            readme += f"- **Nodes:** {len(nodes)}\n"
            readme += f"- **Active:** {'Yes' if workflow.get('active') else 'No'}\n\n"
        
        readme += """## Import Instructions

1. Extract all files from this archive
2. Import each workflow JSON file individually into your n8n instance
3. Configure credentials and environment-specific settings
4. Test workflows before production use

## Notes

"""
        
        if not options.include_credentials:
            readme += "- Credential details were excluded from all workflows\n"
        if options.mask_sensitive_data:
            readme += "- Sensitive data has been masked in all workflows\n"
        if options.clean_for_portability:
            readme += "- Instance-specific data was removed for portability\n"
        
        return readme
    
    async def export_workflow_as_template(self, workflow_id: str) -> Dict[str, Any]:
        """Export workflow as reusable template"""
        try:
            # Get workflow
            workflow = await self.n8n_client.get_workflow(workflow_id)
            
            # Create template-specific options
            template_options = ExportOptions(
                format="json",
                include_credentials=False,
                mask_sensitive_data=True,
                clean_for_portability=True,
                include_metadata=True
            )
            
            # Process for template
            template_workflow = await self._process_workflow_for_export(workflow, template_options)
            
            # Add template-specific metadata
            template_workflow["meta"]["x_template"] = True
            template_workflow["meta"]["x_template_version"] = "1.0"
            template_workflow["meta"]["x_source_workflow"] = workflow.get("name")
            
            # Generate template JSON
            template_json = json.dumps(template_workflow, indent=2, ensure_ascii=False)
            template_data = template_json.encode("utf-8")
            
            # Generate filename
            workflow_name = self._sanitize_filename(workflow.get("name", "workflow"))
            filename = f"{workflow_name}_template.json"
            
            return {
                "success": True,
                "format": "json",
                "filename": filename,
                "size_bytes": len(template_data),
                "data": base64.b64encode(template_data).decode(),
                "template": True,
                "source_workflow": workflow.get("name"),
                "metadata": self._generate_export_metadata(workflow, template_options)
            }
            
        except Exception as e:
            logger.error(f"Template export failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_id": workflow_id
            }
