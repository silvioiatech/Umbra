"""
Tests for F3R1 Router with general_chat fallback.
Tests deterministic routing and AI-powered fallback functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from umbra.router import UmbraRouter, RouteResult, RouteType


class TestUmbraRouter:
    """Test enhanced router with general_chat fallback."""
    
    @pytest.fixture
    def router(self):
        """Create router instance."""
        return UmbraRouter()
    
    @pytest.fixture
    def mock_module_registry(self):
        """Create mock module registry."""
        registry = Mock()
        
        # Mock successful general_chat execution
        registry.execute_module_action = AsyncMock(return_value={
            "success": True,
            "result": {
                "content": "This is an AI response from general_chat"
            }
        })
        
        return registry
    
    def test_router_initialization(self, router):
        """Test router initialization with patterns."""
        assert len(router.routes) > 0
        
        # Check some expected patterns exist
        patterns = [route.pattern for route in router.routes]
        assert "/status" in patterns
        assert "/help" in patterns
        assert "system status" in patterns
    
    def test_exact_match_routing(self, router):
        """Test exact match routing patterns."""
        
        # Test /status command
        result = router.route_message("/status", user_id=123, is_admin=True)
        
        assert result.matched == True
        assert result.module == "bot"
        assert result.action == "status"
        assert result.confidence == 1.0
    
    def test_keyword_match_routing(self, router):
        """Test keyword matching patterns."""
        
        # Test system status
        result = router.route_message("show me system status", user_id=123, is_admin=False)
        
        assert result.matched == True
        assert result.module == "concierge_mcp"
        assert result.action == "system_status"
        assert result.confidence == 0.8
    
    def test_regex_pattern_routing(self, router):
        """Test regex pattern matching with parameter extraction."""
        
        # Test calculation pattern
        result = router.route_message("calculate 2 + 2", user_id=123, is_admin=False)
        
        assert result.matched == True
        assert result.module == "general_chat_mcp"
        assert result.action == "calculate"
        assert result.params == {"expression": "2 + 2"}
    
    def test_unit_conversion_routing(self, router):
        """Test unit conversion pattern with complex parameter extraction."""
        
        # Test unit conversion
        result = router.route_message("convert 100 km to miles", user_id=123, is_admin=False)
        
        assert result.matched == True
        assert result.module == "general_chat_mcp"
        assert result.action == "convert_units"
        assert result.params["value"] == 100
        assert result.params["from_unit"] == "km"
        assert result.params["to_unit"] == "miles"
    
    def test_admin_only_routing(self, router):
        """Test admin-only pattern protection."""
        
        # Non-admin tries admin command
        result = router.route_message("execute ls -la", user_id=123, is_admin=False)
        
        assert result.matched == False
        assert result.requires_admin == True
        
        # Admin uses admin command
        result = router.route_message("execute ls -la", user_id=123, is_admin=True)
        
        assert result.matched == True
        assert result.module == "concierge_mcp"
        assert result.action == "execute_command"
        assert result.params == {"command": "ls -la"}
    
    def test_no_match_fallback(self, router):
        """Test behavior when no patterns match."""
        
        # Random text that shouldn't match any pattern
        result = router.route_message("random unmatched text", user_id=123, is_admin=False)
        
        assert result.matched == False
        assert result.requires_admin == False
    
    @pytest.mark.asyncio
    async def test_general_chat_fallback_success(self, router, mock_module_registry):
        """Test successful routing to general_chat for unmatched messages."""
        
        message = "Tell me about artificial intelligence"
        user_id = 123
        
        response = await router.route_to_general_chat(message, user_id, mock_module_registry)
        
        assert response == "This is an AI response from general_chat"
        
        # Verify the correct call was made
        mock_module_registry.execute_module_action.assert_called_once_with(
            "general_chat_mcp",
            "ask",
            {
                "text": message,
                "use_tools": True,
                "user_id": user_id
            },
            user_id
        )
    
    @pytest.mark.asyncio
    async def test_general_chat_fallback_failure(self, router):
        """Test handling when general_chat fails."""
        
        # Mock failing module registry
        mock_registry = Mock()
        mock_registry.execute_module_action = AsyncMock(return_value={
            "success": False,
            "error": "General chat module failed"
        })
        
        response = await router.route_to_general_chat("test message", 123, mock_registry)
        
        assert response is None
    
    @pytest.mark.asyncio
    async def test_general_chat_exception_handling(self, router):
        """Test exception handling in general_chat routing."""
        
        # Mock registry that raises exception
        mock_registry = Mock()
        mock_registry.execute_module_action = AsyncMock(side_effect=Exception("Connection error"))
        
        response = await router.route_to_general_chat("test message", 123, mock_registry)
        
        assert response is None
    
    def test_pattern_statistics_tracking(self, router):
        """Test routing statistics tracking."""
        
        # Initial stats
        initial_stats = router.get_stats()
        initial_requests = initial_stats["total_requests"]
        
        # Route some messages
        router.route_message("/status", 123, False)
        router.route_message("system status", 123, False)
        router.route_message("unmatched message", 123, False)
        
        # Check updated stats
        stats = router.get_stats()
        
        assert stats["total_requests"] == initial_requests + 3
        assert stats["matched_requests"] >= 2
        assert stats["unmatched_requests"] >= 1
        assert stats["match_rate"] >= 0
    
    def test_pattern_usage_tracking(self, router):
        """Test individual pattern usage tracking."""
        
        # Use the same pattern multiple times
        router.route_message("/status", 123, False)
        router.route_message("/status", 456, False)
        
        stats = router.get_stats()
        
        # Check that pattern usage is tracked
        assert "most_used_patterns" in stats
        assert len(stats["most_used_patterns"]) >= 0
    
    def test_get_available_patterns(self, router):
        """Test getting available patterns."""
        
        # Get all patterns
        all_patterns = router.get_available_patterns(admin_only=False)
        assert len(all_patterns) > 0
        
        # Get admin-only patterns
        admin_patterns = router.get_available_patterns(admin_only=True)
        
        # Check pattern structure
        for pattern in all_patterns:
            assert "pattern" in pattern
            assert "type" in pattern
            assert "module" in pattern
            assert "action" in pattern
            assert "description" in pattern
            assert "admin_only" in pattern
        
        # Admin patterns should be subset of all patterns
        assert len(admin_patterns) <= len(all_patterns)
    
    def test_stats_reset(self, router):
        """Test statistics reset functionality."""
        
        # Generate some stats
        router.route_message("/status", 123, False)
        router.route_message("test", 123, False)
        
        # Verify stats exist
        stats_before = router.get_stats()
        assert stats_before["total_requests"] > 0
        
        # Reset stats
        router.reset_stats()
        
        # Verify reset
        stats_after = router.get_stats()
        assert stats_after["total_requests"] == 0
        assert stats_after["matched_requests"] == 0
        assert stats_after["unmatched_requests"] == 0
    
    def test_f3r1_enhanced_stats(self, router):
        """Test F3R1 enhanced statistics including general_chat fallbacks."""
        
        stats = router.get_stats()
        
        # F3R1 should include general_chat_fallbacks in stats
        assert "general_chat_fallbacks" in stats
        assert stats["general_chat_fallbacks"] >= 0
    
    def test_fallback_response_content(self, router):
        """Test fallback response when general_chat is not available."""
        
        response = router.get_fallback_response("test message", 123)
        
        assert isinstance(response, str)
        assert "F3R1 Mode" in response
        assert "AI Chat" in response
        assert "naturally" in response.lower()


class TestRoutePatternMatching:
    """Test specific pattern matching logic."""
    
    @pytest.fixture
    def router(self):
        return UmbraRouter()
    
    def test_time_patterns(self, router):
        """Test time-related patterns."""
        
        # Various time queries
        time_queries = [
            "what time is it",
            "current time",
            "time now",
            "what's the time"
        ]
        
        for query in time_queries:
            result = router.route_message(query, 123, False)
            assert result.matched == True
            assert result.module == "general_chat_mcp"
            assert result.action == "get_time"
    
    def test_calculation_patterns(self, router):
        """Test calculation patterns."""
        
        calc_queries = [
            "calculate 5 + 5",
            "calculate sqrt(16)",
            "calculate 2 * pi"
        ]
        
        for query in calc_queries:
            result = router.route_message(query, 123, False)
            assert result.matched == True
            assert result.module == "general_chat_mcp"
            assert result.action == "calculate"
            assert "expression" in result.params
    
    def test_docker_patterns(self, router):
        """Test Docker-related patterns."""
        
        docker_queries = [
            "docker status",
            "docker ps",
            "docker containers"
        ]
        
        for query in docker_queries:
            result = router.route_message(query, 123, False)
            assert result.matched == True
            assert result.module == "concierge_mcp"
            assert result.action == "docker_status"


if __name__ == "__main__":
    pytest.main([__file__])
