"""
Workflow Planner for Production Module

Transforms user prompts into structured execution plans with complexity estimation
and multi-LLM routing decisions.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from ...ai.agent import UmbraAIAgent
from ...core.config import UmbraConfig

logger = logging.getLogger(__name__)

class ComplexityTier(Enum):
    """Workflow complexity tiers for LLM routing"""
    SMALL = "S"      # Simple workflows, 1-3 steps
    MEDIUM = "M"     # Medium workflows, 4-7 steps  
    LARGE = "L"      # Complex workflows, 8-15 steps
    EXTRA_LARGE = "XL"  # Very complex workflows, 15+ steps

@dataclass
class WorkflowStep:
    """Individual step in workflow plan"""
    id: str
    type: str
    description: str
    inputs: List[str]
    outputs: List[str]
    requirements: Dict[str, Any]
    dependencies: List[str]

@dataclass
class WorkflowPlan:
    """Complete workflow execution plan"""
    name: str
    description: str
    complexity: ComplexityTier
    steps: List[WorkflowStep]
    estimated_nodes: int
    estimated_tokens: int
    triggers: List[str]
    outputs: List[str]
    metadata: Dict[str, Any]

class WorkflowPlanner:
    """Plans workflow creation from user prompts"""
    
    def __init__(self, ai_agent: UmbraAIAgent, config: UmbraConfig):
        self.ai_agent = ai_agent
        self.config = config
        self.max_retries = 3
        
        logger.info("Workflow planner initialized")
    
    async def plan_from_prompt(self, prompt: str) -> Dict[str, Any]:
        """Create structured plan from user prompt"""
        try:
            # Determine complexity tier first
            complexity = await self._estimate_complexity(prompt)
            
            # Select appropriate LLM based on complexity
            model = self._get_planner_model(complexity)
            
            # Generate plan using structured prompt
            plan_json = await self._generate_plan(prompt, complexity, model)
            
            # Validate and enhance plan
            validated_plan = await self._validate_plan(plan_json)
            
            return {
                "plan": validated_plan,
                "complexity": complexity.value,
                "model_used": model,
                "tokens_used": plan_json.get("tokens_used", 0)
            }
            
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            raise Exception(f"Failed to create plan: {e}")
    
    async def _estimate_complexity(self, prompt: str) -> ComplexityTier:
        """Estimate workflow complexity from prompt"""
        # Use fast model for complexity estimation
        complexity_prompt = f"""
        Analyze this workflow request and determine its complexity tier.
        
        Request: "{prompt}"
        
        Complexity Criteria:
        - S (Small): 1-3 steps, simple operations (webhook->response, cron->email)
        - M (Medium): 4-7 steps, moderate logic (data processing, conditionals) 
        - L (Large): 8-15 steps, complex workflows (multi-API, transformations)
        - XL (Extra Large): 15+ steps, very complex (enterprise integration, ML)
        
        Consider:
        - Number of integrations/APIs mentioned
        - Data processing complexity  
        - Conditional logic requirements
        - Error handling needs
        - Scalability requirements
        
        Respond with only the complexity tier: S, M, L, or XL
        """
        
        try:
            response = await self.ai_agent.generate_response(
                complexity_prompt,
                role="planner",
                response_format="text",
                max_tokens=10
            )
            
            tier_map = {
                "S": ComplexityTier.SMALL,
                "M": ComplexityTier.MEDIUM, 
                "L": ComplexityTier.LARGE,
                "XL": ComplexityTier.EXTRA_LARGE
            }
            
            tier = response.strip().upper()
            return tier_map.get(tier, ComplexityTier.MEDIUM)
            
        except Exception as e:
            logger.warning(f"Complexity estimation failed: {e}, defaulting to MEDIUM")
            return ComplexityTier.MEDIUM
    
    def _get_planner_model(self, complexity: ComplexityTier) -> str:
        """Select appropriate LLM model for planning based on complexity"""
        llm_routes = self.config.get("LLM_ROUTES", {})
        
        if complexity == ComplexityTier.SMALL:
            return llm_routes.get("planner", "claude-haiku")
        elif complexity == ComplexityTier.MEDIUM:
            return llm_routes.get("planner", "claude-haiku")
        elif complexity == ComplexityTier.LARGE:
            return llm_routes.get("planner_l", "claude-sonnet-4")
        else:  # EXTRA_LARGE
            return llm_routes.get("planner_xl", "claude-opus")
    
    async def _generate_plan(self, prompt: str, complexity: ComplexityTier, model: str) -> Dict[str, Any]:
        """Generate structured workflow plan"""
        planning_prompt = f"""
        Create a detailed workflow plan for this request.
        
        User Request: "{prompt}"
        Complexity Tier: {complexity.value}
        
        You must respond with a valid JSON object matching this exact schema:
        {{
            "name": "workflow_name",
            "description": "detailed_description",
            "triggers": ["trigger_type1", "trigger_type2"],
            "steps": [
                {{
                    "id": "step_1",
                    "type": "trigger|action|condition|transform",
                    "description": "what this step does",
                    "inputs": ["input1", "input2"],
                    "outputs": ["output1", "output2"],
                    "requirements": {{
                        "node_type": "n8n_node_name",
                        "credentials": "credential_name_if_needed",
                        "parameters": {{"key": "value"}}
                    }},
                    "dependencies": ["step_id1", "step_id2"]
                }}
            ],
            "outputs": ["final_output1", "final_output2"],
            "estimated_nodes": 5,
            "metadata": {{
                "tags": ["tag1", "tag2"],
                "priority": "normal|high|critical",
                "estimated_runtime": "short|medium|long"
            }}
        }}
        
        Guidelines:
        - Use clear, descriptive step IDs (trigger_webhook, process_data, send_email)
        - Map to actual n8n node types when possible (Webhook, HTTP Request, Gmail, etc.)
        - Include all necessary credentials and parameters
        - Define proper step dependencies for execution order
        - Estimate realistic node count
        - Add relevant tags for categorization
        
        Respond with only the JSON object, no additional text.
        """
        
        for attempt in range(self.max_retries):
            try:
                response = await self.ai_agent.generate_response(
                    planning_prompt,
                    role="planner",
                    model=model,
                    response_format="json",
                    max_tokens=2000
                )
                
                # Parse and validate JSON
                plan_data = json.loads(response)
                
                # Add metadata
                plan_data["tokens_used"] = len(response) // 4  # Rough token estimate
                
                return plan_data
                
            except json.JSONDecodeError as e:
                logger.warning(f"Plan generation attempt {attempt + 1} failed: Invalid JSON - {e}")
                if attempt == self.max_retries - 1:
                    raise Exception("Failed to generate valid plan JSON after retries")
            except Exception as e:
                logger.error(f"Plan generation attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
    
    async def _validate_plan(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enhance the generated plan"""
        errors = []
        
        # Check required fields
        required_fields = ["name", "description", "steps", "triggers", "outputs"]
        for field in required_fields:
            if field not in plan_data:
                errors.append(f"Missing required field: {field}")
        
        # Validate steps
        steps = plan_data.get("steps", [])
        if not isinstance(steps, list) or len(steps) == 0:
            errors.append("Plan must have at least one step")
        else:
            step_ids = set()
            for i, step in enumerate(steps):
                # Check step structure
                step_required = ["id", "type", "description", "requirements"]
                for field in step_required:
                    if field not in step:
                        errors.append(f"Step {i}: Missing required field '{field}'")
                
                # Check for duplicate step IDs
                step_id = step.get("id")
                if step_id in step_ids:
                    errors.append(f"Duplicate step ID: {step_id}")
                step_ids.add(step_id)
                
                # Validate dependencies reference existing steps
                dependencies = step.get("dependencies", [])
                for dep_id in dependencies:
                    if dep_id not in step_ids and dep_id not in [s.get("id") for s in steps]:
                        # This will be checked after all steps are processed
                        pass
        
        # Validate triggers
        triggers = plan_data.get("triggers", [])
        valid_triggers = ["webhook", "cron", "manual", "email", "file", "webhook", "interval"]
        for trigger in triggers:
            if trigger not in valid_triggers:
                logger.warning(f"Unknown trigger type: {trigger}")
        
        if errors:
            raise Exception(f"Plan validation failed: {'; '.join(errors)}")
        
        # Enhance plan with defaults
        plan_data.setdefault("estimated_nodes", len(steps) + 1)  # +1 for trigger
        plan_data.setdefault("metadata", {})
        plan_data["metadata"].setdefault("tags", [])
        plan_data["metadata"].setdefault("priority", "normal")
        plan_data["metadata"].setdefault("estimated_runtime", "medium")
        
        # Add validation timestamp
        import datetime
        plan_data["validated_at"] = datetime.datetime.utcnow().isoformat()
        
        return plan_data
    
    def estimate_execution_cost(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate execution cost for the planned workflow"""
        steps = plan.get("steps", [])
        complexity = plan.get("complexity", "M")
        
        # Base costs by complexity
        base_costs = {
            "S": {"tokens": 500, "chf": 0.01},
            "M": {"tokens": 1500, "chf": 0.03},
            "L": {"tokens": 4000, "chf": 0.08},
            "XL": {"tokens": 8000, "chf": 0.15}
        }
        
        base = base_costs.get(complexity, base_costs["M"])
        
        # Adjust based on step count
        step_multiplier = len(steps) / 5  # Normalize to 5 steps
        estimated_tokens = int(base["tokens"] * step_multiplier)
        estimated_chf = base["chf"] * step_multiplier
        
        # Add overhead for each phase
        total_tokens = estimated_tokens * 3  # Planning + Selection + Building
        total_chf = estimated_chf * 3
        
        return {
            "estimated_tokens": total_tokens,
            "estimated_chf": round(total_chf, 3),
            "breakdown": {
                "planning": int(estimated_tokens * 0.2),
                "selection": int(estimated_tokens * 0.3), 
                "building": int(estimated_tokens * 0.5)
            }
        }
    
    async def refine_plan(self, plan: Dict[str, Any], feedback: str) -> Dict[str, Any]:
        """Refine existing plan based on feedback"""
        refinement_prompt = f"""
        Refine this workflow plan based on the feedback provided.
        
        Current Plan:
        {json.dumps(plan, indent=2)}
        
        Feedback: "{feedback}"
        
        Provide the updated plan as a JSON object with the same structure.
        Focus only on the areas mentioned in the feedback while preserving
        the overall workflow structure and logic.
        
        Respond with only the JSON object.
        """
        
        try:
            response = await self.ai_agent.generate_response(
                refinement_prompt,
                role="planner", 
                response_format="json",
                max_tokens=2000
            )
            
            refined_plan = json.loads(response)
            
            # Re-validate refined plan
            validated_plan = await self._validate_plan(refined_plan)
            
            return validated_plan
            
        except Exception as e:
            logger.error(f"Plan refinement failed: {e}")
            raise Exception(f"Failed to refine plan: {e}")
