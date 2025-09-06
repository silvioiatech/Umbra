"""
Workflow Validator for Production Module

Validates n8n workflow structure, schema compliance, and logical correctness
before import and execution.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
import re

from ...core.config import UmbraConfig
from .n8n_client import N8nClient

logger = logging.getLogger(__name__)

@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    level: str  # "error", "warning", "info"
    category: str  # "schema", "logic", "security", "performance"
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None

@dataclass
class ValidationResult:
    """Complete validation result"""
    valid: bool
    issues: List[ValidationIssue]
    score: float  # 0.0 to 1.0
    summary: Dict[str, Any]

class WorkflowValidator:
    """Validates n8n workflows for correctness and quality"""
    
    def __init__(self, n8n_client: N8nClient, config: UmbraConfig):
        self.n8n_client = n8n_client
        self.config = config
        
        # Validation rules
        self.strict_mode = config.get("PROD_VALIDATION_STRICT", True)
        self.security_checks = config.get("PROD_SECURITY_CHECKS", True)
        
        # Known node types cache
        self._node_types_cache = None
        
        logger.info("Workflow validator initialized")
    
    async def validate_workflow(self, workflow_json: Dict[str, Any]) -> Dict[str, Any]:
        """Validate complete workflow and return detailed results"""
        try:
            issues = []
            
            # 1. Schema validation
            schema_issues = await self._validate_schema(workflow_json)
            issues.extend(schema_issues)
            
            # 2. Structure validation
            structure_issues = await self._validate_structure(workflow_json)
            issues.extend(structure_issues)
            
            # 3. Logic validation
            logic_issues = await self._validate_logic(workflow_json)
            issues.extend(logic_issues)
            
            # 4. Security validation
            if self.security_checks:
                security_issues = await self._validate_security(workflow_json)
                issues.extend(security_issues)
            
            # 5. Performance validation
            performance_issues = await self._validate_performance(workflow_json)
            issues.extend(performance_issues)
            
            # 6. n8n-specific validation
            n8n_issues = await self._validate_n8n_specific(workflow_json)
            issues.extend(n8n_issues)
            
            # Calculate overall result
            result = self._compile_validation_result(issues, workflow_json)
            
            return {
                "ok": result.valid,
                "score": result.score,
                "issues": [issue.__dict__ for issue in result.issues],
                "summary": result.summary,
                "recommendations": self._generate_recommendations(result)
            }
            
        except Exception as e:
            logger.error(f"Workflow validation failed: {e}")
            return {
                "ok": False,
                "error": f"Validation failed: {e}",
                "issues": [],
                "summary": {}
            }
    
    async def _validate_schema(self, workflow: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate workflow against n8n schema"""
        issues = []
        
        # Required top-level fields
        required_fields = {
            "name": str,
            "nodes": list,
            "connections": dict
        }
        
        for field, expected_type in required_fields.items():
            if field not in workflow:
                issues.append(ValidationIssue(
                    level="error",
                    category="schema",
                    message=f"Missing required field: {field}",
                    suggestion=f"Add '{field}' field to workflow"
                ))
            elif not isinstance(workflow[field], expected_type):
                issues.append(ValidationIssue(
                    level="error",
                    category="schema",
                    message=f"Field '{field}' must be {expected_type.__name__}",
                    suggestion=f"Change '{field}' to {expected_type.__name__} type"
                ))
        
        # Optional fields with types
        optional_fields = {
            "active": bool,
            "settings": dict,
            "staticData": dict,
            "meta": dict,
            "tags": list
        }
        
        for field, expected_type in optional_fields.items():
            if field in workflow and not isinstance(workflow[field], expected_type):
                issues.append(ValidationIssue(
                    level="warning",
                    category="schema",
                    message=f"Field '{field}' should be {expected_type.__name__}",
                    suggestion=f"Change '{field}' to {expected_type.__name__} type"
                ))
        
        # Validate nodes array
        nodes = workflow.get("nodes", [])
        for i, node in enumerate(nodes):
            node_issues = self._validate_node_schema(node, i)
            issues.extend(node_issues)
        
        # Validate connections
        connections = workflow.get("connections", {})
        connection_issues = self._validate_connections_schema(connections, nodes)
        issues.extend(connection_issues)
        
        return issues
    
    def _validate_node_schema(self, node: Dict[str, Any], index: int) -> List[ValidationIssue]:
        """Validate individual node schema"""
        issues = []
        location = f"nodes[{index}]"
        
        # Required node fields
        required_fields = {
            "id": str,
            "name": str,
            "type": str,
            "typeVersion": int,
            "position": list
        }
        
        for field, expected_type in required_fields.items():
            if field not in node:
                issues.append(ValidationIssue(
                    level="error",
                    category="schema",
                    message=f"Node missing required field: {field}",
                    location=location,
                    suggestion=f"Add '{field}' field to node"
                ))
            elif not isinstance(node[field], expected_type):
                issues.append(ValidationIssue(
                    level="error", 
                    category="schema",
                    message=f"Node field '{field}' must be {expected_type.__name__}",
                    location=location
                ))
        
        # Validate position array
        position = node.get("position", [])
        if isinstance(position, list):
            if len(position) != 2:
                issues.append(ValidationIssue(
                    level="error",
                    category="schema",
                    message="Node position must have exactly 2 coordinates [x, y]",
                    location=location
                ))
            elif not all(isinstance(coord, (int, float)) for coord in position):
                issues.append(ValidationIssue(
                    level="error",
                    category="schema", 
                    message="Node position coordinates must be numbers",
                    location=location
                ))
        
        # Validate optional fields
        if "parameters" in node and not isinstance(node["parameters"], dict):
            issues.append(ValidationIssue(
                level="error",
                category="schema",
                message="Node parameters must be an object",
                location=location
            ))
        
        if "credentials" in node and not isinstance(node["credentials"], dict):
            issues.append(ValidationIssue(
                level="error", 
                category="schema",
                message="Node credentials must be an object",
                location=location
            ))
        
        return issues
    
    def _validate_connections_schema(self, connections: Dict[str, Any], nodes: List[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate connections schema"""
        issues = []
        node_ids = {node.get("id") for node in nodes if "id" in node}
        
        for source_id, connection_data in connections.items():
            location = f"connections['{source_id}']"
            
            # Check source node exists
            if source_id not in node_ids:
                issues.append(ValidationIssue(
                    level="error",
                    category="schema",
                    message=f"Connection source node '{source_id}' does not exist",
                    location=location
                ))
                continue
            
            # Validate connection data structure
            if not isinstance(connection_data, dict):
                issues.append(ValidationIssue(
                    level="error",
                    category="schema",
                    message="Connection data must be an object",
                    location=location
                ))
                continue
            
            # Validate each output type
            for output_type, outputs in connection_data.items():
                output_location = f"{location}.{output_type}"
                
                if not isinstance(outputs, list):
                    issues.append(ValidationIssue(
                        level="error",
                        category="schema",
                        message=f"Output '{output_type}' must be an array",
                        location=output_location
                    ))
                    continue
                
                # Validate each output connection
                for i, output_list in enumerate(outputs):
                    if not isinstance(output_list, list):
                        issues.append(ValidationIssue(
                            level="error",
                            category="schema",
                            message=f"Output connection {i} must be an array",
                            location=f"{output_location}[{i}]"
                        ))
                        continue
                    
                    # Validate individual connections
                    for j, connection in enumerate(output_list):
                        conn_location = f"{output_location}[{i}][{j}]"
                        
                        if not isinstance(connection, dict):
                            issues.append(ValidationIssue(
                                level="error",
                                category="schema",
                                message="Connection must be an object",
                                location=conn_location
                            ))
                            continue
                        
                        # Check required connection fields
                        if "node" not in connection:
                            issues.append(ValidationIssue(
                                level="error",
                                category="schema",
                                message="Connection missing 'node' field",
                                location=conn_location
                            ))
                        elif connection["node"] not in node_ids:
                            issues.append(ValidationIssue(
                                level="error",
                                category="schema",
                                message=f"Connection target node '{connection['node']}' does not exist",
                                location=conn_location
                            ))
        
        return issues
    
    async def _validate_structure(self, workflow: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate workflow structural integrity"""
        issues = []
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        if not nodes:
            issues.append(ValidationIssue(
                level="error",
                category="structure",
                message="Workflow must have at least one node",
                suggestion="Add a trigger or manual trigger node"
            ))
            return issues
        
        # Check for duplicate node IDs
        node_ids = [node.get("id") for node in nodes if "id" in node]
        duplicate_ids = set([nid for nid in node_ids if node_ids.count(nid) > 1])
        
        for dup_id in duplicate_ids:
            issues.append(ValidationIssue(
                level="error",
                category="structure",
                message=f"Duplicate node ID: {dup_id}",
                suggestion="Ensure all node IDs are unique"
            ))
        
        # Check for orphaned nodes (except triggers)
        connected_nodes = set()
        for connection_data in connections.values():
            for outputs in connection_data.values():
                for output_list in outputs:
                    for connection in output_list:
                        if isinstance(connection, dict) and "node" in connection:
                            connected_nodes.add(connection["node"])
        
        # Find trigger nodes
        trigger_nodes = set()
        for node in nodes:
            node_type = node.get("type", "")
            if ("trigger" in node_type.lower() or 
                "webhook" in node_type.lower() or
                "manual" in node_type.lower()):
                trigger_nodes.add(node.get("id"))
        
        # Check for orphaned non-trigger nodes
        all_node_ids = set(node_ids)
        source_nodes = set(connections.keys())
        orphaned_nodes = all_node_ids - connected_nodes - source_nodes - trigger_nodes
        
        for orphan_id in orphaned_nodes:
            issues.append(ValidationIssue(
                level="warning",
                category="structure",
                message=f"Orphaned node: {orphan_id}",
                suggestion="Connect node to workflow or remove if unused"
            ))
        
        return issues
    
    async def _validate_logic(self, workflow: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate workflow logical flow"""
        issues = []
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        # Check for triggers
        trigger_nodes = []
        for node in nodes:
            node_type = node.get("type", "")
            if ("trigger" in node_type.lower() or
                "webhook" in node_type.lower() or 
                "manual" in node_type.lower()):
                trigger_nodes.append(node)
        
        if not trigger_nodes:
            issues.append(ValidationIssue(
                level="error",
                category="logic",
                message="Workflow must have at least one trigger node",
                suggestion="Add a webhook, cron, or manual trigger"
            ))
        
        # Check for circular dependencies
        circular_deps = self._detect_circular_dependencies(connections)
        for cycle in circular_deps:
            issues.append(ValidationIssue(
                level="error",
                category="logic",
                message=f"Circular dependency detected: {' -> '.join(cycle)}",
                suggestion="Remove circular connections to prevent infinite loops"
            ))
        
        # Check for unreachable nodes
        if trigger_nodes and connections:
            reachable_nodes = set()
            for trigger in trigger_nodes:
                trigger_id = trigger.get("id")
                reachable = self._find_reachable_nodes(trigger_id, connections)
                reachable_nodes.update(reachable)
            
            all_node_ids = {node.get("id") for node in nodes}
            unreachable = all_node_ids - reachable_nodes
            
            for unreachable_id in unreachable:
                issues.append(ValidationIssue(
                    level="warning",
                    category="logic",
                    message=f"Node '{unreachable_id}' is unreachable from triggers",
                    suggestion="Connect node to execution flow or remove if unused"
                ))
        
        return issues
    
    def _detect_circular_dependencies(self, connections: Dict[str, Any]) -> List[List[str]]:
        """Detect circular dependencies in workflow"""
        cycles = []
        visited = set()
        path = []
        
        def dfs(node_id: str):
            if node_id in path:
                # Found cycle
                cycle_start = path.index(node_id)
                cycle = path[cycle_start:] + [node_id]
                cycles.append(cycle)
                return
            
            if node_id in visited:
                return
            
            visited.add(node_id)
            path.append(node_id)
            
            # Follow connections
            node_connections = connections.get(node_id, {})
            for outputs in node_connections.values():
                for output_list in outputs:
                    for connection in output_list:
                        if isinstance(connection, dict) and "node" in connection:
                            dfs(connection["node"])
            
            path.pop()
        
        # Start DFS from all nodes
        for node_id in connections.keys():
            if node_id not in visited:
                dfs(node_id)
        
        return cycles
    
    def _find_reachable_nodes(self, start_node: str, connections: Dict[str, Any]) -> Set[str]:
        """Find all nodes reachable from start node"""
        reachable = {start_node}
        queue = [start_node]
        
        while queue:
            current = queue.pop(0)
            node_connections = connections.get(current, {})
            
            for outputs in node_connections.values():
                for output_list in outputs:
                    for connection in output_list:
                        if isinstance(connection, dict) and "node" in connection:
                            target = connection["node"]
                            if target not in reachable:
                                reachable.add(target)
                                queue.append(target)
        
        return reachable
    
    async def _validate_security(self, workflow: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate workflow security aspects"""
        issues = []
        nodes = workflow.get("nodes", [])
        
        for node in nodes:
            node_type = node.get("type", "")
            node_id = node.get("id", "unknown")
            parameters = node.get("parameters", {})
            
            # Check for dangerous node types
            dangerous_nodes = ["code", "function", "shell", "script"]
            if any(danger in node_type.lower() for danger in dangerous_nodes):
                issues.append(ValidationIssue(
                    level="warning",
                    category="security",
                    message=f"Node '{node_id}' uses potentially dangerous type: {node_type}",
                    location=f"nodes['{node_id}']",
                    suggestion="Review code for security vulnerabilities"
                ))
            
            # Check for hardcoded secrets
            secret_patterns = [
                r'password[\s]*[:=][\s]*["\']([^"\']+)["\']',
                r'token[\s]*[:=][\s]*["\']([^"\']+)["\']',
                r'key[\s]*[:=][\s]*["\']([^"\']+)["\']',
                r'secret[\s]*[:=][\s]*["\']([^"\']+)["\']'
            ]
            
            param_str = json.dumps(parameters)
            for pattern in secret_patterns:
                matches = re.findall(pattern, param_str, re.IGNORECASE)
                if matches:
                    issues.append(ValidationIssue(
                        level="error",
                        category="security", 
                        message=f"Node '{node_id}' contains hardcoded secrets",
                        location=f"nodes['{node_id}'].parameters",
                        suggestion="Use credentials or environment variables instead"
                    ))
            
            # Check for missing credentials
            if node_type in ["n8n-nodes-base.gmail", "n8n-nodes-base.slack", "n8n-nodes-base.github"]:
                if "credentials" not in node:
                    issues.append(ValidationIssue(
                        level="warning",
                        category="security",
                        message=f"Node '{node_id}' missing credentials configuration",
                        location=f"nodes['{node_id}']",
                        suggestion="Configure proper authentication credentials"
                    ))
        
        return issues
    
    async def _validate_performance(self, workflow: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate workflow performance characteristics"""
        issues = []
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        # Check for performance anti-patterns
        
        # 1. Too many nodes
        if len(nodes) > 50:
            issues.append(ValidationIssue(
                level="warning",
                category="performance",
                message=f"Workflow has {len(nodes)} nodes, consider breaking into smaller workflows",
                suggestion="Split complex workflows for better maintainability"
            ))
        
        # 2. Deep nesting
        max_depth = self._calculate_workflow_depth(connections)
        if max_depth > 20:
            issues.append(ValidationIssue(
                level="warning",
                category="performance",
                message=f"Workflow depth is {max_depth}, very deep execution chains",
                suggestion="Consider parallel processing or workflow splitting"
            ))
        
        # 3. Check for potential bottlenecks
        for node in nodes:
            node_type = node.get("type", "")
            node_id = node.get("id", "unknown")
            parameters = node.get("parameters", {})
            
            # HTTP requests without timeout
            if "http" in node_type.lower():
                timeout = parameters.get("timeout", parameters.get("options", {}).get("timeout"))
                if not timeout:
                    issues.append(ValidationIssue(
                        level="info",
                        category="performance",
                        message=f"HTTP node '{node_id}' lacks timeout configuration",
                        location=f"nodes['{node_id}']",
                        suggestion="Set appropriate timeout to prevent hanging"
                    ))
        
        return issues
    
    def _calculate_workflow_depth(self, connections: Dict[str, Any]) -> int:
        """Calculate maximum execution depth of workflow"""
        max_depth = 0
        
        def dfs(node_id: str, current_depth: int, visited: Set[str]):
            nonlocal max_depth
            max_depth = max(max_depth, current_depth)
            
            if node_id in visited:
                return  # Avoid cycles
            
            visited.add(node_id)
            
            node_connections = connections.get(node_id, {})
            for outputs in node_connections.values():
                for output_list in outputs:
                    for connection in output_list:
                        if isinstance(connection, dict) and "node" in connection:
                            dfs(connection["node"], current_depth + 1, visited.copy())
        
        # Start from all root nodes (nodes not targeted by any connection)
        all_targets = set()
        for connection_data in connections.values():
            for outputs in connection_data.values():
                for output_list in outputs:
                    for connection in output_list:
                        if isinstance(connection, dict) and "node" in connection:
                            all_targets.add(connection["node"])
        
        root_nodes = set(connections.keys()) - all_targets
        
        for root in root_nodes:
            dfs(root, 1, set())
        
        return max_depth
    
    async def _validate_n8n_specific(self, workflow: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate n8n-specific requirements"""
        issues = []
        
        try:
            # Try to validate against actual n8n instance if available
            validation_result = await self.n8n_client.validate_workflow(workflow)
            
            if not validation_result.get("ok", True):
                n8n_errors = validation_result.get("errors", [])
                for error in n8n_errors:
                    issues.append(ValidationIssue(
                        level="error",
                        category="n8n",
                        message=f"n8n validation: {error}",
                        suggestion="Fix according to n8n requirements"
                    ))
        
        except Exception as e:
            logger.debug(f"n8n validation not available: {e}")
            # Fallback to basic checks
            
            # Check node types against known types
            if not self._node_types_cache:
                try:
                    node_types_response = await self.n8n_client.get_node_types()
                    self._node_types_cache = set(node_types_response.get("data", {}).keys())
                except Exception:
                    self._node_types_cache = set()  # Empty set if can't fetch
            
            if self._node_types_cache:
                nodes = workflow.get("nodes", [])
                for node in nodes:
                    node_type = node.get("type", "")
                    if node_type and node_type not in self._node_types_cache:
                        issues.append(ValidationIssue(
                            level="warning",
                            category="n8n",
                            message=f"Unknown node type: {node_type}",
                            location=f"nodes['{node.get('id', 'unknown')}']",
                            suggestion="Verify node type is available in target n8n instance"
                        ))
        
        return issues
    
    def _compile_validation_result(self, issues: List[ValidationIssue], workflow: Dict[str, Any]) -> ValidationResult:
        """Compile final validation result"""
        
        # Count issues by level
        error_count = len([i for i in issues if i.level == "error"])
        warning_count = len([i for i in issues if i.level == "warning"]) 
        info_count = len([i for i in issues if i.level == "info"])
        
        # Determine if workflow is valid
        valid = error_count == 0 and (not self.strict_mode or warning_count == 0)
        
        # Calculate score (0.0 to 1.0)
        total_issues = len(issues)
        if total_issues == 0:
            score = 1.0
        else:
            # Weight errors more heavily than warnings
            weighted_issues = error_count * 3 + warning_count * 1 + info_count * 0.1
            score = max(0.0, 1.0 - (weighted_issues / 10))  # Normalize to 0-1
        
        # Generate summary
        summary = {
            "total_issues": total_issues,
            "errors": error_count,
            "warnings": warning_count,
            "info": info_count,
            "node_count": len(workflow.get("nodes", [])),
            "connection_count": sum(
                len(output_list)
                for connection_data in workflow.get("connections", {}).values()
                for outputs in connection_data.values()
                for output_list in outputs
            ),
            "categories": {}
        }
        
        # Count by category
        for issue in issues:
            category = issue.category
            summary["categories"][category] = summary["categories"].get(category, 0) + 1
        
        return ValidationResult(
            valid=valid,
            issues=issues,
            score=score,
            summary=summary
        )
    
    def _generate_recommendations(self, result: ValidationResult) -> List[str]:
        """Generate actionable recommendations based on validation results"""
        recommendations = []
        
        if result.summary["errors"] > 0:
            recommendations.append("Fix all validation errors before deploying workflow")
        
        if result.summary["warnings"] > 5:
            recommendations.append("Consider addressing warnings to improve workflow quality")
        
        if result.summary["node_count"] > 30:
            recommendations.append("Consider breaking large workflow into smaller, manageable pieces")
        
        # Category-specific recommendations
        categories = result.summary["categories"]
        
        if categories.get("security", 0) > 0:
            recommendations.append("Review security issues carefully before production deployment")
        
        if categories.get("performance", 0) > 2:
            recommendations.append("Optimize workflow for better performance")
        
        if categories.get("logic", 0) > 0:
            recommendations.append("Review workflow logic to ensure correct execution flow")
        
        return recommendations
