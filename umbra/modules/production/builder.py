"""
Workflow Builder for Production Module

Constructs valid n8n workflow JSON from node mappings using AI-driven
code generation with strict schema validation.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import copy

from ...ai.agent import UmbraAIAgent
from ...core.config import UmbraConfig

logger = logging.getLogger(__name__)

@dataclass
class WorkflowConnection:
    """Represents a connection between workflow nodes"""
    source_node: str
    source_output: str
    target_node: str
    target_input: str

@dataclass
class WorkflowNode:
    """Represents a complete n8n workflow node"""
    id: str
    name: str
    type: str
    type_version: int
    position: List[int]
    parameters: Dict[str, Any]
    credentials: Optional[Dict[str, Any]] = None

class WorkflowBuilder:
    """Builds n8n workflows from node mappings"""
    
    def __init__(self, ai_agent: UmbraAIAgent, config: UmbraConfig):
        self.ai_agent = ai_agent
        self.config = config
        self.max_retries = 3
        
        # n8n schema constants
        self.default_type_version = 1
        self.node_spacing = 300  # Pixels between nodes
        
        logger.info("Workflow builder initialized")
    
    async def build_workflow(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Build complete n8n workflow from node mapping"""
        try:
            mappings = mapping.get("mappings", [])
            if not mappings:
                raise Exception("No node mappings provided")
            
            # Select appropriate LLM model
            model = self._get_builder_model(len(mappings))
            
            # Generate workflow structure
            workflow_json = await self._generate_workflow(mappings, model)
            
            # Validate and enhance workflow
            enhanced_workflow = await self._enhance_workflow(workflow_json, mappings)
            
            # Add metadata
            enhanced_workflow["tokens_used"] = workflow_json.get("tokens_used", 0)
            enhanced_workflow["builder_version"] = "1.0"
            
            return enhanced_workflow
            
        except Exception as e:
            logger.error(f"Workflow building failed: {e}")
            raise Exception(f"Failed to build workflow: {e}")
    
    def _get_builder_model(self, node_count: int) -> str:
        """Select appropriate LLM model for building based on complexity"""
        llm_routes = self.config.get("LLM_ROUTES", {})
        
        if node_count <= 3:
            return llm_routes.get("builder", "gpt-4o-mini")
        elif node_count <= 7:
            return llm_routes.get("builder", "gpt-4o-mini")
        else:
            return llm_routes.get("builder_l", "gpt-4o")
    
    async def _generate_workflow(self, mappings: List[Dict[str, Any]], model: str) -> Dict[str, Any]:
        """Generate n8n workflow JSON using AI"""
        
        building_prompt = self._build_workflow_prompt(mappings)
        
        for attempt in range(self.max_retries):
            try:
                response = await self.ai_agent.generate_response(
                    building_prompt,
                    role="builder",
                    model=model,
                    response_format="json",
                    max_tokens=4000
                )
                
                # Parse and validate JSON
                workflow_data = json.loads(response)
                workflow_data["tokens_used"] = len(response) // 4  # Rough estimate
                
                return workflow_data
                
            except json.JSONDecodeError as e:
                logger.warning(f"Workflow building attempt {attempt + 1} failed: Invalid JSON - {e}")
                if attempt == self.max_retries - 1:
                    raise Exception("Failed to generate valid workflow JSON")
            except Exception as e:
                logger.error(f"Workflow building attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
    
    def _build_workflow_prompt(self, mappings: List[Dict[str, Any]]) -> str:
        """Build prompt for workflow generation"""
        
        # Prepare mapping information
        mapping_info = []
        for mapping in mappings:
            mapping_info.append({
                "step_id": mapping.get("step_id"),
                "node_type": mapping.get("node_id"),
                "parameters": mapping.get("parameters", {}),
                "reasoning": mapping.get("reasoning", "")
            })
        
        prompt = f"""
        Generate a complete n8n workflow JSON from the provided node mappings.
        
        Node Mappings:
        {json.dumps(mapping_info, indent=2)}
        
        Requirements:
        1. Create valid n8n workflow structure with proper schema
        2. Generate unique node IDs and position nodes logically
        3. Configure parameters for each node based on mappings
        4. Create proper connections between nodes based on data flow
        5. Set appropriate workflow metadata (name, active, etc.)
        
        N8n Workflow Schema:
        {{
            "name": "Generated Workflow",
            "active": false,
            "nodes": [
                {{
                    "id": "unique-node-id",
                    "name": "Node Name",
                    "type": "n8n-nodes-base.nodetype",
                    "typeVersion": 1,
                    "position": [x, y],
                    "parameters": {{
                        "param1": "value1"
                    }},
                    "credentials": {{
                        "credentialType": {{
                            "id": "credential-id",
                            "name": "credential-name"
                        }}
                    }}
                }}
            ],
            "connections": {{
                "source-node-id": {{
                    "main": [
                        [
                            {{
                                "node": "target-node-id",
                                "type": "main",
                                "index": 0
                            }}
                        ]
                    ]
                }}
            }},
            "staticData": {{}},
            "settings": {{
                "executionOrder": "v1"
            }},
            "meta": {{
                "x_generated": true,
                "x_generator": "umbra-production"
            }}
        }}
        
        Guidelines:
        - Start with trigger nodes (webhook, cron, manual)
        - Position nodes left-to-right in execution order
        - Use 300px spacing between nodes horizontally
        - Connect nodes based on logical data flow
        - Include all required parameters for each node type
        - Set workflow as inactive by default (active: false)
        - Add generator metadata to meta section
        - Use proper n8n node type names exactly as provided
        - Generate UUIDs for node IDs or use descriptive names
        
        Connection Rules:
        - Trigger nodes connect to first action nodes
        - Action nodes connect to subsequent actions or conditions
        - Condition nodes have multiple output paths
        - Final nodes may not have outgoing connections
        
        Respond with only the JSON workflow object, no additional text.
        """
        
        return prompt
    
    async def _enhance_workflow(self, workflow_data: Dict[str, Any], mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhance and validate the generated workflow"""
        enhanced = copy.deepcopy(workflow_data)
        
        # Ensure required fields exist
        enhanced.setdefault("name", "Generated Workflow")
        enhanced.setdefault("active", False)
        enhanced.setdefault("nodes", [])
        enhanced.setdefault("connections", {})
        enhanced.setdefault("staticData", {})
        enhanced.setdefault("settings", {"executionOrder": "v1"})
        enhanced.setdefault("meta", {})
        
        # Add enhancement metadata
        enhanced["meta"]["x_generated"] = True
        enhanced["meta"]["x_generator"] = "umbra-production"
        enhanced["meta"]["x_node_count"] = len(enhanced["nodes"])
        
        # Validate and fix nodes
        enhanced["nodes"] = await self._validate_nodes(enhanced["nodes"], mappings)
        
        # Validate and fix connections
        enhanced["connections"] = self._validate_connections(enhanced["connections"], enhanced["nodes"])
        
        # Add default settings
        enhanced["settings"].update({
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner"
        })
        
        return enhanced
    
    async def _validate_nodes(self, nodes: List[Dict[str, Any]], mappings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and fix workflow nodes"""
        validated_nodes = []
        mapping_by_step = {m.get("step_id"): m for m in mappings}
        
        for i, node in enumerate(nodes):
            # Ensure required fields
            if "id" not in node:
                node["id"] = f"node_{i}_{uuid.uuid4().hex[:8]}"
            
            if "name" not in node:
                node["name"] = f"Node {i + 1}"
            
            if "type" not in node:
                # Try to get from mapping
                step_id = node.get("step_id") or f"step_{i}"
                if step_id in mapping_by_step:
                    node["type"] = mapping_by_step[step_id].get("node_id", "n8n-nodes-base.noOp")
                else:
                    node["type"] = "n8n-nodes-base.noOp"
            
            if "typeVersion" not in node:
                node["typeVersion"] = self.default_type_version
            
            if "position" not in node:
                node["position"] = [i * self.node_spacing, 200]
            
            if "parameters" not in node:
                node["parameters"] = {}
            
            # Merge parameters from mapping
            step_id = node.get("step_id") or f"step_{i}"
            if step_id in mapping_by_step:
                mapping_params = mapping_by_step[step_id].get("parameters", {})
                node["parameters"].update(mapping_params)
            
            # Remove step_id as it's not part of n8n schema
            if "step_id" in node:
                del node["step_id"]
            
            validated_nodes.append(node)
        
        return validated_nodes
    
    def _validate_connections(self, connections: Dict[str, Any], nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate and fix workflow connections"""
        node_ids = {node["id"] for node in nodes}
        validated_connections = {}
        
        for source_id, connection_data in connections.items():
            # Skip if source node doesn't exist
            if source_id not in node_ids:
                logger.warning(f"Connection source node {source_id} not found")
                continue
            
            # Validate connection structure
            if not isinstance(connection_data, dict):
                continue
            
            validated_outputs = {}
            for output_type, output_connections in connection_data.items():
                if not isinstance(output_connections, list):
                    continue
                
                validated_output_connections = []
                for connection_list in output_connections:
                    if not isinstance(connection_list, list):
                        continue
                    
                    valid_connections = []
                    for connection in connection_list:
                        if isinstance(connection, dict) and "node" in connection:
                            target_node = connection["node"]
                            if target_node in node_ids:
                                # Ensure required connection fields
                                connection.setdefault("type", "main")
                                connection.setdefault("index", 0)
                                valid_connections.append(connection)
                            else:
                                logger.warning(f"Connection target node {target_node} not found")
                    
                    if valid_connections:
                        validated_output_connections.append(valid_connections)
                
                if validated_output_connections:
                    validated_outputs[output_type] = validated_output_connections
            
            if validated_outputs:
                validated_connections[source_id] = validated_outputs
        
        # Ensure all nodes except the last have connections
        self._ensure_basic_connectivity(validated_connections, nodes)
        
        return validated_connections
    
    def _ensure_basic_connectivity(self, connections: Dict[str, Any], nodes: List[Dict[str, Any]]):
        """Ensure basic connectivity between nodes"""
        node_ids = [node["id"] for node in nodes]
        
        # Simple linear connection if no connections exist
        if not connections and len(nodes) > 1:
            for i in range(len(nodes) - 1):
                source_id = node_ids[i]
                target_id = node_ids[i + 1]
                
                connections[source_id] = {
                    "main": [[{
                        "node": target_id,
                        "type": "main",
                        "index": 0
                    }]]
                }
    
    async def patch_workflow(self, workflow_json: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        """Apply patch to existing workflow"""
        try:
            patched_workflow = copy.deepcopy(workflow_json)
            
            # Apply different types of patches
            patch_type = patch.get("type", "merge")
            
            if patch_type == "merge":
                # Merge patch data into workflow
                self._merge_patch(patched_workflow, patch.get("data", {}))
            
            elif patch_type == "node_update":
                # Update specific node
                node_id = patch.get("node_id")
                node_updates = patch.get("updates", {})
                self._update_node(patched_workflow, node_id, node_updates)
            
            elif patch_type == "connection_update":
                # Update connections
                connection_updates = patch.get("connections", {})
                patched_workflow["connections"].update(connection_updates)
            
            elif patch_type == "parameter_update":
                # Update node parameters
                node_id = patch.get("node_id")
                parameter_updates = patch.get("parameters", {})
                self._update_node_parameters(patched_workflow, node_id, parameter_updates)
            
            else:
                raise Exception(f"Unknown patch type: {patch_type}")
            
            return patched_workflow
            
        except Exception as e:
            logger.error(f"Workflow patching failed: {e}")
            raise Exception(f"Failed to patch workflow: {e}")
    
    def _merge_patch(self, workflow: Dict[str, Any], patch_data: Dict[str, Any]):
        """Merge patch data into workflow"""
        for key, value in patch_data.items():
            if isinstance(value, dict) and key in workflow and isinstance(workflow[key], dict):
                # Recursive merge for nested dicts
                self._merge_patch(workflow[key], value)
            else:
                # Direct replacement
                workflow[key] = value
    
    def _update_node(self, workflow: Dict[str, Any], node_id: str, updates: Dict[str, Any]):
        """Update specific node in workflow"""
        nodes = workflow.get("nodes", [])
        for node in nodes:
            if node.get("id") == node_id:
                node.update(updates)
                break
    
    def _update_node_parameters(self, workflow: Dict[str, Any], node_id: str, parameter_updates: Dict[str, Any]):
        """Update node parameters specifically"""
        nodes = workflow.get("nodes", [])
        for node in nodes:
            if node.get("id") == node_id:
                node.setdefault("parameters", {})
                node["parameters"].update(parameter_updates)
                break
    
    def validate_workflow_schema(self, workflow: Dict[str, Any]) -> Dict[str, bool]:
        """Validate workflow against n8n schema"""
        errors = []
        
        # Check required top-level fields
        required_fields = ["name", "nodes", "connections"]
        for field in required_fields:
            if field not in workflow:
                errors.append(f"Missing required field: {field}")
        
        # Validate nodes
        nodes = workflow.get("nodes", [])
        if not isinstance(nodes, list):
            errors.append("Nodes must be an array")
        else:
            for i, node in enumerate(nodes):
                node_errors = self._validate_node_schema(node, i)
                errors.extend(node_errors)
        
        # Validate connections
        connections = workflow.get("connections", {})
        if not isinstance(connections, dict):
            errors.append("Connections must be an object")
        else:
            connection_errors = self._validate_connection_schema(connections, nodes)
            errors.extend(connection_errors)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _validate_node_schema(self, node: Dict[str, Any], index: int) -> List[str]:
        """Validate individual node schema"""
        errors = []
        
        # Required node fields
        required_fields = ["id", "name", "type", "typeVersion", "position"]
        for field in required_fields:
            if field not in node:
                errors.append(f"Node {index}: Missing required field '{field}'")
        
        # Validate field types
        if "position" in node and not isinstance(node["position"], list):
            errors.append(f"Node {index}: Position must be an array")
        
        if "typeVersion" in node and not isinstance(node["typeVersion"], int):
            errors.append(f"Node {index}: TypeVersion must be a number")
        
        if "parameters" in node and not isinstance(node["parameters"], dict):
            errors.append(f"Node {index}: Parameters must be an object")
        
        return errors
    
    def _validate_connection_schema(self, connections: Dict[str, Any], nodes: List[Dict[str, Any]]) -> List[str]:
        """Validate connections schema"""
        errors = []
        node_ids = {node.get("id") for node in nodes}
        
        for source_id, connection_data in connections.items():
            if source_id not in node_ids:
                errors.append(f"Connection source '{source_id}' references non-existent node")
            
            if not isinstance(connection_data, dict):
                errors.append(f"Connection data for '{source_id}' must be an object")
                continue
            
            for output_type, outputs in connection_data.items():
                if not isinstance(outputs, list):
                    errors.append(f"Connection outputs for '{source_id}.{output_type}' must be an array")
                    continue
                
                for i, output_list in enumerate(outputs):
                    if not isinstance(output_list, list):
                        errors.append(f"Connection output {i} for '{source_id}.{output_type}' must be an array")
                        continue
                    
                    for j, connection in enumerate(output_list):
                        if not isinstance(connection, dict) or "node" not in connection:
                            errors.append(f"Invalid connection {j} in '{source_id}.{output_type}[{i}]'")
                        elif connection["node"] not in node_ids:
                            errors.append(f"Connection target '{connection['node']}' references non-existent node")
        
        return errors
    
    def generate_workflow_summary(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of workflow structure"""
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        # Count node types
        node_types = {}
        for node in nodes:
            node_type = node.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        # Count connections
        total_connections = 0
        for connection_data in connections.values():
            for outputs in connection_data.values():
                for output_list in outputs:
                    total_connections += len(output_list)
        
        # Identify triggers and endpoints
        triggers = [n for n in nodes if "trigger" in n.get("type", "").lower()]
        endpoints = self._find_endpoint_nodes(nodes, connections)
        
        return {
            "name": workflow.get("name", "Unnamed"),
            "node_count": len(nodes),
            "connection_count": total_connections,
            "node_types": node_types,
            "triggers": len(triggers),
            "endpoints": len(endpoints),
            "complexity": self._calculate_complexity(nodes, connections),
            "estimated_execution_time": self._estimate_execution_time(nodes)
        }
    
    def _find_endpoint_nodes(self, nodes: List[Dict[str, Any]], connections: Dict[str, Any]) -> List[str]:
        """Find nodes that don't have outgoing connections"""
        node_ids = {node["id"] for node in nodes}
        connected_nodes = set()
        
        for connection_data in connections.values():
            for outputs in connection_data.values():
                for output_list in outputs:
                    for connection in output_list:
                        connected_nodes.add(connection.get("node"))
        
        return list(node_ids - connected_nodes)
    
    def _calculate_complexity(self, nodes: List[Dict[str, Any]], connections: Dict[str, Any]) -> str:
        """Calculate workflow complexity"""
        node_count = len(nodes)
        connection_count = sum(
            len(output_list)
            for connection_data in connections.values()
            for outputs in connection_data.values()
            for output_list in outputs
        )
        
        if node_count <= 3 and connection_count <= 2:
            return "Simple"
        elif node_count <= 7 and connection_count <= 10:
            return "Medium"
        elif node_count <= 15 and connection_count <= 25:
            return "Complex"
        else:
            return "Very Complex"
    
    def _estimate_execution_time(self, nodes: List[Dict[str, Any]]) -> str:
        """Estimate workflow execution time"""
        # Simple heuristic based on node types
        time_weights = {
            "webhook": 0.1,
            "http": 2.0,
            "code": 0.5,
            "if": 0.1,
            "set": 0.1,
            "email": 3.0,
            "file": 1.0
        }
        
        total_time = 0
        for node in nodes:
            node_type = node.get("type", "").lower()
            for pattern, weight in time_weights.items():
                if pattern in node_type:
                    total_time += weight
                    break
            else:
                total_time += 1.0  # Default weight
        
        if total_time < 5:
            return "Fast (< 5s)"
        elif total_time < 30:
            return "Medium (5-30s)"
        else:
            return "Slow (> 30s)"
