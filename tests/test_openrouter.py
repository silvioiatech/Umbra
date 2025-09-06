"""
Tests for F3R1 OpenRouter Provider.
Tests OpenRouter client, model routing, and API integration.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import httpx

from umbra.providers.openrouter import OpenRouterClient, OpenRouterProvider, ModelRole
from umbra.ai.agent import AgentRequest, AgentCapability


class TestOpenRouterClient:
    """Test OpenRouter API client."""
    
    @pytest.fixture
    def config_mock(self):
        """Mock configuration."""
        config = Mock()
        config.OPENROUTER_API_KEY = "test_api_key"
        config.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
        config.OPENROUTER_DEFAULT_MODEL = "anthropic/claude-3.5-sonnet:beta"
        config.OPENROUTER_REQUEST_TIMEOUT_MS = 20000
        config.OPENROUTER_MODEL_PLANNER = "anthropic/claude-3-haiku:beta"
        config.OPENROUTER_MODEL_CHAT = "anthropic/claude-3.5-sonnet:beta"
        return config
    
    @pytest.fixture
    def client(self, config_mock):
        """Create OpenRouter client."""
        return OpenRouterClient(config_mock)
    
    def test_client_initialization(self, client, config_mock):
        """Test client initialization."""
        assert client.api_key == "test_api_key"
        assert client.default_model == "anthropic/claude-3.5-sonnet:beta"
        assert client.is_available() == True
        
        # Test role model mapping
        assert client.get_model_for_role(ModelRole.PLANNER) == "anthropic/claude-3-haiku:beta"
        assert client.get_model_for_role(ModelRole.CHAT) == "anthropic/claude-3.5-sonnet:beta"
        assert client.get_model_for_role(None) == "anthropic/claude-3.5-sonnet:beta"
    
    def test_client_not_available_without_key(self):
        """Test client is not available without API key."""
        config = Mock()
        config.OPENROUTER_API_KEY = None
        client = OpenRouterClient(config)
        assert client.is_available() == False
    
    @pytest.mark.asyncio
    async def test_successful_completion(self, client):
        """Test successful API completion."""
        
        # Mock response
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "Hello! This is a test response."
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18
            },
            "model": "anthropic/claude-3.5-sonnet:beta"
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            # Setup mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            # Test completion
            messages = [{"role": "user", "content": "Hello"}]
            result = await client.generate_completion(messages, temperature=0.7)
            
            assert result == mock_response_data
            assert "choices" in result
            assert result["choices"][0]["message"]["content"] == "Hello! This is a test response."
    
    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, client):
        """Test retry logic on rate limit."""
        
        with patch('httpx.AsyncClient') as mock_client:
            # First response: rate limit
            rate_limit_response = Mock()
            rate_limit_response.status_code = 429
            
            # Second response: success
            success_response = Mock()
            success_response.status_code = 200
            success_response.json.return_value = {
                "choices": [{"message": {"content": "Success after retry"}}]
            }
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=[rate_limit_response, success_response]
            )
            
            with patch('asyncio.sleep') as mock_sleep:
                messages = [{"role": "user", "content": "Test"}]
                result = await client.generate_completion(messages, retries=1)
                
                # Should have retried once
                assert mock_sleep.call_count == 1
                assert result["choices"][0]["message"]["content"] == "Success after retry"


class TestOpenRouterProvider:
    """Test OpenRouter AI Provider."""
    
    @pytest.fixture
    def config_mock(self):
        """Mock configuration."""
        config = Mock()
        config.OPENROUTER_API_KEY = "test_api_key"
        config.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
        config.OPENROUTER_DEFAULT_MODEL = "anthropic/claude-3.5-sonnet:beta"
        config.LOCALE_TZ = "Europe/Zurich"
        return config
    
    @pytest.fixture
    def provider(self, config_mock):
        """Create OpenRouter provider."""
        return OpenRouterProvider(config_mock)
    
    def test_provider_capabilities(self, provider):
        """Test provider capabilities."""
        caps = provider.get_capabilities()
        assert AgentCapability.CONVERSATION in caps
        assert AgentCapability.FUNCTION_CALLING in caps
        assert AgentCapability.CODE_GENERATION in caps
    
    def test_provider_availability(self, provider):
        """Test provider availability."""
        assert provider.is_available() == True
    
    @pytest.mark.asyncio
    async def test_successful_response_generation(self, provider):
        """Test successful response generation."""
        
        # Mock the client
        with patch.object(provider.client, 'generate_completion') as mock_completion:
            mock_completion.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "This is a test AI response."
                        }
                    }
                ],
                "usage": {"total_tokens": 20},
                "model": "anthropic/claude-3.5-sonnet:beta"
            }
            
            # Create request
            request = AgentRequest(
                message="Hello AI",
                user_id=123,
                context={"test": "context"}
            )
            
            # Generate response
            response = await provider.generate_response(request)
            
            assert response.success == True
            assert response.content == "This is a test AI response."
            assert response.provider == "openrouter"
            assert response.model == "anthropic/claude-3.5-sonnet:beta"
    
    @pytest.mark.asyncio
    async def test_provider_not_available(self):
        """Test response when provider not available."""
        config = Mock()
        config.OPENROUTER_API_KEY = None
        provider = OpenRouterProvider(config)
        
        request = AgentRequest(message="Test", user_id=123)
        response = await provider.generate_response(request)
        
        assert response.success == False
        assert "not configured" in response.error


if __name__ == "__main__":
    pytest.main([__file__])
