"""
Production Controller for Production Module

Manages multi-LLM routing, escalation policies, retry logic, and overall
orchestration of the workflow creation process.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import time

from ...ai.agent import UmbraAIAgent
from ...core.config import UmbraConfig

logger = logging.getLogger(__name__)

class EscalationLevel(Enum):
    """Escalation levels for LLM routing"""
    NONE = "none"
    RETRY_SAME = "retry_same"
    UPGRADE_MODEL = "upgrade_model"
    HUMAN_REVIEW = "human_review"

class ProcessingStage(Enum):
    """Stages in workflow creation process"""
    PLANNING = "planning"
    CATALOG = "catalog"
    SELECTION = "selection"
    BUILDING = "building"
    VALIDATION = "validation"
    TESTING = "testing"

@dataclass
class ExecutionAttempt:
    """Record of a processing attempt"""
    stage: ProcessingStage
    model: str
    attempt: int
    start_time: float
    end_time: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    tokens_used: int = 0
    cost_chf: float = 0.0

@dataclass
class EscalationPolicy:
    """Escalation policy for a stage"""
    max_attempts: int = 3
    retry_delay: float = 1.0
    upgrade_after_attempts: int = 2
    max_cost_chf: float = 0.50
    max_tokens: int = 10000
    timeout_seconds: float = 30.0

class ProductionController:
    """Controls workflow creation process with escalation and retries"""
    
    def __init__(self, ai_agent: UmbraAIAgent, config: UmbraConfig):
        self.ai_agent = ai_agent
        self.config = config
        
        # Escalation policies by stage
        self.policies = self._load_escalation_policies()
        
        # Model upgrade paths
        self.model_upgrades = self._load_model_upgrades()
        
        # Execution tracking
        self.execution_history: List[ExecutionAttempt] = []
        
        logger.info("Production controller initialized")
    
    def _load_escalation_policies(self) -> Dict[ProcessingStage, EscalationPolicy]:
        """Load escalation policies from config"""
        config_policies = self.config.get("PROD_ESCALATION_POLICIES", {})
        
        default_policies = {
            ProcessingStage.PLANNING: EscalationPolicy(
                max_attempts=3,
                retry_delay=1.0,
                upgrade_after_attempts=2,
                max_cost_chf=0.10,
                max_tokens=2000,
                timeout_seconds=30.0
            ),
            ProcessingStage.CATALOG: EscalationPolicy(
                max_attempts=2,
                retry_delay=0.5,
                upgrade_after_attempts=1,
                max_cost_chf=0.05,
                max_tokens=1000,
                timeout_seconds=15.0
            ),
            ProcessingStage.SELECTION: EscalationPolicy(
                max_attempts=3,
                retry_delay=1.0,
                upgrade_after_attempts=2,
                max_cost_chf=0.15,
                max_tokens=3000,
                timeout_seconds=30.0
            ),
            ProcessingStage.BUILDING: EscalationPolicy(
                max_attempts=4,
                retry_delay=2.0,
                upgrade_after_attempts=2,
                max_cost_chf=0.25,
                max_tokens=4000,
                timeout_seconds=45.0
            ),
            ProcessingStage.VALIDATION: EscalationPolicy(
                max_attempts=2,
                retry_delay=0.5,
                upgrade_after_attempts=1,
                max_cost_chf=0.05,
                max_tokens=500,
                timeout_seconds=10.0
            ),
            ProcessingStage.TESTING: EscalationPolicy(
                max_attempts=3,
                retry_delay=3.0,
                upgrade_after_attempts=2,
                max_cost_chf=0.10,
                max_tokens=1000,
                timeout_seconds=60.0
            )
        }
        
        # Override with config values
        for stage_name, policy_config in config_policies.items():
            try:
                stage = ProcessingStage(stage_name)
                if stage in default_policies:
                    # Update policy with config values
                    policy = default_policies[stage]
                    for key, value in policy_config.items():
                        if hasattr(policy, key):
                            setattr(policy, key, value)
            except ValueError:
                logger.warning(f"Unknown escalation policy stage: {stage_name}")
        
        return default_policies
    
    def _load_model_upgrades(self) -> Dict[str, str]:
        """Load model upgrade paths"""
        llm_routes = self.config.get("LLM_ROUTES", {})
        
        return {
            # Planning upgrades
            llm_routes.get("planner", "claude-haiku"): llm_routes.get("planner_l", "claude-sonnet-4"),
            llm_routes.get("planner_l", "claude-sonnet-4"): llm_routes.get("planner_xl", "claude-opus"),
            
            # Building upgrades
            llm_routes.get("builder", "gpt-4o-mini"): llm_routes.get("builder_l", "gpt-4o"),
            
            # Controller upgrades (for complex decisions)
            llm_routes.get("controller", "claude-sonnet-4"): llm_routes.get("planner_xl", "claude-opus")
        }
    
    async def execute_with_escalation(
        self,
        stage: ProcessingStage,
        operation_func,
        initial_model: str,
        *args,
        **kwargs
    ) -> Tuple[Any, List[ExecutionAttempt]]:
        """Execute operation with escalation and retry logic"""
        
        policy = self.policies.get(stage, EscalationPolicy())
        attempts = []
        current_model = initial_model
        
        for attempt in range(1, policy.max_attempts + 1):
            attempt_record = ExecutionAttempt(
                stage=stage,
                model=current_model,
                attempt=attempt,
                start_time=time.time()
            )
            
            try:
                # Check resource limits
                if self._check_resource_limits(stage, attempts, policy):
                    attempt_record.error = "Resource limits exceeded"
                    attempts.append(attempt_record)
                    break
                
                # Execute operation with timeout
                result = await asyncio.wait_for(
                    operation_func(*args, model=current_model, **kwargs),
                    timeout=policy.timeout_seconds
                )
                
                # Record successful attempt
                attempt_record.end_time = time.time()
                attempt_record.success = True
                attempt_record.tokens_used = result.get("tokens_used", 0)
                attempt_record.cost_chf = self._estimate_cost(attempt_record.tokens_used, current_model)
                attempts.append(attempt_record)
                
                logger.info(f"Stage {stage.value} succeeded on attempt {attempt} with {current_model}")
                return result, attempts
                
            except asyncio.TimeoutError:
                attempt_record.end_time = time.time()
                attempt_record.error = f"Timeout after {policy.timeout_seconds}s"
                logger.warning(f"Stage {stage.value} attempt {attempt} timed out")
                
            except Exception as e:
                attempt_record.end_time = time.time()
                attempt_record.error = str(e)
                logger.warning(f"Stage {stage.value} attempt {attempt} failed: {e}")
            
            attempts.append(attempt_record)
            
            # Determine escalation action
            escalation = self._determine_escalation(attempt, policy, current_model)
            
            if escalation == EscalationLevel.RETRY_SAME:
                # Retry with same model after delay
                await asyncio.sleep(policy.retry_delay)
                continue
                
            elif escalation == EscalationLevel.UPGRADE_MODEL:
                # Upgrade to more powerful model
                upgraded_model = self.model_upgrades.get(current_model)
                if upgraded_model:
                    current_model = upgraded_model
                    logger.info(f"Escalating {stage.value} to model {current_model}")
                    await asyncio.sleep(policy.retry_delay)
                    continue
                else:
                    logger.warning(f"No upgrade path available for {current_model}")
                    break
                    
            elif escalation == EscalationLevel.HUMAN_REVIEW:
                logger.error(f"Stage {stage.value} requires human review after {attempt} attempts")
                break
            
            else:  # EscalationLevel.NONE
                break
        
        # All attempts failed
        raise Exception(f"Stage {stage.value} failed after {len(attempts)} attempts")
    
    def _determine_escalation(self, attempt: int, policy: EscalationPolicy, current_model: str) -> EscalationLevel:
        """Determine appropriate escalation action"""
        
        # Check if we should upgrade model
        if attempt >= policy.upgrade_after_attempts and current_model in self.model_upgrades:
            return EscalationLevel.UPGRADE_MODEL
        
        # Check if we should retry with same model
        if attempt < policy.max_attempts:
            return EscalationLevel.RETRY_SAME
        
        # Check if human review is needed (complex failures)
        if attempt >= policy.max_attempts - 1:
            return EscalationLevel.HUMAN_REVIEW
        
        return EscalationLevel.NONE
    
    def _check_resource_limits(self, stage: ProcessingStage, attempts: List[ExecutionAttempt], policy: EscalationPolicy) -> bool:
        """Check if resource limits are exceeded"""
        
        # Check cost limits
        total_cost = sum(a.cost_chf for a in attempts)
        if total_cost >= policy.max_cost_chf:
            logger.warning(f"Cost limit exceeded for {stage.value}: {total_cost:.3f} CHF")
            return True
        
        # Check token limits
        total_tokens = sum(a.tokens_used for a in attempts)
        if total_tokens >= policy.max_tokens:
            logger.warning(f"Token limit exceeded for {stage.value}: {total_tokens} tokens")
            return True
        
        return False
    
    def _estimate_cost(self, tokens: int, model: str) -> float:
        """Estimate cost in CHF for tokens and model"""
        # Cost per 1K tokens in CHF (approximate)
        model_costs = {
            "claude-haiku": 0.0005,
            "claude-sonnet-4": 0.006,
            "claude-opus": 0.030,
            "gpt-4o-mini": 0.0003,
            "gpt-4o": 0.010,
            "gpt-4": 0.060
        }
        
        cost_per_1k = model_costs.get(model, 0.005)  # Default cost
        return (tokens / 1000) * cost_per_1k
    
    async def orchestrate_workflow_creation(self, prompt: str) -> Dict[str, Any]:
        """Orchestrate complete workflow creation process"""
        start_time = time.time()
        all_attempts = []
        
        try:
            # Stage 1: Planning
            logger.info("Starting workflow planning stage")
            from .planner import WorkflowPlanner
            planner = WorkflowPlanner(self.ai_agent, self.config)
            
            async def plan_operation(*args, model=None, **kwargs):
                return await planner.plan_from_prompt(prompt)
            
            plan_result, plan_attempts = await self.execute_with_escalation(
                ProcessingStage.PLANNING,
                plan_operation,
                self.config.get("LLM_ROUTES", {}).get("planner", "claude-haiku")
            )
            all_attempts.extend(plan_attempts)
            
            # Stage 2: Catalog scraping (deterministic, no escalation needed)
            logger.info("Starting catalog scraping stage")
            from .catalog import CatalogManager
            from .n8n_client import N8nClient
            
            n8n_client = N8nClient(self.config)
            catalog_manager = CatalogManager(n8n_client, self.config)
            
            steps = plan_result.get("plan", {}).get("steps", [])
            catalog_result = await catalog_manager.scrape_catalog(steps)
            
            # Stage 3: Node selection
            logger.info("Starting node selection stage")
            from .selector import NodeSelector
            selector = NodeSelector(self.ai_agent, self.config)
            
            async def select_operation(*args, model=None, **kwargs):
                # Use the model parameter if provided
                if model:
                    # Temporarily update selector's agent model preference
                    return await selector.select_nodes(plan_result["plan"], catalog_result)
                return await selector.select_nodes(plan_result["plan"], catalog_result)
            
            selection_result, selection_attempts = await self.execute_with_escalation(
                ProcessingStage.SELECTION,
                select_operation,
                self.config.get("LLM_ROUTES", {}).get("planner", "claude-haiku")
            )
            all_attempts.extend(selection_attempts)
            
            # Stage 4: Workflow building
            logger.info("Starting workflow building stage")
            from .builder import WorkflowBuilder
            builder = WorkflowBuilder(self.ai_agent, self.config)
            
            async def build_operation(*args, model=None, **kwargs):
                return await builder.build_workflow(selection_result)
            
            build_result, build_attempts = await self.execute_with_escalation(
                ProcessingStage.BUILDING,
                build_operation,
                self.config.get("LLM_ROUTES", {}).get("builder", "gpt-4o-mini")
            )
            all_attempts.extend(build_attempts)
            
            # Stage 5: Validation (lightweight, minimal escalation)
            logger.info("Starting workflow validation stage")
            from .validator import WorkflowValidator
            
            n8n_client = N8nClient(self.config)
            validator = WorkflowValidator(n8n_client, self.config)
            
            validation_result = await validator.validate_workflow(build_result)
            
            # If validation fails, attempt fixes
            if not validation_result.get("ok", False):
                logger.warning("Workflow validation failed, attempting fixes")
                
                async def fix_operation(*args, model=None, **kwargs):
                    return await self._attempt_workflow_fixes(build_result, validation_result, model)
                
                try:
                    fixed_result, fix_attempts = await self.execute_with_escalation(
                        ProcessingStage.VALIDATION,
                        fix_operation,
                        self.config.get("LLM_ROUTES", {}).get("controller", "claude-sonnet-4")
                    )
                    all_attempts.extend(fix_attempts)
                    build_result = fixed_result
                except Exception as e:
                    logger.error(f"Workflow fixes failed: {e}")
                    # Continue with original result
            
            # Compile final result
            end_time = time.time()
            total_cost = sum(a.cost_chf for a in all_attempts)
            total_tokens = sum(a.tokens_used for a in all_attempts)
            
            result = {
                "workflow": build_result,
                "plan": plan_result["plan"],
                "selection": selection_result,
                "catalog": catalog_result,
                "validation": validation_result,
                "execution_summary": {
                    "total_time_seconds": end_time - start_time,
                    "total_attempts": len(all_attempts),
                    "total_cost_chf": round(total_cost, 3),
                    "total_tokens": total_tokens,
                    "stages_completed": len(set(a.stage for a in all_attempts)),
                    "escalations": len([a for a in all_attempts if a.attempt > 1])
                },
                "attempts": [asdict(a) for a in all_attempts],
                "status": "success"
            }
            
            logger.info(f"Workflow creation completed in {end_time - start_time:.1f}s, cost: {total_cost:.3f} CHF")
            return result
            
        except Exception as e:
            end_time = time.time()
            logger.error(f"Workflow creation failed: {e}")
            
            return {
                "error": str(e),
                "execution_summary": {
                    "total_time_seconds": end_time - start_time,
                    "total_attempts": len(all_attempts),
                    "total_cost_chf": round(sum(a.cost_chf for a in all_attempts), 3),
                    "total_tokens": sum(a.tokens_used for a in all_attempts),
                    "failed_at_stage": all_attempts[-1].stage.value if all_attempts else "unknown"
                },
                "attempts": [asdict(a) for a in all_attempts],
                "status": "failed"
            }
    
    async def _attempt_workflow_fixes(self, workflow: Dict[str, Any], validation_result: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Attempt to fix workflow validation errors"""
        
        errors = validation_result.get("errors", [])
        if not errors:
            return workflow
        
        fix_prompt = f"""
        Fix the following n8n workflow validation errors:
        
        Workflow:
        {json.dumps(workflow, indent=2)}
        
        Validation Errors:
        {json.dumps(errors, indent=2)}
        
        Provide the corrected workflow as a JSON object.
        Focus only on fixing the validation errors while preserving
        the overall workflow structure and functionality.
        
        Common fixes:
        - Add missing required fields
        - Correct field types and formats
        - Fix node connections
        - Ensure proper parameter structures
        
        Respond with only the corrected JSON workflow.
        """
        
        try:
            response = await self.ai_agent.generate_response(
                fix_prompt,
                role="controller",
                model=model,
                response_format="json",
                max_tokens=3000
            )
            
            import json
            fixed_workflow = json.loads(response)
            
            # Preserve metadata
            fixed_workflow["tokens_used"] = len(response) // 4
            
            return fixed_workflow
            
        except Exception as e:
            logger.error(f"Workflow fix attempt failed: {e}")
            raise Exception(f"Failed to fix workflow: {e}")
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get execution statistics and insights"""
        if not self.execution_history:
            return {"message": "No execution history available"}
        
        # Aggregate statistics
        total_attempts = len(self.execution_history)
        successful_attempts = len([a for a in self.execution_history if a.success])
        
        # By stage
        stage_stats = {}
        for stage in ProcessingStage:
            stage_attempts = [a for a in self.execution_history if a.stage == stage]
            if stage_attempts:
                stage_stats[stage.value] = {
                    "attempts": len(stage_attempts),
                    "success_rate": len([a for a in stage_attempts if a.success]) / len(stage_attempts),
                    "avg_tokens": sum(a.tokens_used for a in stage_attempts) / len(stage_attempts),
                    "total_cost": sum(a.cost_chf for a in stage_attempts)
                }
        
        # Model performance
        model_stats = {}
        for attempt in self.execution_history:
            model = attempt.model
            if model not in model_stats:
                model_stats[model] = {"attempts": 0, "successes": 0, "total_tokens": 0, "total_cost": 0.0}
            
            model_stats[model]["attempts"] += 1
            if attempt.success:
                model_stats[model]["successes"] += 1
            model_stats[model]["total_tokens"] += attempt.tokens_used
            model_stats[model]["total_cost"] += attempt.cost_chf
        
        # Calculate success rates
        for model in model_stats:
            stats = model_stats[model]
            stats["success_rate"] = stats["successes"] / stats["attempts"] if stats["attempts"] > 0 else 0
        
        return {
            "total_attempts": total_attempts,
            "success_rate": successful_attempts / total_attempts if total_attempts > 0 else 0,
            "stage_statistics": stage_stats,
            "model_performance": model_stats,
            "total_cost": sum(a.cost_chf for a in self.execution_history),
            "total_tokens": sum(a.tokens_used for a in self.execution_history)
        }
    
    def reset_execution_history(self):
        """Reset execution history"""
        self.execution_history.clear()
        logger.info("Execution history reset")
