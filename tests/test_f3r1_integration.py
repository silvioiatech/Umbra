"""
Integration tests for F3R1 complete flow.
Tests the full pipeline: Bot -> Router -> Module Registry -> AI Agent -> OpenRouter.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from umbra.bot import UmbraBot
from umbra.router import UmbraRouter
from umbra.modules.registry import ModuleRegistry
from umbra.ai.agent import UmbraAIAgent


class TestF3R1Integration:
    """Test complete F3R1 integration flow."""
    
    @pytest.fixture
    def config_f3r1(self):
        """Mock configuration for F3R1 testing."""
        config = Mock()
        
        # Required bot config
        config.TELEGRAM_BOT_TOKEN = "test_bot_token"
        config.ALLOWED_USER_IDS = [123, 456]
        config.ALLOWED_ADMIN_IDS = [123]
        config.RATE_LIMIT_PER_MIN = 20
        config.RATE_LIMIT_ENABLED = True
        config.DATABASE_PATH = ":memory:"
        config.ENVIRONMENT = "test"
        config.LOCALE_TZ = "Europe/Zurich"
        config.PRIVACY_MODE = "strict"
        config.PORT = 8000
        
        # F3R1 OpenRouter config
        config.OPENROUTER_API_KEY = "test_openrouter_key"
        config.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
        config.OPENROUTER_DEFAULT_MODEL = "anthropic/claude-3.5-sonnet:beta"
        config.OPENROUTER_REQUEST_TIMEOUT_MS = 20000
        
        return config
    
    @pytest.fixture
    async def bot_with_f3r1(self, config_f3r1):
        """Create bot instance with F3R1 components."""
        
        # Mock database manager to avoid file operations
        with patch('umbra.bot.DatabaseManager') as mock_db_manager:
            mock_db_manager.return_value.add_user = Mock()
            mock_db_manager.return_value.close = AsyncMock()
            
            # Mock conversation manager
            with patch('umbra.bot.ConversationManager') as mock_conv_manager:
                mock_conv_manager.return_value.add_message = Mock()
                
                # Create bot instance
                bot = UmbraBot(config_f3r1)
                
                return bot
    
    @pytest.mark.asyncio
    async def test_f3r1_component_initialization(self, bot_with_f3r1):
        """Test that all F3R1 components are properly initialized."""
        
        bot = bot_with_f3r1
        
        # Check core components exist
        assert bot.ai_agent is not None
        assert bot.module_registry is not None
        assert bot.router is not None
        
        # Check F3R1 component types
        assert isinstance(bot.ai_agent, UmbraAIAgent)
        assert isinstance(bot.module_registry, ModuleRegistry)
        assert isinstance(bot.router, UmbraRouter)
        
        # Initialize F3R1 components
        await bot._initialize_f3r1_components()
        
        # Check initialization completed
        assert bot._modules_discovered == True
    
    @pytest.mark.asyncio
    async def test_deterministic_routing_flow(self, bot_with_f3r1):
        """Test deterministic routing to modules."""
        
        bot = bot_with_f3r1
        await bot._initialize_f3r1_components()
        
        # Mock module execution
        with patch.object(bot.module_registry, 'execute_module_action') as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "result": {"content": "System status: All good!"}
            }
            
            # Test routing
            response = await bot._execute_module_action(
                "concierge_mcp", "system_status", {}, 123
            )
            
            assert response == "System status: All good!"
            mock_execute.assert_called_once_with(
                "concierge_mcp", "system_status", {}, 123
            )
    
    @pytest.mark.asyncio
    async def test_general_chat_fallback_flow(self, bot_with_f3r1):
        """Test general_chat fallback for unmatched messages."""
        
        bot = bot_with_f3r1
        await bot._initialize_f3r1_components()
        
        # Mock general_chat response
        with patch.object(bot.router, 'route_to_general_chat') as mock_general_chat:
            mock_general_chat.return_value = "I understand you're asking about AI. Here's what I know..."
            
            # Test unmatched message routing
            message = "Tell me about artificial intelligence"
            user_id = 123
            
            # Route message
            route_result = bot.router.route_message(message, user_id, is_admin=False)
            assert route_result.matched == False
            
            # Should fall back to general_chat
            response = await bot.router.route_to_general_chat(message, user_id, bot.module_registry)
            
            assert response == "I understand you're asking about AI. Here's what I know..."
            mock_general_chat.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_openrouter_ai_integration(self, bot_with_f3r1):
        """Test OpenRouter AI integration through general_chat."""
        
        bot = bot_with_f3r1
        
        # Mock OpenRouter provider
        with patch('umbra.providers.openrouter.OpenRouterProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.is_available.return_value = True
            mock_provider.get_capabilities.return_value = []
            
            # Mock AI response
            from umbra.ai.agent import AgentResponse
            mock_provider.generate_response = AsyncMock(return_value=AgentResponse(
                content="According to my knowledge, artificial intelligence is...",
                success=True,
                provider="openrouter",
                model="anthropic/claude-3.5-sonnet:beta"
            ))
            
            mock_provider_class.return_value = mock_provider
            
            # Test AI agent generation
            response = await bot.ai_agent.generate_response(
                message="What is artificial intelligence?",
                user_id=123
            )
            
            assert response.success == True
            assert response.content == "According to my knowledge, artificial intelligence is..."
            assert response.provider == "openrouter"
    
    @pytest.mark.asyncio
    async def test_builtin_tools_integration(self, bot_with_f3r1):
        """Test built-in tools (calculator, time, units) integration."""
        
        bot = bot_with_f3r1
        await bot._initialize_f3r1_components()
        
        # Test calculator routing
        calc_route = bot.router.route_message("calculate 2 + 2", 123, False)
        assert calc_route.matched == True
        assert calc_route.module == "general_chat_mcp"
        assert calc_route.action == "calculate"
        assert calc_route.params["expression"] == "2 + 2"
        
        # Test time routing
        time_route = bot.router.route_message("what time is it", 123, False)
        assert time_route.matched == True
        assert time_route.module == "general_chat_mcp"
        assert time_route.action == "get_time"
        
        # Test unit conversion routing
        unit_route = bot.router.route_message("convert 100 km to miles", 123, False)
        assert unit_route.matched == True
        assert unit_route.module == "general_chat_mcp"
        assert unit_route.action == "convert_units"
    
    @pytest.mark.asyncio
    async def test_admin_permission_flow(self, bot_with_f3r1):
        """Test admin permission checking in routing."""
        
        bot = bot_with_f3r1
        
        # Test admin-only command as non-admin
        admin_route = bot.router.route_message("execute ls -la", 456, is_admin=False)
        assert admin_route.matched == False
        assert admin_route.requires_admin == True
        
        # Test same command as admin
        admin_route = bot.router.route_message("execute ls -la", 123, is_admin=True)
        assert admin_route.matched == True
        assert admin_route.module == "concierge_mcp"
        assert admin_route.action == "execute_command"
    
    @pytest.mark.asyncio
    async def test_error_handling_flow(self, bot_with_f3r1):
        """Test error handling throughout the F3R1 flow."""
        
        bot = bot_with_f3r1
        await bot._initialize_f3r1_components()
        
        # Test module execution error
        with patch.object(bot.module_registry, 'execute_module_action') as mock_execute:
            mock_execute.side_effect = Exception("Module execution failed")
            
            response = await bot._execute_module_action(
                "test_module", "test_action", {}, 123
            )
            
            assert "Execution Failed" in response
            assert "Module execution failed" not in response  # Should be redacted
    
    @pytest.mark.asyncio
    async def test_complete_message_processing_flow(self, bot_with_f3r1):
        """Test complete message processing from input to output."""
        
        bot = bot_with_f3r1
        await bot._initialize_f3r1_components()
        
        # Mock Telegram update
        from telegram import Update, Message, User, Chat
        
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=123, type="private")
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            text="What's 5 + 3?"
        )
        
        # Mock update
        update = Mock()
        update.effective_user = user
        update.effective_chat = chat
        update.message = message
        update.message.text = "What's 5 + 3?"
        update.message.reply_text = AsyncMock()
        
        # Mock context
        context = Mock()
        context.bot.send_chat_action = AsyncMock()
        
        # Mock module execution for general_chat
        with patch.object(bot.module_registry, 'execute_module_action') as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "result": {"content": "**Calculation:** 5 + 3 = **8**"}
            }
            
            # Process message
            await bot._handle_text_message(update, context)
            
            # Verify response was sent
            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            assert "5 + 3 = **8**" in response_text
    
    def test_f3r1_status_integration(self, bot_with_f3r1):
        """Test integrated status reporting across all F3R1 components."""
        
        bot = bot_with_f3r1
        
        # Get comprehensive status
        bot_status = bot.get_status()
        ai_status = bot.ai_agent.get_status()
        router_stats = bot.router.get_stats()
        
        # Verify F3R1 status fields
        assert bot_status["f3r1_mode"] == True
        assert "components" in bot_status
        assert ai_status["mode"] == "F3R1_enhanced"
        assert "general_chat_fallbacks" in router_stats
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, bot_with_f3r1):
        """Test graceful degradation when components fail."""
        
        bot = bot_with_f3r1
        
        # Test when AI agent fails
        with patch.object(bot.ai_agent, 'generate_response') as mock_ai:
            mock_ai.side_effect = Exception("AI service unavailable")
            
            # Should still work with fallback
            route_result = bot.router.route_message("Random question", 123, False)
            assert route_result.matched == False
            
            # Fallback response should still work
            fallback = bot.router.get_fallback_response("Random question", 123)
            assert isinstance(fallback, str)
            assert "F3R1" in fallback
    
    @pytest.mark.asyncio
    async def test_module_discovery_integration(self, bot_with_f3r1):
        """Test module discovery and registry integration."""
        
        bot = bot_with_f3r1
        
        # Mock module discovery
        with patch.object(bot.module_registry, 'discover_modules') as mock_discover:
            mock_discover.return_value = 5  # Found 5 modules
            
            with patch.object(bot.module_registry, 'get_available_modules') as mock_available:
                mock_available.return_value = ["general_chat_mcp", "concierge_mcp", "finance_mcp"]
                
                await bot._initialize_f3r1_components()
                
                assert bot._modules_discovered == True
                mock_discover.assert_called_once()


class TestF3R1Performance:
    """Test F3R1 performance and efficiency."""
    
    @pytest.fixture
    def config_f3r1(self):
        """Mock configuration for performance testing."""
        config = Mock()
        config.TELEGRAM_BOT_TOKEN = "test_token"
        config.ALLOWED_USER_IDS = [123]
        config.ALLOWED_ADMIN_IDS = [123]
        config.RATE_LIMIT_PER_MIN = 20
        config.RATE_LIMIT_ENABLED = True
        config.DATABASE_PATH = ":memory:"
        config.ENVIRONMENT = "test"
        config.LOCALE_TZ = "Europe/Zurich"
        config.OPENROUTER_API_KEY = "test_key"
        return config
    
    def test_router_pattern_matching_performance(self, config_f3r1):
        """Test router pattern matching performance."""
        
        router = UmbraRouter()
        
        # Test multiple routing operations
        start_time = asyncio.get_event_loop().time()
        
        for i in range(100):
            result = router.route_message(f"test message {i}", 123, False)
        
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        
        # Should be fast (under 0.1 seconds for 100 operations)
        assert duration < 0.1
        
        # Check statistics are properly tracked
        stats = router.get_stats()
        assert stats["total_requests"] >= 100
    
    @pytest.mark.asyncio
    async def test_component_initialization_speed(self, config_f3r1):
        """Test F3R1 component initialization speed."""
        
        with patch('umbra.bot.DatabaseManager'), \
             patch('umbra.bot.ConversationManager'):
            
            start_time = asyncio.get_event_loop().time()
            
            # Create bot and initialize
            bot = UmbraBot(config_f3r1)
            await bot._initialize_f3r1_components()
            
            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time
            
            # Should initialize quickly (under 1 second)
            assert duration < 1.0
            
            # Verify components are ready
            assert bot.ai_agent is not None
            assert bot.module_registry is not None
            assert bot.router is not None


if __name__ == "__main__":
    pytest.main([__file__])
