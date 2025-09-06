"""
Tests for F3R1 AI Agent with auto-registration.
Tests automatic OpenRouter provider registration and enhanced functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from umbra.ai.agent import UmbraAIAgent, AgentRequest, AgentResponse, AgentCapability


class TestUmbraAIAgentF3R1:
    """Test enhanced AI Agent with F3R1 auto-registration features."""
    
    @pytest.fixture
    def config_with_openrouter(self):
        """Mock configuration with OpenRouter enabled."""
        config = Mock()
        config.OPENROUTER_API_KEY = "test_openrouter_key"
        config.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
        config.OPENROUTER_DEFAULT_MODEL = "anthropic/claude-3.5-sonnet:beta"
        config.LOCALE_TZ = "Europe/Zurich"
        return config
    
    @pytest.fixture
    def config_without_openrouter(self):
        """Mock configuration without OpenRouter."""
        config = Mock()
        config.OPENROUTER_API_KEY = None
        return config
    
    def test_ai_agent_initialization_with_openrouter(self, config_with_openrouter):
        """Test AI agent initialization with OpenRouter auto-registration."""
        
        with patch('umbra.ai.agent.OpenRouterProvider') as mock_provider_class:
            # Mock the provider instance
            mock_provider = Mock()
            mock_provider.is_available.return_value = True
            mock_provider.get_capabilities.return_value = [AgentCapability.CONVERSATION]
            mock_provider_class.return_value = mock_provider
            
            # Create agent
            agent = UmbraAIAgent(config_with_openrouter)
            
            # Should have auto-registered OpenRouter
            assert len(agent.providers) == 1
            assert "openrouter" in agent.providers
            assert agent.default_provider == "openrouter"
    
    def test_ai_agent_initialization_without_openrouter(self, config_without_openrouter):
        """Test AI agent initialization without OpenRouter."""
        
        agent = UmbraAIAgent(config_without_openrouter)
        
        # Should have no providers
        assert len(agent.providers) == 0
        assert agent.default_provider is None
        assert len(agent.get_available_providers()) == 0
    
    def test_auto_registration_import_error_handling(self, config_with_openrouter):
        """Test handling of import errors during auto-registration."""
        
        # Mock import error
        with patch('umbra.ai.agent.OpenRouterProvider', side_effect=ImportError("Module not found")):
            agent = UmbraAIAgent(config_with_openrouter)
            
            # Should handle gracefully
            assert len(agent.providers) == 0
            assert agent.default_provider is None
    
    def test_auto_registration_exception_handling(self, config_with_openrouter):
        """Test handling of general exceptions during auto-registration."""
        
        with patch('umbra.ai.agent.OpenRouterProvider') as mock_provider_class:
            # Mock provider that raises exception during creation
            mock_provider_class.side_effect = Exception("Provider initialization failed")
            
            agent = UmbraAIAgent(config_with_openrouter)
            
            # Should handle gracefully
            assert len(agent.providers) == 0
            assert agent.default_provider is None
    
    def test_f3r1_status_reporting(self, config_with_openrouter):
        """Test F3R1 enhanced status reporting."""
        
        with patch('umbra.ai.agent.OpenRouterProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.is_available.return_value = True
            mock_provider.get_capabilities.return_value = [AgentCapability.CONVERSATION]
            mock_provider_class.return_value = mock_provider
            
            agent = UmbraAIAgent(config_with_openrouter)
            status = agent.get_status()
            
            # F3R1 status should include enhanced fields
            assert status["mode"] == "F3R1_enhanced"
            assert status["openrouter_configured"] == True
            assert "openrouter" in status["available_providers"]
            assert status["fallback_mode"] == False
    
    def test_f3r1_status_without_openrouter(self, config_without_openrouter):
        """Test F3R1 status reporting without OpenRouter."""
        
        agent = UmbraAIAgent(config_without_openrouter)
        status = agent.get_status()
        
        assert status["mode"] == "F3R1_enhanced"
        assert status["openrouter_configured"] == False
        assert status["fallback_mode"] == True
    
    @pytest.mark.asyncio
    async def test_successful_response_generation_with_openrouter(self, config_with_openrouter):
        """Test successful response generation using OpenRouter."""
        
        # Mock successful OpenRouter provider
        with patch('umbra.ai.agent.OpenRouterProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.is_available.return_value = True
            mock_provider.get_capabilities.return_value = [AgentCapability.CONVERSATION]
            
            # Mock successful response
            mock_provider.generate_response = AsyncMock(return_value=AgentResponse(
                content="Hello! This is a response from OpenRouter.",
                success=True,
                provider="openrouter",
                model="anthropic/claude-3.5-sonnet:beta",
                duration_ms=250.5
            ))
            
            mock_provider_class.return_value = mock_provider
            
            # Create agent and generate response
            agent = UmbraAIAgent(config_with_openrouter)
            response = await agent.generate_response(
                message="Hello AI",
                user_id=123,
                context={"test": True}
            )
            
            # Verify response
            assert response.success == True
            assert response.content == "Hello! This is a response from OpenRouter."
            assert response.provider == "openrouter"
            assert response.model == "anthropic/claude-3.5-sonnet:beta"
            assert response.duration_ms == 250.5
    
    @pytest.mark.asyncio
    async def test_fallback_response_without_provider(self, config_without_openrouter):
        """Test fallback response when no providers are available."""
        
        agent = UmbraAIAgent(config_without_openrouter)
        
        response = await agent.generate_response(
            message="Hello AI",
            user_id=123
        )
        
        # Should get fallback response
        assert response.success == False
        assert response.provider == "fallback"
        assert response.model == "basic_patterns"
        assert "F3R1" in response.content
        assert "OpenRouter integration" in response.content
    
    @pytest.mark.asyncio
    async def test_provider_error_fallback(self, config_with_openrouter):
        """Test fallback when provider fails."""
        
        with patch('umbra.ai.agent.OpenRouterProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.is_available.return_value = True
            mock_provider.get_capabilities.return_value = [AgentCapability.CONVERSATION]
            
            # Mock provider that fails during response generation
            mock_provider.generate_response = AsyncMock(side_effect=Exception("API Error"))
            mock_provider_class.return_value = mock_provider
            
            agent = UmbraAIAgent(config_with_openrouter)
            
            response = await agent.generate_response(
                message="Hello AI",
                user_id=123
            )
            
            # Should get fallback response
            assert response.success == False
            assert response.provider == "fallback"
            assert response.error is not None
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, config_with_openrouter):
        """Test timeout handling during response generation."""
        
        with patch('umbra.ai.agent.OpenRouterProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.is_available.return_value = True
            mock_provider.get_capabilities.return_value = [AgentCapability.CONVERSATION]
            
            # Mock provider that times out
            async def slow_response(request):
                await asyncio.sleep(2)  # Longer than timeout
                return AgentResponse(content="Should not reach here", success=True)
            
            mock_provider.generate_response = slow_response
            mock_provider_class.return_value = mock_provider
            
            agent = UmbraAIAgent(config_with_openrouter)
            
            response = await agent.generate_response(
                message="Hello AI",
                user_id=123,
                timeout=1  # 1 second timeout
            )
            
            # Should get timeout fallback
            assert response.success == False
            assert response.provider == "fallback"
            assert "timeout" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_health_check_with_openrouter(self, config_with_openrouter):
        """Test health check with OpenRouter provider."""
        
        with patch('umbra.ai.agent.OpenRouterProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.is_available.return_value = True
            mock_provider.get_capabilities.return_value = [AgentCapability.CONVERSATION]
            mock_provider_class.return_value = mock_provider
            
            agent = UmbraAIAgent(config_with_openrouter)
            health = await agent.health_check()
            
            assert health["agent_healthy"] == True
            assert health["overall_status"] == "healthy"
            assert "openrouter" in health["providers"]
            assert health["providers"]["openrouter"]["available"] == True
            assert health["providers"]["openrouter"]["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_check_with_provider_error(self, config_with_openrouter):
        """Test health check when provider has errors."""
        
        with patch('umbra.ai.agent.OpenRouterProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.is_available.side_effect = Exception("Provider error")
            mock_provider_class.return_value = mock_provider
            
            agent = UmbraAIAgent(config_with_openrouter)
            health = await agent.health_check()
            
            assert "openrouter" in health["providers"]
            assert health["providers"]["openrouter"]["available"] == False
            assert health["providers"]["openrouter"]["status"] == "error"
    
    def test_f3r1_enhanced_basic_responses(self, config_without_openrouter):
        """Test enhanced basic responses in F3R1 mode."""
        
        agent = UmbraAIAgent(config_without_openrouter)
        
        # Test various pattern responses
        hello_response = agent._generate_basic_response("Hello")
        assert "OpenRouter integration" in hello_response
        
        help_response = agent._generate_basic_response("What can you do?")
        assert "F3R1 capabilities" in help_response
        assert "OpenRouter" in help_response
        
        status_response = agent._generate_basic_response("Status")
        assert "F3R1 Mode" in status_response
        
        # Default response should be more informative
        default_response = agent._generate_basic_response("Random question")
        assert "F3R1 Mode" in default_response
        assert "OpenRouter integration" in default_response
        assert "naturally" in default_response


class TestManualProviderRegistration:
    """Test manual provider registration still works in F3R1."""
    
    @pytest.fixture
    def agent(self):
        """Create agent without auto-registration."""
        config = Mock()
        config.OPENROUTER_API_KEY = None  # Disable auto-registration
        return UmbraAIAgent(config)
    
    def test_manual_provider_registration(self, agent):
        """Test manual provider registration."""
        
        # Create mock provider
        mock_provider = Mock()
        mock_provider.is_available.return_value = True
        mock_provider.get_capabilities.return_value = [AgentCapability.CONVERSATION]
        
        # Register manually
        agent.register_provider("custom_provider", mock_provider)
        
        assert "custom_provider" in agent.providers
        assert agent.default_provider == "custom_provider"
        assert len(agent.get_available_providers()) == 1
    
    def test_multiple_provider_registration(self, agent):
        """Test registering multiple providers."""
        
        # Create multiple mock providers
        provider1 = Mock()
        provider1.is_available.return_value = True
        provider1.get_capabilities.return_value = [AgentCapability.CONVERSATION]
        
        provider2 = Mock()
        provider2.is_available.return_value = True
        provider2.get_capabilities.return_value = [AgentCapability.CODE_GENERATION]
        
        # Register both
        agent.register_provider("provider1", provider1)
        agent.register_provider("provider2", provider2)
        
        assert len(agent.providers) == 2
        assert agent.default_provider == "provider1"  # First available becomes default
        assert len(agent.get_available_providers()) == 2


if __name__ == "__main__":
    pytest.main([__file__])
