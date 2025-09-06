"""
Cost Manager for Production Module

Tracks token usage, cost estimation, and budget management for
AI-powered workflow creation processes.
"""

import time
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import os

from ...core.config import UmbraConfig

logger = logging.getLogger(__name__)

@dataclass
class CostEntry:
    """Individual cost tracking entry"""
    timestamp: float
    stage: str  # planning, selection, building, validation, testing
    model: str
    tokens_used: int
    estimated_cost_chf: float
    operation: str  # specific operation performed
    success: bool
    execution_time_ms: Optional[int] = None

@dataclass
class BudgetLimit:
    """Budget limit configuration"""
    name: str
    limit_chf: float
    period: str  # "daily", "weekly", "monthly"
    scope: str  # "total", "per_workflow", "per_user"
    enabled: bool = True

@dataclass
class CostSummary:
    """Cost summary for a period"""
    period_start: float
    period_end: float
    total_tokens: int
    total_cost_chf: float
    operations_count: int
    successful_operations: int
    cost_by_stage: Dict[str, float]
    cost_by_model: Dict[str, float]
    average_cost_per_operation: float

class CostManager:
    """Manages cost tracking and budget limits for production operations"""
    
    def __init__(self, config: UmbraConfig):
        self.config = config
        
        # Cost tracking settings
        self.tracking_enabled = config.get("PROD_COST_TRACKING", True)
        self.storage_path = config.get("PROD_COST_STORAGE_PATH", "/tmp/umbra_costs.json")
        
        # Budget limits
        self.daily_budget_chf = config.get("PROD_COST_CAP_CHF_DAILY", 10.0)
        self.per_workflow_budget_chf = config.get("PROD_COST_CAP_CHF_PER_WORKFLOW", 1.0)
        self.token_cap_per_step = config.get("PROD_TOKEN_CAP_PER_STEP", 5000)
        
        # Model pricing (CHF per 1K tokens)
        self.model_pricing = self._load_model_pricing()
        
        # Cost entries storage
        self.cost_entries: List[CostEntry] = []
        self.budget_limits: List[BudgetLimit] = []
        
        # Initialize
        self._initialize_cost_tracking()
        self._load_budget_limits()
        
        logger.info("Cost manager initialized")
    
    def _load_model_pricing(self) -> Dict[str, Dict[str, float]]:
        """Load model pricing information"""
        # Default pricing in CHF per 1K tokens (approximate)
        default_pricing = {
            "claude-haiku": {"input": 0.0005, "output": 0.0015},
            "claude-sonnet-4": {"input": 0.006, "output": 0.024},
            "claude-opus": {"input": 0.030, "output": 0.120},
            "gpt-4o-mini": {"input": 0.0003, "output": 0.0012},
            "gpt-4o": {"input": 0.010, "output": 0.030},
            "gpt-4": {"input": 0.060, "output": 0.120}
        }
        
        # Override with config if available
        config_pricing = self.config.get("PROD_MODEL_PRICING", {})
        default_pricing.update(config_pricing)
        
        return default_pricing
    
    def _initialize_cost_tracking(self):
        """Initialize cost tracking system"""
        if not self.tracking_enabled:
            return
        
        # Load existing cost data if available
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    
                # Load cost entries
                entries_data = data.get("cost_entries", [])
                self.cost_entries = [
                    CostEntry(**entry) for entry in entries_data
                ]
                
                logger.info(f"Loaded {len(self.cost_entries)} existing cost entries")
        except Exception as e:
            logger.warning(f"Failed to load existing cost data: {e}")
    
    def _load_budget_limits(self):
        """Load budget limit configurations"""
        # Default budget limits
        default_limits = [
            BudgetLimit(
                name="daily_total",
                limit_chf=self.daily_budget_chf,
                period="daily",
                scope="total",
                enabled=True
            ),
            BudgetLimit(
                name="per_workflow",
                limit_chf=self.per_workflow_budget_chf,
                period="session",
                scope="per_workflow",
                enabled=True
            )
        ]
        
        # Load custom limits from config
        custom_limits = self.config.get("PROD_BUDGET_LIMITS", [])
        for limit_config in custom_limits:
            try:
                limit = BudgetLimit(**limit_config)
                default_limits.append(limit)
            except Exception as e:
                logger.warning(f"Invalid budget limit configuration: {e}")
        
        self.budget_limits = default_limits
    
    async def log_step_cost(self, stage: str, tokens_used: int, model: str = "unknown", operation: str = "unknown", success: bool = True, execution_time_ms: Optional[int] = None) -> Dict[str, Any]:
        """Log cost for a workflow creation step"""
        if not self.tracking_enabled:
            return {"cost_logged": False, "reason": "tracking_disabled"}
        
        # Calculate cost
        estimated_cost = self._calculate_cost(model, tokens_used)
        
        # Create cost entry
        entry = CostEntry(
            timestamp=time.time(),
            stage=stage,
            model=model,
            tokens_used=tokens_used,
            estimated_cost_chf=estimated_cost,
            operation=operation,
            success=success,
            execution_time_ms=execution_time_ms
        )
        
        # Add to tracking
        self.cost_entries.append(entry)
        
        # Check budget limits
        budget_status = await self._check_budget_limits(entry)
        
        # Persist data
        await self._persist_cost_data()
        
        logger.debug(f"Logged cost: {stage} - {tokens_used} tokens - {estimated_cost:.4f} CHF")
        
        return {
            "cost_logged": True,
            "stage": stage,
            "tokens_used": tokens_used,
            "estimated_cost_chf": estimated_cost,
            "budget_status": budget_status,
            "total_daily_cost": self._get_daily_cost(),
            "remaining_daily_budget": max(0, self.daily_budget_chf - self._get_daily_cost())
        }
    
    def _calculate_cost(self, model: str, tokens_used: int, input_ratio: float = 0.7) -> float:
        """Calculate cost for tokens and model"""
        if model not in self.model_pricing:
            # Use average pricing for unknown models
            avg_input = sum(p["input"] for p in self.model_pricing.values()) / len(self.model_pricing)
            avg_output = sum(p["output"] for p in self.model_pricing.values()) / len(self.model_pricing)
            pricing = {"input": avg_input, "output": avg_output}
        else:
            pricing = self.model_pricing[model]
        
        # Estimate input/output split
        input_tokens = int(tokens_used * input_ratio)
        output_tokens = tokens_used - input_tokens
        
        # Calculate cost per 1K tokens
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    async def _check_budget_limits(self, entry: CostEntry) -> Dict[str, Any]:
        """Check if entry violates any budget limits"""
        violations = []
        warnings = []
        
        for limit in self.budget_limits:
            if not limit.enabled:
                continue
            
            current_usage = self._calculate_usage_for_limit(limit)
            new_usage = current_usage + entry.estimated_cost_chf
            
            if new_usage > limit.limit_chf:
                violations.append({
                    "limit_name": limit.name,
                    "limit_chf": limit.limit_chf,
                    "current_usage": current_usage,
                    "new_usage": new_usage,
                    "overage": new_usage - limit.limit_chf
                })
            elif new_usage > limit.limit_chf * 0.8:  # 80% warning threshold
                warnings.append({
                    "limit_name": limit.name,
                    "limit_chf": limit.limit_chf,
                    "current_usage": current_usage,
                    "usage_percentage": (new_usage / limit.limit_chf) * 100
                })
        
        return {
            "violations": violations,
            "warnings": warnings,
            "within_budget": len(violations) == 0
        }
    
    def _calculate_usage_for_limit(self, limit: BudgetLimit) -> float:
        """Calculate current usage for a specific budget limit"""
        now = time.time()
        
        # Determine time window
        if limit.period == "daily":
            start_time = now - (24 * 60 * 60)  # 24 hours ago
        elif limit.period == "weekly":
            start_time = now - (7 * 24 * 60 * 60)  # 7 days ago
        elif limit.period == "monthly":
            start_time = now - (30 * 24 * 60 * 60)  # 30 days ago
        else:  # session or other
            start_time = 0  # All time
        
        # Filter entries by time window
        relevant_entries = [
            entry for entry in self.cost_entries
            if entry.timestamp >= start_time
        ]
        
        # Calculate usage based on scope
        if limit.scope == "total":
            return sum(entry.estimated_cost_chf for entry in relevant_entries)
        elif limit.scope == "per_workflow":
            # For per-workflow limits, we need to group by workflow session
            # This is simplified - in practice, you'd track workflow sessions
            return sum(entry.estimated_cost_chf for entry in relevant_entries)
        else:
            return 0.0
    
    def _get_daily_cost(self) -> float:
        """Get total cost for current day"""
        now = time.time()
        start_of_day = now - (24 * 60 * 60)
        
        daily_entries = [
            entry for entry in self.cost_entries
            if entry.timestamp >= start_of_day
        ]
        
        return sum(entry.estimated_cost_chf for entry in daily_entries)
    
    async def _persist_cost_data(self):
        """Persist cost data to storage"""
        if not self.tracking_enabled:
            return
        
        try:
            # Limit stored entries to recent data (last 30 days)
            cutoff_time = time.time() - (30 * 24 * 60 * 60)
            recent_entries = [
                entry for entry in self.cost_entries
                if entry.timestamp >= cutoff_time
            ]
            
            data = {
                "cost_entries": [asdict(entry) for entry in recent_entries],
                "last_updated": time.time(),
                "version": "1.0"
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Write to temporary file first, then rename (atomic operation)
            temp_path = f"{self.storage_path}.tmp"
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            os.rename(temp_path, self.storage_path)
            
            # Update in-memory data
            self.cost_entries = recent_entries
            
        except Exception as e:
            logger.error(f"Failed to persist cost data: {e}")
    
    def get_cost_summary(self, period_hours: int = 24) -> CostSummary:
        """Get cost summary for specified period"""
        now = time.time()
        start_time = now - (period_hours * 60 * 60)
        
        # Filter entries for period
        period_entries = [
            entry for entry in self.cost_entries
            if entry.timestamp >= start_time
        ]
        
        if not period_entries:
            return CostSummary(
                period_start=start_time,
                period_end=now,
                total_tokens=0,
                total_cost_chf=0.0,
                operations_count=0,
                successful_operations=0,
                cost_by_stage={},
                cost_by_model={},
                average_cost_per_operation=0.0
            )
        
        # Calculate aggregates
        total_tokens = sum(entry.tokens_used for entry in period_entries)
        total_cost = sum(entry.estimated_cost_chf for entry in period_entries)
        operations_count = len(period_entries)
        successful_operations = len([e for e in period_entries if e.success])
        
        # Group by stage
        cost_by_stage = {}
        for entry in period_entries:
            stage = entry.stage
            cost_by_stage[stage] = cost_by_stage.get(stage, 0.0) + entry.estimated_cost_chf
        
        # Group by model
        cost_by_model = {}
        for entry in period_entries:
            model = entry.model
            cost_by_model[model] = cost_by_model.get(model, 0.0) + entry.estimated_cost_chf
        
        return CostSummary(
            period_start=start_time,
            period_end=now,
            total_tokens=total_tokens,
            total_cost_chf=total_cost,
            operations_count=operations_count,
            successful_operations=successful_operations,
            cost_by_stage=cost_by_stage,
            cost_by_model=cost_by_model,
            average_cost_per_operation=total_cost / operations_count if operations_count > 0 else 0.0
        )
    
    def check_workflow_budget(self, estimated_tokens: int, estimated_stages: int = 5) -> Dict[str, Any]:
        """Check if workflow creation would exceed budget"""
        # Estimate total cost for workflow
        avg_model_cost = sum(
            (pricing["input"] + pricing["output"]) / 2 
            for pricing in self.model_pricing.values()
        ) / len(self.model_pricing)
        
        estimated_cost = (estimated_tokens / 1000) * avg_model_cost * estimated_stages
        
        # Check against per-workflow budget
        per_workflow_limit = self.per_workflow_budget_chf
        within_workflow_budget = estimated_cost <= per_workflow_limit
        
        # Check against daily budget
        daily_used = self._get_daily_cost()
        daily_remaining = self.daily_budget_chf - daily_used
        within_daily_budget = estimated_cost <= daily_remaining
        
        return {
            "estimated_cost_chf": estimated_cost,
            "estimated_tokens": estimated_tokens,
            "estimated_stages": estimated_stages,
            "within_workflow_budget": within_workflow_budget,
            "workflow_budget_chf": per_workflow_limit,
            "within_daily_budget": within_daily_budget,
            "daily_budget_chf": self.daily_budget_chf,
            "daily_used_chf": daily_used,
            "daily_remaining_chf": daily_remaining,
            "budget_approved": within_workflow_budget and within_daily_budget,
            "warnings": self._generate_budget_warnings(estimated_cost, daily_used, daily_remaining)
        }
    
    def _generate_budget_warnings(self, estimated_cost: float, daily_used: float, daily_remaining: float) -> List[str]:
        """Generate budget-related warnings"""
        warnings = []
        
        if estimated_cost > self.per_workflow_budget_chf * 0.8:
            warnings.append(f"Workflow cost approaching per-workflow limit ({estimated_cost:.3f} CHF)")
        
        if daily_used > self.daily_budget_chf * 0.8:
            warnings.append(f"Daily budget usage above 80% ({daily_used:.3f} CHF)")
        
        if estimated_cost > daily_remaining:
            warnings.append("Workflow cost exceeds remaining daily budget")
        
        if len(self.cost_entries) > 1000:  # Large number of operations
            recent_cost = sum(
                entry.estimated_cost_chf for entry in self.cost_entries[-10:]
            )
            if recent_cost > 0.5:  # High recent activity
                warnings.append("High recent activity - monitor costs closely")
        
        return warnings
    
    def get_cost_breakdown(self, group_by: str = "stage") -> Dict[str, Any]:
        """Get detailed cost breakdown"""
        if group_by not in ["stage", "model", "operation", "day"]:
            raise ValueError("group_by must be one of: stage, model, operation, day")
        
        breakdown = {}
        
        for entry in self.cost_entries:
            if group_by == "stage":
                key = entry.stage
            elif group_by == "model":
                key = entry.model
            elif group_by == "operation":
                key = entry.operation
            elif group_by == "day":
                date = datetime.fromtimestamp(entry.timestamp)
                key = date.strftime("%Y-%m-%d")
            
            if key not in breakdown:
                breakdown[key] = {
                    "total_cost_chf": 0.0,
                    "total_tokens": 0,
                    "operations_count": 0,
                    "successful_operations": 0,
                    "average_cost": 0.0,
                    "first_seen": entry.timestamp,
                    "last_seen": entry.timestamp
                }
            
            breakdown[key]["total_cost_chf"] += entry.estimated_cost_chf
            breakdown[key]["total_tokens"] += entry.tokens_used
            breakdown[key]["operations_count"] += 1
            if entry.success:
                breakdown[key]["successful_operations"] += 1
            
            breakdown[key]["last_seen"] = max(breakdown[key]["last_seen"], entry.timestamp)
            breakdown[key]["first_seen"] = min(breakdown[key]["first_seen"], entry.timestamp)
        
        # Calculate averages
        for key, data in breakdown.items():
            if data["operations_count"] > 0:
                data["average_cost"] = data["total_cost_chf"] / data["operations_count"]
        
        # Sort by total cost descending
        sorted_breakdown = dict(
            sorted(breakdown.items(), key=lambda x: x[1]["total_cost_chf"], reverse=True)
        )
        
        return {
            "group_by": group_by,
            "breakdown": sorted_breakdown,
            "total_categories": len(sorted_breakdown),
            "summary": {
                "total_cost": sum(data["total_cost_chf"] for data in breakdown.values()),
                "total_tokens": sum(data["total_tokens"] for data in breakdown.values()),
                "total_operations": sum(data["operations_count"] for data in breakdown.values())
            }
        }
    
    def optimize_cost_settings(self) -> Dict[str, Any]:
        """Analyze usage patterns and suggest cost optimizations"""
        if len(self.cost_entries) < 10:
            return {"message": "Insufficient data for optimization analysis"}
        
        recent_entries = self.cost_entries[-50:]  # Last 50 operations
        
        # Analyze model usage efficiency
        model_efficiency = {}
        for entry in recent_entries:
            model = entry.model
            if model not in model_efficiency:
                model_efficiency[model] = {
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "operations": 0,
                    "success_rate": 0.0,
                    "avg_cost_per_token": 0.0
                }
            
            model_efficiency[model]["total_cost"] += entry.estimated_cost_chf
            model_efficiency[model]["total_tokens"] += entry.tokens_used
            model_efficiency[model]["operations"] += 1
            model_efficiency[model]["success_rate"] += (1 if entry.success else 0)
        
        # Calculate efficiency metrics
        for model, data in model_efficiency.items():
            if data["operations"] > 0:
                data["success_rate"] /= data["operations"]
                data["avg_cost_per_token"] = data["total_cost"] / data["total_tokens"] if data["total_tokens"] > 0 else 0
        
        # Generate recommendations
        recommendations = []
        
        # Find most expensive models
        expensive_models = sorted(
            model_efficiency.items(),
            key=lambda x: x[1]["avg_cost_per_token"],
            reverse=True
        )
        
        if expensive_models:
            most_expensive = expensive_models[0]
            if most_expensive[1]["avg_cost_per_token"] > 0.01:  # 0.01 CHF per token threshold
                recommendations.append(
                    f"Consider reducing usage of {most_expensive[0]} - high cost per token ({most_expensive[1]['avg_cost_per_token']:.4f} CHF)"
                )
        
        # Find models with low success rates
        for model, data in model_efficiency.items():
            if data["success_rate"] < 0.8 and data["operations"] >= 5:
                recommendations.append(
                    f"Model {model} has low success rate ({data['success_rate']:.1%}) - consider reviewing prompts or switching models"
                )
        
        # Analyze stage costs
        stage_costs = {}
        for entry in recent_entries:
            stage = entry.stage
            stage_costs[stage] = stage_costs.get(stage, 0.0) + entry.estimated_cost_chf
        
        if stage_costs:
            most_expensive_stage = max(stage_costs.items(), key=lambda x: x[1])
            if most_expensive_stage[1] > sum(stage_costs.values()) * 0.5:  # More than 50% of total cost
                recommendations.append(
                    f"Stage '{most_expensive_stage[0]}' accounts for most costs - consider optimization"
                )
        
        return {
            "model_efficiency": model_efficiency,
            "stage_costs": stage_costs,
            "recommendations": recommendations,
            "cost_trend": self._calculate_cost_trend(),
            "budget_utilization": {
                "daily_usage_percent": (self._get_daily_cost() / self.daily_budget_chf) * 100,
                "projected_monthly": self._get_daily_cost() * 30
            }
        }
    
    def _calculate_cost_trend(self) -> Dict[str, Any]:
        """Calculate cost trend over time"""
        if len(self.cost_entries) < 20:
            return {"trend": "insufficient_data"}
        
        # Split entries into two halves for comparison
        mid_point = len(self.cost_entries) // 2
        first_half = self.cost_entries[:mid_point]
        second_half = self.cost_entries[mid_point:]
        
        first_half_avg = sum(e.estimated_cost_chf for e in first_half) / len(first_half)
        second_half_avg = sum(e.estimated_cost_chf for e in second_half) / len(second_half)
        
        if second_half_avg > first_half_avg * 1.2:
            trend = "increasing"
        elif second_half_avg < first_half_avg * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "first_half_avg": first_half_avg,
            "second_half_avg": second_half_avg,
            "change_percent": ((second_half_avg - first_half_avg) / first_half_avg) * 100 if first_half_avg > 0 else 0
        }
    
    def export_cost_data(self, format: str = "json") -> Dict[str, Any]:
        """Export cost data for analysis"""
        if format not in ["json", "csv"]:
            raise ValueError("Format must be 'json' or 'csv'")
        
        data = {
            "export_timestamp": time.time(),
            "total_entries": len(self.cost_entries),
            "cost_entries": [asdict(entry) for entry in self.cost_entries],
            "summary": asdict(self.get_cost_summary(24 * 7)),  # Weekly summary
            "model_pricing": self.model_pricing,
            "budget_limits": [asdict(limit) for limit in self.budget_limits]
        }
        
        if format == "json":
            return {
                "format": "json",
                "data": data,
                "size": len(json.dumps(data))
            }
        elif format == "csv":
            # Convert to CSV format
            import io
            import csv
            
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            
            # Write header
            writer.writerow([
                "timestamp", "stage", "model", "tokens_used", 
                "estimated_cost_chf", "operation", "success", "execution_time_ms"
            ])
            
            # Write data
            for entry in self.cost_entries:
                writer.writerow([
                    entry.timestamp, entry.stage, entry.model, entry.tokens_used,
                    entry.estimated_cost_chf, entry.operation, entry.success, entry.execution_time_ms
                ])
            
            return {
                "format": "csv",
                "data": csv_buffer.getvalue(),
                "size": len(csv_buffer.getvalue())
            }
    
    def reset_cost_data(self, confirm: bool = False) -> Dict[str, Any]:
        """Reset all cost tracking data"""
        if not confirm:
            return {
                "action": "reset_cost_data",
                "status": "confirmation_required",
                "message": "Set confirm=True to proceed with data reset"
            }
        
        # Backup current data
        backup_data = {
            "reset_timestamp": time.time(),
            "entries_count": len(self.cost_entries),
            "total_cost": sum(e.estimated_cost_chf for e in self.cost_entries)
        }
        
        # Clear data
        self.cost_entries.clear()
        
        # Persist empty state
        try:
            if os.path.exists(self.storage_path):
                backup_path = f"{self.storage_path}.backup.{int(time.time())}"
                os.rename(self.storage_path, backup_path)
                logger.info(f"Backed up cost data to {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to backup cost data: {e}")
        
        return {
            "action": "reset_cost_data",
            "status": "completed",
            "backup_info": backup_data
        }
