"""
Node Selector for Production Module

Intelligently selects appropriate n8n nodes from catalog based on workflow plan
using AI-driven matching and constraint validation.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from ...ai.agent import UmbraAIAgent
from ...core.config import UmbraConfig

logger = logging.getLogger(__name__)

@dataclass
class NodeMapping:
    """Mapping between workflow step and selected node"""
    step_id: str
    node_id: str
    node_name: str
    confidence: float
    parameters: Dict[str, Any]
    reasoning: str
    alternatives: List[str]

@dataclass
class SelectionResult:
    """Complete node selection result"""
    mappings: List[NodeMapping]
    total_confidence: float
    warnings: List[str]
    tokens_used: int

class NodeSelector:
    """Selects optimal nodes from catalog for workflow steps"""
    
    def __init__(self, ai_agent: UmbraAIAgent, config: UmbraConfig):
        self.ai_agent = ai_agent
        self.config = config
        self.max_retries = 3
        
        logger.info("Node selector initialized")
    
    async def select_nodes(self, plan: Dict[str, Any], catalog: Dict[str, Any]) -> Dict[str, Any]:
        """Select nodes from catalog based on workflow plan"""
        try:
            steps = plan.get("steps", [])
            step_catalogs = catalog.get("step_catalogs", {})
            
            if not steps:
                raise Exception("No steps in plan")
            
            # Select appropriate LLM model
            model = self._get_selector_model(len(steps))
            
            # Perform node selection
            selection_result = await self._perform_selection(steps, step_catalogs, model)
            
            # Validate selections
            validated_result = await self._validate_selections(selection_result, step_catalogs)
            
            return {
                "mappings": [mapping.__dict__ for mapping in validated_result.mappings],
                "confidence": validated_result.total_confidence,
                "warnings": validated_result.warnings,
                "tokens_used": validated_result.tokens_used,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Node selection failed: {e}")
            raise Exception(f"Failed to select nodes: {e}")
    
    def _get_selector_model(self, step_count: int) -> str:
        """Select appropriate LLM model based on selection complexity"""
        llm_routes = self.config.get("LLM_ROUTES", {})
        
        if step_count <= 3:
            return llm_routes.get("planner", "claude-haiku")
        elif step_count <= 7:
            return llm_routes.get("planner", "claude-haiku") 
        else:
            return llm_routes.get("planner_l", "claude-sonnet-4")
    
    async def _perform_selection(self, steps: List[Dict[str, Any]], step_catalogs: Dict[str, Any], model: str) -> SelectionResult:
        """Perform AI-driven node selection"""
        
        selection_prompt = self._build_selection_prompt(steps, step_catalogs)
        
        for attempt in range(self.max_retries):
            try:
                response = await self.ai_agent.generate_response(
                    selection_prompt,
                    role="planner",
                    model=model,
                    response_format="json",
                    max_tokens=3000
                )
                
                # Parse response
                selection_data = json.loads(response)
                
                # Convert to structured result
                result = self._parse_selection_response(selection_data)
                result.tokens_used = len(response) // 4  # Rough estimate
                
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Selection attempt {attempt + 1} failed: Invalid JSON - {e}")
                if attempt == self.max_retries - 1:
                    raise Exception("Failed to generate valid selection JSON")
            except Exception as e:
                logger.error(f"Selection attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
    
    def _build_selection_prompt(self, steps: List[Dict[str, Any]], step_catalogs: Dict[str, Any]) -> str:
        """Build prompt for node selection"""
        
        # Prepare catalog information
        catalog_info = {}
        for step_id, entries in step_catalogs.items():
            catalog_info[step_id] = [
                {
                    "node_id": entry["node"]["id"],
                    "name": entry["node"]["display_name"],
                    "description": entry["node"]["description"],
                    "category": entry["node"]["category"],
                    "score": entry["relevance_score"],
                    "tags": entry["tags"],
                    "use_cases": entry["use_cases"],
                    "parameters": entry["node"]["parameters"][:3],  # Limit for brevity
                    "credentials": entry["node"]["credentials"]
                }
                for entry in entries
            ]
        
        prompt = f"""
        Select the best n8n nodes for each workflow step from the provided catalog.
        
        Workflow Steps:
        {json.dumps(steps, indent=2)}
        
        Available Nodes by Step:
        {json.dumps(catalog_info, indent=2)}
        
        Selection Criteria:
        1. Choose the highest relevance score node that matches step requirements
        2. Ensure node capabilities align with step type (trigger/action/condition)
        3. Consider credential requirements and availability
        4. Prefer nodes with proven use cases for the scenario
        5. Validate that selected nodes can connect properly (inputs/outputs)
        
        Response Format (JSON only):
        {{
            "selections": [
                {{
                    "step_id": "step_1",
                    "selected_node_id": "n8n-nodes-base.webhook",
                    "confidence": 0.95,
                    "reasoning": "Best match for webhook trigger requirement",
                    "parameters": {{
                        "path": "workflow-trigger",
                        "httpMethod": "POST"
                    }},
                    "alternatives": ["n8n-nodes-base.manualTrigger"]
                }}
            ],
            "overall_confidence": 0.88,
            "warnings": ["Step X requires credentials that may not be available"]
        }}
        
        Guidelines:
        - Confidence should reflect how well the node matches the step (0.0-1.0)
        - Include essential parameters needed for the node to function
        - List 1-2 alternative nodes if available
        - Add warnings for potential issues (missing credentials, complex setup)
        - Ensure all selected nodes are from the provided catalog
        
        Respond with only the JSON object, no additional text.
        """
        
        return prompt
    
    def _parse_selection_response(self, response_data: Dict[str, Any]) -> SelectionResult:
        """Parse AI response into structured SelectionResult"""
        selections = response_data.get("selections", [])
        overall_confidence = response_data.get("overall_confidence", 0.0)
        warnings = response_data.get("warnings", [])
        
        mappings = []
        for selection in selections:
            mapping = NodeMapping(
                step_id=selection.get("step_id"),
                node_id=selection.get("selected_node_id"),
                node_name=selection.get("selected_node_id", "").split(".")[-1],  # Extract name
                confidence=selection.get("confidence", 0.0),
                parameters=selection.get("parameters", {}),
                reasoning=selection.get("reasoning", ""),
                alternatives=selection.get("alternatives", [])
            )
            mappings.append(mapping)
        
        return SelectionResult(
            mappings=mappings,
            total_confidence=overall_confidence,
            warnings=warnings,
            tokens_used=0  # Will be set later
        )
    
    async def _validate_selections(self, result: SelectionResult, step_catalogs: Dict[str, Any]) -> SelectionResult:
        """Validate node selections against catalog and constraints"""
        validated_mappings = []
        additional_warnings = []
        
        for mapping in result.mappings:
            # Check if selected node exists in catalog for this step
            step_catalog = step_catalogs.get(mapping.step_id, [])
            available_nodes = {entry["node"]["id"] for entry in step_catalog}
            
            if mapping.node_id not in available_nodes:
                additional_warnings.append(f"Selected node {mapping.node_id} not in catalog for step {mapping.step_id}")
                # Try to find alternative
                if step_catalog:
                    # Use highest scoring alternative
                    best_alternative = step_catalog[0]["node"]["id"]
                    mapping.node_id = best_alternative
                    mapping.confidence *= 0.7  # Reduce confidence
                    mapping.reasoning += f" (Fallback to {best_alternative})"
            
            # Validate parameters
            validated_params = self._validate_parameters(mapping, step_catalog)
            mapping.parameters = validated_params
            
            validated_mappings.append(mapping)
        
        # Update result
        result.mappings = validated_mappings
        result.warnings.extend(additional_warnings)
        
        # Recalculate overall confidence
        if validated_mappings:
            result.total_confidence = sum(m.confidence for m in validated_mappings) / len(validated_mappings)
        
        return result
    
    def _validate_parameters(self, mapping: NodeMapping, step_catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate and enhance node parameters"""
        # Find node info in catalog
        node_info = None
        for entry in step_catalog:
            if entry["node"]["id"] == mapping.node_id:
                node_info = entry["node"]
                break
        
        if not node_info:
            return mapping.parameters
        
        validated_params = mapping.parameters.copy()
        node_params = node_info.get("parameters", [])
        
        # Check required parameters
        for param in node_params:
            param_name = param.get("name")
            is_required = param.get("required", False)
            
            if is_required and param_name not in validated_params:
                # Add default value based on parameter type
                param_type = param.get("type", "string")
                default_value = self._get_default_parameter_value(param_type, param_name)
                if default_value is not None:
                    validated_params[param_name] = default_value
        
        return validated_params
    
    def _get_default_parameter_value(self, param_type: str, param_name: str) -> Any:
        """Get sensible default value for parameter"""
        defaults = {
            "string": "",
            "number": 0,
            "boolean": False,
            "array": [],
            "object": {}
        }
        
        # Special defaults for common parameters
        if param_name.lower() in ["method", "httpmethod"]:
            return "GET"
        elif param_name.lower() in ["path", "url"]:
            return "/"
        elif param_name.lower() in ["timeout"]:
            return 10000
        
        return defaults.get(param_type.lower())
    
    async def optimize_selections(self, result: Dict[str, Any], optimization_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize node selections based on additional criteria"""
        try:
            mappings = result.get("mappings", [])
            if not mappings:
                return result
            
            # Apply optimization criteria
            criteria = optimization_criteria.get("criteria", {})
            
            optimized_mappings = []
            for mapping_data in mappings:
                mapping = NodeMapping(**mapping_data)
                
                # Performance optimization
                if criteria.get("optimize_for_performance"):
                    mapping = self._optimize_for_performance(mapping)
                
                # Cost optimization  
                if criteria.get("optimize_for_cost"):
                    mapping = self._optimize_for_cost(mapping)
                
                # Reliability optimization
                if criteria.get("optimize_for_reliability"):
                    mapping = self._optimize_for_reliability(mapping)
                
                optimized_mappings.append(mapping.__dict__)
            
            result["mappings"] = optimized_mappings
            result["optimized"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"Selection optimization failed: {e}")
            return result
    
    def _optimize_for_performance(self, mapping: NodeMapping) -> NodeMapping:
        """Optimize mapping for performance"""
        # Adjust parameters for better performance
        if "timeout" in mapping.parameters:
            # Reduce timeout for faster failures
            mapping.parameters["timeout"] = min(mapping.parameters["timeout"], 5000)
        
        if "retries" in mapping.parameters:
            # Limit retries for faster processing
            mapping.parameters["retries"] = min(mapping.parameters.get("retries", 1), 2)
        
        return mapping
    
    def _optimize_for_cost(self, mapping: NodeMapping) -> NodeMapping:
        """Optimize mapping for cost efficiency"""
        # Prefer simpler nodes or parameters that reduce external calls
        if "batchSize" in mapping.parameters:
            # Increase batch size to reduce API calls
            mapping.parameters["batchSize"] = max(mapping.parameters.get("batchSize", 1), 10)
        
        return mapping
    
    def _optimize_for_reliability(self, mapping: NodeMapping) -> NodeMapping:
        """Optimize mapping for reliability"""
        # Add error handling and retry logic
        if "retries" in mapping.parameters:
            # Increase retries for better reliability
            mapping.parameters["retries"] = max(mapping.parameters.get("retries", 1), 3)
        
        if "timeout" in mapping.parameters:
            # Increase timeout for more reliable operations
            mapping.parameters["timeout"] = max(mapping.parameters.get("timeout", 5000), 15000)
        
        return mapping
    
    async def explain_selection(self, mapping_data: Dict[str, Any], step_data: Dict[str, Any]) -> Dict[str, Any]:
        """Provide detailed explanation for a node selection"""
        try:
            explanation_prompt = f"""
            Explain why this node was selected for the given workflow step.
            
            Step: {json.dumps(step_data, indent=2)}
            Selected Node: {mapping_data.get('node_id')}
            Confidence: {mapping_data.get('confidence')}
            Parameters: {json.dumps(mapping_data.get('parameters', {}), indent=2)}
            
            Provide a detailed explanation covering:
            1. Why this node is the best fit for the step requirements
            2. How the node capabilities match the step type and description
            3. What the configured parameters do
            4. Any potential limitations or considerations
            5. Alternative approaches if applicable
            
            Keep the explanation clear and technical but accessible.
            """
            
            explanation = await self.ai_agent.generate_response(
                explanation_prompt,
                role="planner",
                response_format="text",
                max_tokens=500
            )
            
            return {
                "explanation": explanation,
                "selection_rationale": mapping_data.get("reasoning", ""),
                "confidence_factors": self._analyze_confidence_factors(mapping_data),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Selection explanation failed: {e}")
            return {"error": f"Failed to explain selection: {e}"}
    
    def _analyze_confidence_factors(self, mapping_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze factors contributing to selection confidence"""
        confidence = mapping_data.get("confidence", 0.0)
        
        factors = {
            "node_match": "High" if confidence > 0.8 else "Medium" if confidence > 0.5 else "Low",
            "parameter_completeness": "Good" if mapping_data.get("parameters") else "Basic",
            "alternatives_available": len(mapping_data.get("alternatives", [])) > 0,
            "reasoning_quality": len(mapping_data.get("reasoning", "")) > 20
        }
        
        return factors
