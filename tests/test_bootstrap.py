"""
Bootstrap/smoke tests for Umbra Bot Phase 1.

These tests verify that the basic bot infrastructure works without
requiring external dependencies like Telegram tokens or API keys.
"""

import os
import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime

# Import the components we want to test
from umbra import UmbraBot, UmbraConfig, InternalEnvelope, ModuleBase
from umbra.core.feature_flags import is_enabled, get_enabled_features
from umbra.core.logger import get_logger
from umbra.modules.finance import FinanceModule
from umbra.modules.monitoring import MonitoringModule


class TestBootstrap:
    """Basic bootstrap tests to verify core functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        # Set required environment variables for testing
        os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:test_token_for_testing"
        os.environ["ALLOWED_USER_IDS"] = "123456789,987654321"
        os.environ["LOG_LEVEL"] = "DEBUG"
    
    def teardown_method(self):
        """Cleanup test environment."""
        # Clean up environment variables
        test_vars = [
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_IDS", 
            "LOG_LEVEL"
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
    
    def test_config_loading(self):
        """Test that configuration loads correctly."""
        config = UmbraConfig()
        
        assert config.telegram_bot_token == "123456789:test_token_for_testing"
        assert "123456789" in config.allowed_user_ids
        assert "987654321" in config.allowed_user_ids
        assert config.log_level == "DEBUG"
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Test missing required fields
        del os.environ["TELEGRAM_BOT_TOKEN"]
        
        with pytest.raises(Exception):
            UmbraConfig()
    
    def test_feature_flags(self):
        """Test feature flag system."""
        # Test default flags
        assert is_enabled("finance_ocr_enabled") == True
        assert is_enabled("ai_integration_enabled") == False
        assert is_enabled("metrics_collection_enabled") == True
        
        # Test unknown flag
        assert is_enabled("unknown_flag") == False
        assert is_enabled("unknown_flag", default=True) == True
        
        # Test getting all features
        features = get_enabled_features()
        assert isinstance(features, dict)
        assert "finance_ocr_enabled" in features
    
    def test_logger_creation(self):
        """Test logger creation and basic functionality."""
        logger = get_logger("test_logger")
        
        assert logger is not None
        assert logger.name == "test_logger"
        
        # Test logging methods exist
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "debug")
    
    def test_envelope_creation(self):
        """Test internal envelope creation and functionality."""
        envelope = InternalEnvelope(
            user_id="123456789",
            action="test_action",
            data={"test": "data"}
        )
        
        assert envelope.user_id == "123456789"
        assert envelope.action == "test_action"
        assert envelope.data["test"] == "data"
        assert envelope.req_id is not None
        assert envelope.correlation_id is not None
        assert "created" in envelope.timestamps
        
        # Test envelope methods
        envelope.mark_received("test_module")
        envelope.mark_processed("test_module")
        
        assert f"received_by_test_module" in envelope.timestamps
        assert f"processed_by_test_module" in envelope.timestamps
        
        duration = envelope.get_processing_duration("test_module")
        assert duration is not None
        assert duration >= 0
    
    @pytest.mark.asyncio
    async def test_finance_module_initialization(self):
        """Test finance module can be created and initialized."""
        module = FinanceModule()
        
        assert module.name == "finance"
        assert isinstance(module, ModuleBase)
        
        # Test initialization (should succeed even without OCR dependencies)
        result = await module._initialize_wrapper()
        assert result == True
        assert module.is_initialized == True
        
        # Test handler registration
        handlers = await module._register_handlers_wrapper()
        assert isinstance(handlers, dict)
        assert len(handlers) > 0
        assert "receipt" in handlers
        assert "finance help" in handlers
        
        # Test health check
        health = await module._health_check_wrapper()
        assert isinstance(health, dict)
        assert "status" in health
        assert "module" in health
        
        # Test cleanup
        await module._shutdown_wrapper()
    
    @pytest.mark.asyncio
    async def test_monitoring_module_initialization(self):
        """Test monitoring module can be created and initialized."""
        module = MonitoringModule()
        
        assert module.name == "monitoring"
        assert isinstance(module, ModuleBase)
        
        # Test initialization
        result = await module._initialize_wrapper()
        assert result == True
        assert module.is_initialized == True
        
        # Test handler registration
        handlers = await module._register_handlers_wrapper()
        assert isinstance(handlers, dict)
        assert len(handlers) > 0
        assert "health" in handlers
        assert "status" in handlers
        
        # Test health check
        health = await module._health_check_wrapper()
        assert isinstance(health, dict)
        assert "status" in health
        assert health["status"] in ["healthy", "degraded"]
        
        # Test cleanup
        await module._shutdown_wrapper()
    
    @pytest.mark.asyncio
    async def test_module_command_matching(self):
        """Test module command matching functionality."""
        module = FinanceModule()
        await module._initialize_wrapper()
        await module._register_handlers_wrapper()
        
        # Test command matching
        assert module.matches_command("receipt processing") is not None
        assert module.matches_command("finance help") is not None
        assert module.matches_command("unknown command") is None
        
        # Test envelope processing
        envelope = InternalEnvelope(
            user_id="123456789",
            action="finance help"
        )
        
        response = await module._process_envelope_wrapper(envelope)
        assert response is not None
        assert "Finance Module Help" in response
    
    @pytest.mark.asyncio
    async def test_bot_initialization_without_telegram(self):
        """Test bot initialization without actually connecting to Telegram."""
        # Mock the Telegram Application to avoid actual connection
        with patch('telegram.ext.Application.builder') as mock_builder:
            mock_app = Mock()
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            bot = UmbraBot()
            assert bot is not None
            assert bot.config is not None
            assert len(bot.modules) == 0  # No modules loaded yet
            
            # Test configuration validation
            assert bot._is_user_allowed("123456789") == True
            assert bot._is_user_allowed("999999999") == False
            
            # Test status
            status = bot.get_status()
            assert isinstance(status, dict)
            assert "is_running" in status
            assert "modules_loaded" in status
    
    def test_environment_variable_parsing(self):
        """Test environment variable parsing edge cases."""
        # Test comma-separated user IDs with spaces
        os.environ["ALLOWED_USER_IDS"] = " 123 , 456 , 789 "
        config = UmbraConfig()
        
        assert "123" in config.allowed_user_ids
        assert "456" in config.allowed_user_ids
        assert "789" in config.allowed_user_ids
        assert len(config.allowed_user_ids) == 3
    
    def test_missing_optional_config_detection(self):
        """Test detection of missing optional configuration."""
        config = UmbraConfig()
        missing = config.get_missing_optional_keys()
        
        assert isinstance(missing, list)
        # Should include API keys that are not set
        assert "OPENAI_API_KEY" in missing
        assert "VPS_HOST" in missing
    
    @pytest.mark.asyncio
    async def test_envelope_processing_error_handling(self):
        """Test error handling in envelope processing."""
        module = FinanceModule()
        await module._initialize_wrapper()
        
        # Create envelope with invalid data
        envelope = InternalEnvelope(
            user_id="123456789",
            action="invalid_action"
        )
        
        # Should not raise exception, should return None or error message
        response = await module._process_envelope_wrapper(envelope)
        # Response can be None (not handled) or an error message
        assert response is None or isinstance(response, str)
    
    def test_module_status_reporting(self):
        """Test module status reporting."""
        module = FinanceModule()
        
        status = module.get_status()
        assert isinstance(status, dict)
        assert status["name"] == "finance"
        assert status["is_initialized"] == False  # Not initialized yet
        assert "handler_count" in status


class TestIntegration:
    """Integration tests for module interactions."""
    
    def setup_method(self):
        """Setup test environment."""
        os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:test_token_for_testing"
        os.environ["ALLOWED_USER_IDS"] = "123456789"
        os.environ["FEATURE_METRICS_COLLECTION"] = "true"
    
    def teardown_method(self):
        """Cleanup test environment."""
        test_vars = [
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_IDS",
            "FEATURE_METRICS_COLLECTION"
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
    
    @pytest.mark.asyncio
    async def test_module_interaction_through_envelopes(self):
        """Test modules can process envelopes correctly."""
        # Initialize both modules
        finance_module = FinanceModule()
        monitoring_module = MonitoringModule()
        
        await finance_module._initialize_wrapper()
        await monitoring_module._initialize_wrapper()
        
        # Test finance module envelope processing
        finance_envelope = InternalEnvelope(
            user_id="123456789",
            action="receipt help"
        )
        
        finance_response = await finance_module._process_envelope_wrapper(finance_envelope)
        assert finance_response is not None
        
        # Test monitoring module envelope processing
        monitoring_envelope = InternalEnvelope(
            user_id="123456789",
            action="health check"
        )
        
        monitoring_response = await monitoring_module._process_envelope_wrapper(monitoring_envelope)
        assert monitoring_response is not None
        assert "System Health Check" in monitoring_response
        
        # Cleanup
        await finance_module._shutdown_wrapper()
        await monitoring_module._shutdown_wrapper()


if __name__ == "__main__":
    # Run basic smoke test
    print("Running Umbra Bot smoke tests...")
    
    # Test configuration loading
    os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:test_token"
    os.environ["ALLOWED_USER_IDS"] = "123456789"
    
    try:
        config = UmbraConfig()
        print("✅ Configuration loading: PASSED")
    except Exception as e:
        print(f"❌ Configuration loading: FAILED - {e}")
        exit(1)
    
    # Test logger
    try:
        logger = get_logger("test")
        logger.info("Test log message")
        print("✅ Logger creation: PASSED")
    except Exception as e:
        print(f"❌ Logger creation: FAILED - {e}")
        exit(1)
    
    # Test feature flags
    try:
        enabled = is_enabled("finance_ocr_enabled")
        print(f"✅ Feature flags: PASSED (finance_ocr_enabled: {enabled})")
    except Exception as e:
        print(f"❌ Feature flags: FAILED - {e}")
        exit(1)
    
    print("\n🎉 All smoke tests passed! The bot infrastructure is working.")
    print("\nTo run full test suite: pytest tests/")
    print("To run the bot: python -m umbra.bot")