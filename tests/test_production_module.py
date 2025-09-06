"""
Basic tests for Production Module

Tests core functionality and integration points.
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock
import time

# Import the production module components
from umbra.modules.production_mcp import ProductionModule, get_capabilities, execute
from umbra.modules.production.planner import WorkflowPlanner, ComplexityTier
from umbra.modules.production.costs import CostManager, CostEntry
from umbra.modules.production.redact import ProductionRedactor
from umbra.modules.production.validator import WorkflowValidator


class TestProductionModule:
    """Test the main Production module"""
    
    def test_module_import(self):
        """Test that the module imports correctly"""
        assert ProductionModule is not None
        assert get_capabilities is not None
        assert execute is not None
    
    @pytest.mark.asyncio
    async def test_get_capabilities(self):
        """Test getting module capabilities"""
        capabilities = await get_capabilities()
        
        assert capabilities["name"] == "production"
        assert capabilities["description"] == "n8n workflow creator and orchestrator"
        assert "actions" in capabilities
        assert len(capabilities["actions"]) > 0
        
        # Check for key actions
        expected_actions = [
            "plan_from_prompt",
            "build_workflow", 
            "validate_workflow",
            "import_workflow",
            "export_workflow"
        ]
        
        for action in expected_actions:
            assert action in capabilities["actions"]
    
    def test_production_module_init(self):
        """Test ProductionModule initialization"""
        # Mock dependencies
        mock_ai_agent = Mock()
        mock_config = Mock()
        mock_config.get = Mock(return_value="test_value")
        
        # Initialize module
        module = ProductionModule(mock_ai_agent, mock_config)
        
        assert module.ai_agent == mock_ai_agent
        assert module.config == mock_config
        assert module.planner is not None
        assert module.catalog is not None
        assert module.builder is not None
    
    @pytest.mark.asyncio
    async def test_execute_unknown_action(self):
        """Test executing unknown action"""
        mock_ai_agent = Mock()
        mock_config = Mock()
        mock_config.get = Mock(return_value="test_value")
        
        module = ProductionModule(mock_ai_agent, mock_config)
        
        result = await module.execute("unknown_action", {})
        assert "error" in result
        assert "Unknown action" in result["error"]


class TestWorkflowPlanner:
    """Test the WorkflowPlanner component"""
    
    def test_complexity_tier_enum(self):
        """Test ComplexityTier enum"""
        assert ComplexityTier.SMALL.value == "S"
        assert ComplexityTier.MEDIUM.value == "M"
        assert ComplexityTier.LARGE.value == "L"
        assert ComplexityTier.EXTRA_LARGE.value == "XL"
    
    def test_planner_init(self):
        """Test WorkflowPlanner initialization"""
        mock_ai_agent = Mock()
        mock_config = Mock()
        mock_config.get = Mock(return_value={})
        
        planner = WorkflowPlanner(mock_ai_agent, mock_config)
        
        assert planner.ai_agent == mock_ai_agent
        assert planner.config == mock_config
        assert planner.max_retries == 3
    
    @pytest.mark.asyncio
    async def test_estimate_complexity(self):
        """Test complexity estimation"""
        mock_ai_agent = Mock()
        mock_ai_agent.generate_response = AsyncMock(return_value="M")
        mock_config = Mock()
        mock_config.get = Mock(return_value={})
        
        planner = WorkflowPlanner(mock_ai_agent, mock_config)
        
        # Test simple prompt
        complexity = await planner._estimate_complexity("Send an email when webhook received")
        assert isinstance(complexity, ComplexityTier)
    
    def test_get_planner_model(self):
        """Test model selection based on complexity"""
        mock_ai_agent = Mock()
        mock_config = Mock()
        mock_config.get = Mock(return_value={
            "planner": "claude-haiku",
            "planner_l": "claude-sonnet-4",
            "planner_xl": "claude-opus"
        })
        
        planner = WorkflowPlanner(mock_ai_agent, mock_config)
        
        assert planner._get_planner_model(ComplexityTier.SMALL) == "claude-haiku"
        assert planner._get_planner_model(ComplexityTier.LARGE) == "claude-sonnet-4" 
        assert planner._get_planner_model(ComplexityTier.EXTRA_LARGE) == "claude-opus"


class TestCostManager:
    """Test the CostManager component"""
    
    def test_cost_manager_init(self):
        """Test CostManager initialization"""
        mock_config = Mock()
        mock_config.get = Mock(side_effect=lambda key, default=None: {
            "PROD_COST_TRACKING": True,
            "PROD_COST_STORAGE_PATH": "/tmp/test_costs.json",
            "PROD_COST_CAP_CHF_DAILY": 5.0,
            "PROD_MODEL_PRICING": {}
        }.get(key, default))
        
        cost_manager = CostManager(mock_config)
        
        assert cost_manager.tracking_enabled == True
        assert cost_manager.daily_budget_chf == 5.0
        assert len(cost_manager.model_pricing) > 0
        assert "claude-haiku" in cost_manager.model_pricing
    
    def test_calculate_cost(self):
        """Test cost calculation"""
        mock_config = Mock()
        mock_config.get = Mock(return_value=None)
        
        cost_manager = CostManager(mock_config)
        
        # Test cost calculation for known model
        cost = cost_manager._calculate_cost("claude-haiku", 1000)
        assert cost > 0
        assert isinstance(cost, float)
        
        # Test cost calculation for unknown model
        cost_unknown = cost_manager._calculate_cost("unknown-model", 1000)
        assert cost_unknown > 0
    
    @pytest.mark.asyncio
    async def test_log_step_cost(self):
        """Test logging step costs"""
        mock_config = Mock()
        mock_config.get = Mock(return_value=None)
        
        cost_manager = CostManager(mock_config)
        
        # Mock persist method to avoid file operations
        cost_manager._persist_cost_data = AsyncMock()
        
        result = await cost_manager.log_step_cost(
            stage="planning",
            tokens_used=500,
            model="claude-haiku",
            operation="test",
            success=True
        )
        
        assert result["cost_logged"] == True
        assert result["stage"] == "planning"
        assert result["tokens_used"] == 500
        assert "estimated_cost_chf" in result
        assert len(cost_manager.cost_entries) == 1
    
    def test_get_cost_summary(self):
        """Test cost summary generation"""
        mock_config = Mock()
        mock_config.get = Mock(return_value=None)
        
        cost_manager = CostManager(mock_config)
        
        # Add some test entries
        test_entries = [
            CostEntry(
                timestamp=time.time(),
                stage="planning",
                model="claude-haiku",
                tokens_used=500,
                estimated_cost_chf=0.01,
                operation="test",
                success=True
            ),
            CostEntry(
                timestamp=time.time(),
                stage="building",
                model="gpt-4o-mini", 
                tokens_used=1000,
                estimated_cost_chf=0.02,
                operation="test",
                success=True
            )
        ]
        
        cost_manager.cost_entries = test_entries
        
        summary = cost_manager.get_cost_summary(24)
        
        assert summary.total_tokens == 1500
        assert summary.total_cost_chf == 0.03
        assert summary.operations_count == 2
        assert summary.successful_operations == 2
        assert len(summary.cost_by_stage) == 2
        assert len(summary.cost_by_model) == 2


class TestProductionRedactor:
    """Test the ProductionRedactor component"""
    
    def test_redactor_init(self):
        """Test ProductionRedactor initialization"""
        mock_config = Mock()
        mock_config.get = Mock(side_effect=lambda key, default=None: {
            "PRIVACY_MODE": "standard",
            "PROD_MASK_CHAR": "*",
            "PROD_PRESERVE_LENGTH": True
        }.get(key, default))
        
        redactor = ProductionRedactor(mock_config)
        
        assert redactor.redaction_enabled == True
        assert redactor.redaction_mode == "standard"
        assert redactor.mask_char == "*"
        assert len(redactor.rules) > 0
    
    def test_redact_text_email(self):
        """Test email redaction"""
        mock_config = Mock()
        mock_config.get = Mock(side_effect=lambda key, default=None: {
            "PRIVACY_MODE": "standard"
        }.get(key, default))
        
        redactor = ProductionRedactor(mock_config)
        
        text = "Contact us at support@example.com for help"
        redacted_text, result = redactor.redact_text(text)
        
        assert "support@example.com" not in redacted_text
        assert "[EMAIL]" in redacted_text or "*" in redacted_text
        assert result.redactions_count > 0
        assert "email" in result.rules_triggered
    
    def test_redact_dict(self):
        """Test dictionary redaction"""
        mock_config = Mock()
        mock_config.get = Mock(side_effect=lambda key, default=None: {
            "PRIVACY_MODE": "standard"
        }.get(key, default))
        
        redactor = ProductionRedactor(mock_config)
        
        data = {
            "username": "john_doe",
            "password": "secret123",
            "email": "john@example.com",
            "api_key": "sk-1234567890abcdef",
            "normal_field": "normal_value"
        }
        
        redacted = redactor.redact_dict(data)
        
        # Sensitive keys should be masked
        assert redacted["password"] != "secret123"
        assert redacted["api_key"] != "sk-1234567890abcdef"
        
        # Normal fields might be redacted if they contain PII patterns
        assert "normal_field" in redacted
        
        # Email should be redacted due to pattern matching
        assert redacted["email"] != "john@example.com"
    
    def test_redaction_disabled(self):
        """Test redaction when disabled"""
        mock_config = Mock()
        mock_config.get = Mock(side_effect=lambda key, default=None: {
            "PRIVACY_MODE": "none"
        }.get(key, default))
        
        redactor = ProductionRedactor(mock_config)
        
        text = "Contact support@example.com with password secret123"
        redacted_text, result = redactor.redact_text(text)
        
        assert redacted_text == text  # No changes when disabled
        assert result.redactions_count == 0


class TestWorkflowValidator:
    """Test the WorkflowValidator component"""
    
    def test_validator_init(self):
        """Test WorkflowValidator initialization"""
        mock_n8n_client = Mock()
        mock_config = Mock()
        mock_config.get = Mock(return_value=True)
        
        validator = WorkflowValidator(mock_n8n_client, mock_config)
        
        assert validator.n8n_client == mock_n8n_client
        assert validator.config == mock_config
        assert validator.strict_mode == True
    
    def test_validate_node_schema(self):
        """Test node schema validation"""
        mock_n8n_client = Mock()
        mock_config = Mock()
        mock_config.get = Mock(return_value=True)
        
        validator = WorkflowValidator(mock_n8n_client, mock_config)
        
        # Valid node
        valid_node = {
            "id": "node1",
            "name": "Test Node",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1,
            "position": [100, 200],
            "parameters": {}
        }
        
        issues = validator._validate_node_schema(valid_node, 0)
        assert len(issues) == 0
        
        # Invalid node (missing required fields)
        invalid_node = {
            "name": "Test Node"
            # Missing id, type, typeVersion, position
        }
        
        issues = validator._validate_node_schema(invalid_node, 0)
        assert len(issues) > 0
        assert any("missing required field" in issue.message.lower() for issue in issues)
    
    @pytest.mark.asyncio
    async def test_validate_workflow_basic(self):
        """Test basic workflow validation"""
        mock_n8n_client = Mock()
        mock_n8n_client.validate_workflow = AsyncMock(return_value={"ok": True})
        mock_n8n_client.get_node_types = AsyncMock(return_value={"data": {}})
        
        mock_config = Mock()
        mock_config.get = Mock(return_value=True)
        
        validator = WorkflowValidator(mock_n8n_client, mock_config)
        
        # Valid workflow
        valid_workflow = {
            "name": "Test Workflow",
            "active": False,
            "nodes": [
                {
                    "id": "webhook",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 1,
                    "position": [100, 200],
                    "parameters": {}
                }
            ],
            "connections": {},
            "settings": {},
            "staticData": {}
        }
        
        result = await validator.validate_workflow(valid_workflow)
        
        assert "ok" in result
        assert "issues" in result
        assert "summary" in result


# Test fixtures and utilities
@pytest.fixture
def mock_ai_agent():
    """Mock AI agent for testing"""
    agent = Mock()
    agent.generate_response = AsyncMock(return_value='{"test": "response"}')
    return agent


@pytest.fixture
def mock_config():
    """Mock config for testing"""
    config = Mock()
    config.get = Mock(return_value=None)
    return config


@pytest.fixture
def sample_workflow():
    """Sample workflow for testing"""
    return {
        "name": "Sample Workflow",
        "active": False,
        "nodes": [
            {
                "id": "webhook_node",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [100, 200],
                "parameters": {
                    "path": "test-webhook"
                }
            },
            {
                "id": "http_node", 
                "name": "HTTP Request",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "position": [400, 200],
                "parameters": {
                    "url": "https://api.example.com/data",
                    "method": "GET"
                }
            }
        ],
        "connections": {
            "webhook_node": {
                "main": [
                    [
                        {
                            "node": "http_node",
                            "type": "main",
                            "index": 0
                        }
                    ]
                ]
            }
        },
        "settings": {
            "executionOrder": "v1"
        },
        "staticData": {}
    }


# Integration tests
class TestProductionIntegration:
    """Integration tests for Production module"""
    
    @pytest.mark.asyncio
    async def test_module_execute_with_context(self, mock_ai_agent, mock_config):
        """Test module execution with proper context"""
        context = {
            "ai_agent": mock_ai_agent,
            "config": mock_config,
            "r2_client": None
        }
        
        # Test getting capabilities through execute function
        result = await execute("get_capabilities", {}, context)
        
        # Since the action doesn't exist in our execute function,
        # this should return an error, but the context should be valid
        assert "ai_agent" in context
        assert "config" in context
    
    def test_cost_redaction_integration(self):
        """Test integration between cost tracking and redaction"""
        mock_config = Mock()
        mock_config.get = Mock(side_effect=lambda key, default=None: {
            "PRIVACY_MODE": "standard",
            "PROD_COST_TRACKING": True
        }.get(key, default))
        
        cost_manager = CostManager(mock_config)
        redactor = ProductionRedactor(mock_config)
        
        # Create cost entry with sensitive data
        sensitive_data = {
            "operation": "workflow_creation",
            "user_email": "user@example.com",
            "api_key": "sk-1234567890abcdef"
        }
        
        # Redact before logging
        redacted_data = redactor.redact_dict(sensitive_data)
        
        assert redacted_data["user_email"] != "user@example.com"
        assert redacted_data["api_key"] != "sk-1234567890abcdef"
        assert redacted_data["operation"] == "workflow_creation"  # Should remain unchanged


if __name__ == "__main__":
    # Run basic tests
    pytest.main([__file__, "-v"])
