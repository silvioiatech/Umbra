"""
Tests for F3R1 General Chat MCP.
Tests built-in tools: calculator, unit converter, time helper, and AI integration.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from umbra.modules.general_chat_mcp import (
    GeneralChatMCP, Calculator, UnitConverter, TimeHelper, TableFormatter
)


class TestCalculator:
    """Test safe calculator functionality."""
    
    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return Calculator()
    
    def test_basic_arithmetic(self, calculator):
        """Test basic arithmetic operations."""
        
        # Addition
        result = calculator.evaluate("2 + 3")
        assert result.success == True
        assert result.result == 5
        
        # Subtraction
        result = calculator.evaluate("10 - 4")
        assert result.success == True
        assert result.result == 6
        
        # Multiplication
        result = calculator.evaluate("7 * 8")
        assert result.success == True
        assert result.result == 56
        
        # Division
        result = calculator.evaluate("15 / 3")
        assert result.success == True
        assert result.result == 5
    
    def test_advanced_math(self, calculator):
        """Test advanced mathematical functions."""
        
        # Square root
        result = calculator.evaluate("sqrt(16)")
        assert result.success == True
        assert result.result == 4
        
        # Power
        result = calculator.evaluate("pow(2, 3)")
        assert result.success == True
        assert result.result == 8
        
        # Trigonometry
        result = calculator.evaluate("sin(0)")
        assert result.success == True
        assert result.result == 0
        
        # Constants
        result = calculator.evaluate("pi")
        assert result.success == True
        assert abs(result.result - 3.14159) < 0.001
    
    def test_division_by_zero(self, calculator):
        """Test division by zero handling."""
        result = calculator.evaluate("5 / 0")
        assert result.success == False
        assert "Division by zero" in result.error
    
    def test_invalid_expression(self, calculator):
        """Test invalid expression handling."""
        result = calculator.evaluate("2 +")
        assert result.success == False
        assert "Invalid mathematical expression" in result.error
    
    def test_security_protection(self, calculator):
        """Test protection against unsafe expressions."""
        
        # Should block import
        result = calculator.evaluate("import os")
        assert result.success == False
        assert "unsafe" in result.error.lower()
        
        # Should block exec
        result = calculator.evaluate("exec('print(1)')")
        assert result.success == False
        assert "unsafe" in result.error.lower()


class TestUnitConverter:
    """Test unit conversion functionality."""
    
    @pytest.fixture
    def converter(self):
        """Create unit converter instance."""
        return UnitConverter()
    
    def test_length_conversions(self, converter):
        """Test length unit conversions."""
        
        # Meters to kilometers
        result = converter.convert(1000, "m", "km")
        assert result.success == True
        assert result.result == 1
        
        # Centimeters to meters
        result = converter.convert(100, "cm", "m")
        assert result.success == True
        assert result.result == 1
        
        # Inches to centimeters
        result = converter.convert(1, "inch", "cm")
        assert result.success == True
        assert abs(result.result - 2.54) < 0.01
    
    def test_weight_conversions(self, converter):
        """Test weight unit conversions."""
        
        # Kilograms to pounds
        result = converter.convert(1, "kg", "lb")
        assert result.success == True
        assert abs(result.result - 2.20462) < 0.001
        
        # Grams to kilograms
        result = converter.convert(1000, "g", "kg")
        assert result.success == True
        assert result.result == 1
    
    def test_unsupported_conversion(self, converter):
        """Test unsupported conversion handling."""
        result = converter.convert(10, "invalid", "also_invalid")
        assert result.success == False
        assert "not supported" in result.error


class TestTimeHelper:
    """Test time helper functionality."""
    
    @pytest.fixture
    def time_helper(self):
        """Create time helper instance."""
        return TimeHelper()
    
    def test_current_time_formats(self, time_helper):
        """Test different time format outputs."""
        
        # Default format
        result = time_helper.get_current_time("default")
        assert result.success == True
        assert isinstance(result.result, str)
        assert len(result.result) > 10  # Should be a reasonable time string
        
        # ISO format
        result = time_helper.get_current_time("iso")
        assert result.success == True
        assert "T" in result.result  # ISO format contains T
        
        # Human format
        result = time_helper.get_current_time("human")
        assert result.success == True
        assert any(day in result.result for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
    
    def test_duration_parsing(self, time_helper):
        """Test duration string parsing."""
        
        # Hours and minutes
        result = time_helper.parse_duration("2h 30m")
        assert result.success == True
        assert result.result == 2 * 3600 + 30 * 60  # 9000 seconds
        
        # Just hours
        result = time_helper.parse_duration("1h")
        assert result.success == True
        assert result.result == 3600
        
        # Complex duration
        result = time_helper.parse_duration("1d 2h 30m 45s")
        assert result.success == True
        expected = 1 * 86400 + 2 * 3600 + 30 * 60 + 45
        assert result.result == expected
        
        # Invalid duration
        result = time_helper.parse_duration("invalid")
        assert result.success == False


class TestGeneralChatMCP:
    """Test General Chat MCP module."""
    
    @pytest.fixture
    def config_mock(self):
        """Mock configuration."""
        config = Mock()
        config.LOCALE_TZ = "Europe/Zurich"
        config.OPENROUTER_API_KEY = "test_key"
        return config
    
    @pytest.fixture
    def general_chat(self, config_mock):
        """Create General Chat MCP instance."""
        return GeneralChatMCP(config_mock)
    
    @pytest.mark.asyncio
    async def test_get_capabilities(self, general_chat):
        """Test module capabilities."""
        capabilities = await general_chat.get_capabilities()
        
        assert "ask" in capabilities
        assert "calculate" in capabilities
        assert "convert_units" in capabilities
        assert "get_time" in capabilities
        
        # Check capability details
        ask_cap = capabilities["ask"]
        assert ask_cap["admin_only"] == False
        assert "parameters" in ask_cap
    
    @pytest.mark.asyncio
    async def test_calculate_action(self, general_chat):
        """Test direct calculation action."""
        
        result = await general_chat.execute("calculate", {"expression": "2 + 2"})
        
        assert result["success"] == True
        assert "content" in result
        assert "4" in result["content"]
        assert result["result"] == 4
    
    @pytest.mark.asyncio
    async def test_convert_units_action(self, general_chat):
        """Test unit conversion action."""
        
        result = await general_chat.execute("convert_units", {
            "value": 1000,
            "from_unit": "m",
            "to_unit": "km"
        })
        
        assert result["success"] == True
        assert result["result"] == 1
        assert "1000 m = **1 km**" in result["content"]
    
    @pytest.mark.asyncio
    async def test_get_time_action(self, general_chat):
        """Test time retrieval action."""
        
        result = await general_chat.execute("get_time", {"format": "default"})
        
        assert result["success"] == True
        assert "Current time" in result["content"]
        assert result["timezone"] == "Europe/Zurich"
    
    @pytest.mark.asyncio
    async def test_builtin_tools_detection(self, general_chat):
        """Test built-in tools detection in text."""
        
        # Test calculation detection
        tool_result = await general_chat._try_builtin_tools("What's 5 + 3?")
        assert tool_result is not None
        assert "5 + 3 = 8" in tool_result
        
        # Test time detection
        tool_result = await general_chat._try_builtin_tools("What time is it?")
        assert tool_result is not None
        assert "Current time:" in tool_result
        
        # Test conversion detection
        tool_result = await general_chat._try_builtin_tools("Convert 100 cm to m")
        assert tool_result is not None
        assert "100 cm = 1 m" in tool_result
    
    @pytest.mark.asyncio
    async def test_basic_response_without_ai(self, general_chat):
        """Test basic response generation when AI is not available."""
        
        # Mock no OpenRouter key
        general_chat.config.OPENROUTER_API_KEY = None
        
        result = await general_chat._generate_basic_response("Hello", None)
        
        assert result["success"] == True
        assert "Hello!" in result["content"]
        assert result["provider"] == "builtin"
    
    @pytest.mark.asyncio
    async def test_health_check(self, general_chat):
        """Test module health check."""
        
        health = await general_chat.health_check()
        
        assert "status" in health
        assert "components" in health
        
        # Check individual components
        components = health["components"]
        assert "calculator" in components
        assert "time_helper" in components
        assert "unit_converter" in components
        
        # All components should be healthy
        assert components["calculator"]["status"] == "ok"
        assert components["time_helper"]["status"] == "ok"
        assert components["unit_converter"]["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_unknown_action(self, general_chat):
        """Test handling of unknown actions."""
        
        result = await general_chat.execute("unknown_action", {})
        
        assert result["success"] == False
        assert "Unknown action" in result["error"]
        assert "available_actions" in result


if __name__ == "__main__":
    pytest.main([__file__])
