"""
General Chat MCP - F3R1: General conversation with built-in tools.
Handles ChatGPT-style questions with calculator, units, time, and table tools.
"""
import re
import math
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..core.logger import get_context_logger
from ..core.config import config

logger = get_context_logger(__name__)

@dataclass
class ToolResult:
    """Result from a built-in tool execution."""
    success: bool
    result: Any
    error: Optional[str] = None

class Calculator:
    """Safe calculator with basic math operations."""
    
    # Allowed functions and constants
    SAFE_FUNCTIONS = {
        'abs', 'round', 'min', 'max', 'sum',
        'sin', 'cos', 'tan', 'asin', 'acos', 'atan',
        'sinh', 'cosh', 'tanh', 'asinh', 'acosh', 'atanh',
        'exp', 'log', 'log10', 'log2', 'sqrt', 'pow',
        'ceil', 'floor', 'degrees', 'radians',
        'pi', 'e'
    }
    
    def __init__(self):
        # Build safe namespace
        self.namespace = {
            '__builtins__': {},
            'abs': abs, 'round': round, 'min': min, 'max': max, 'sum': sum,
            'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
            'asin': math.asin, 'acos': math.acos, 'atan': math.atan,
            'sinh': math.sinh, 'cosh': math.cosh, 'tanh': math.tanh,
            'asinh': math.asinh, 'acosh': math.acosh, 'atanh': math.atanh,
            'exp': math.exp, 'log': math.log, 'log10': math.log10, 'log2': math.log2,
            'sqrt': math.sqrt, 'pow': pow,
            'ceil': math.ceil, 'floor': math.floor,
            'degrees': math.degrees, 'radians': math.radians,
            'pi': math.pi, 'e': math.e
        }
    
    def evaluate(self, expression: str) -> ToolResult:
        """Safely evaluate mathematical expression."""
        try:
            # Clean the expression
            expression = expression.strip()
            
            # Basic security checks
            if any(dangerous in expression for dangerous in ['import', 'exec', 'eval', '__']):
                return ToolResult(False, None, "Potentially unsafe expression")
            
            # Remove any whitespace and normalize
            expression = re.sub(r'\s+', ' ', expression)
            
            # Evaluate safely
            result = eval(expression, self.namespace)
            
            # Format result nicely
            if isinstance(result, float):
                # Round to reasonable precision
                if abs(result) < 1e-10:
                    result = 0.0
                elif result == int(result):
                    result = int(result)
                else:
                    result = round(result, 10)
            
            return ToolResult(True, result)
            
        except ZeroDivisionError:
            return ToolResult(False, None, "Division by zero")
        except ValueError as e:
            return ToolResult(False, None, f"Math error: {str(e)}")
        except SyntaxError:
            return ToolResult(False, None, "Invalid mathematical expression")
        except Exception as e:
            return ToolResult(False, None, f"Calculation error: {str(e)}")

class UnitConverter:
    """Basic unit conversion utilities."""
    
    CONVERSIONS = {
        # Length
        'mm_to_cm': 0.1,
        'cm_to_m': 0.01,
        'm_to_km': 0.001,
        'inch_to_cm': 2.54,
        'ft_to_m': 0.3048,
        'mile_to_km': 1.609344,
        
        # Weight/Mass
        'g_to_kg': 0.001,
        'kg_to_lb': 2.20462,
        'oz_to_g': 28.3495,
        
        # Temperature (special handling needed)
        'c_to_f': lambda c: c * 9/5 + 32,
        'f_to_c': lambda f: (f - 32) * 5/9,
        'c_to_k': lambda c: c + 273.15,
        'k_to_c': lambda k: k - 273.15,
        
        # Volume
        'ml_to_l': 0.001,
        'l_to_gal': 0.264172,
        'cup_to_ml': 236.588,
        
        # Currency (placeholder - would need API for real rates)
        'eur_to_chf': 1.08,  # Approximate
        'usd_to_chf': 0.92,  # Approximate
        'gbp_to_chf': 1.15,  # Approximate
    }
    
    def convert(self, value: float, from_unit: str, to_unit: str) -> ToolResult:
        """Convert between units."""
        try:
            conversion_key = f"{from_unit.lower()}_to_{to_unit.lower()}"
            
            if conversion_key in self.CONVERSIONS:
                converter = self.CONVERSIONS[conversion_key]
                
                if callable(converter):
                    result = converter(value)
                else:
                    result = value * converter
                
                return ToolResult(True, round(result, 6))
            
            # Try reverse conversion
            reverse_key = f"{to_unit.lower()}_to_{from_unit.lower()}"
            if reverse_key in self.CONVERSIONS:
                converter = self.CONVERSIONS[reverse_key]
                
                if callable(converter):
                    # Can't easily reverse lambda functions
                    return ToolResult(False, None, "Reverse conversion not supported for this unit pair")
                else:
                    result = value / converter
                
                return ToolResult(True, round(result, 6))
            
            return ToolResult(False, None, f"Conversion from {from_unit} to {to_unit} not supported")
            
        except Exception as e:
            return ToolResult(False, None, f"Conversion error: {str(e)}")

class TimeHelper:
    """Time utilities with Europe/Zurich timezone support."""
    
    def __init__(self):
        self.timezone_name = getattr(config, 'LOCALE_TZ', 'Europe/Zurich')
    
    def get_current_time(self, format_type: str = "default") -> ToolResult:
        """Get current time in various formats."""
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(self.timezone_name)
            now = datetime.now(tz)
            
            if format_type == "iso":
                result = now.isoformat()
            elif format_type == "timestamp":
                result = now.timestamp()
            elif format_type == "human":
                result = now.strftime("%A, %B %d, %Y at %H:%M:%S %Z")
            elif format_type == "time":
                result = now.strftime("%H:%M:%S")
            elif format_type == "date":
                result = now.strftime("%Y-%m-%d")
            else:  # default
                result = now.strftime("%Y-%m-%d %H:%M:%S %Z")
            
            return ToolResult(True, result)
            
        except Exception as e:
            # Fallback to UTC if timezone fails
            try:
                now = datetime.now(timezone.utc)
                result = now.strftime("%Y-%m-%d %H:%M:%S UTC")
                return ToolResult(True, result)
            except Exception:
                return ToolResult(False, None, f"Time error: {str(e)}")
    
    def parse_duration(self, duration_str: str) -> ToolResult:
        """Parse duration string and convert to seconds."""
        try:
            duration_str = duration_str.lower().strip()
            
            # Parse patterns like "2h 30m", "1d 3h", "45s"
            total_seconds = 0
            
            # Days
            days_match = re.search(r'(\d+(?:\.\d+)?)\s*d(?:ays?)?', duration_str)
            if days_match:
                total_seconds += float(days_match.group(1)) * 86400
            
            # Hours  
            hours_match = re.search(r'(\d+(?:\.\d+)?)\s*h(?:ours?)?', duration_str)
            if hours_match:
                total_seconds += float(hours_match.group(1)) * 3600
            
            # Minutes
            minutes_match = re.search(r'(\d+(?:\.\d+)?)\s*m(?:inutes?)?', duration_str)
            if minutes_match:
                total_seconds += float(minutes_match.group(1)) * 60
            
            # Seconds
            seconds_match = re.search(r'(\d+(?:\.\d+)?)\s*s(?:econds?)?', duration_str)
            if seconds_match:
                total_seconds += float(seconds_match.group(1))
            
            if total_seconds == 0:
                return ToolResult(False, None, "Could not parse duration")
            
            return ToolResult(True, total_seconds)
            
        except Exception as e:
            return ToolResult(False, None, f"Duration parsing error: {str(e)}")

class TableFormatter:
    """Simple table formatting utilities."""
    
    def create_table(self, data: List[List[str]], headers: Optional[List[str]] = None) -> ToolResult:
        """Create a simple text table."""
        try:
            if not data:
                return ToolResult(False, None, "No data provided")
            
            # Ensure all rows have same length
            max_cols = max(len(row) for row in data)
            normalized_data = [row + [''] * (max_cols - len(row)) for row in data]
            
            # Add headers if provided
            if headers:
                headers = headers + [''] * (max_cols - len(headers))
                normalized_data.insert(0, headers)
            
            # Calculate column widths
            col_widths = []
            for col in range(max_cols):
                max_width = max(len(str(row[col])) for row in normalized_data)
                col_widths.append(max(max_width, 3))  # Minimum width of 3
            
            # Build table
            lines = []
            for i, row in enumerate(normalized_data):
                line = "| "
                for j, cell in enumerate(row):
                    line += str(cell).ljust(col_widths[j]) + " | "
                lines.append(line)
                
                # Add separator after headers
                if headers and i == 0:
                    separator = "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"
                    lines.append(separator)
            
            result = "\n".join(lines)
            return ToolResult(True, result)
            
        except Exception as e:
            return ToolResult(False, None, f"Table formatting error: {str(e)}")

class GeneralChatMCP:
    """General Chat MCP module with built-in tools."""
    
    def __init__(self, config=None, db_manager=None):
        self.config = config or globals()['config']
        self.db_manager = db_manager
        self.logger = get_context_logger(__name__)
        
        # Initialize tools
        self.calculator = Calculator()
        self.unit_converter = UnitConverter()
        self.time_helper = TimeHelper()
        self.table_formatter = TableFormatter()
        
        self.logger.info(
            "General Chat MCP initialized",
            extra={
                "tools": ["calculator", "unit_converter", "time_helper", "table_formatter"],
                "timezone": self.time_helper.timezone_name
            }
        )
    
    async def get_capabilities(self) -> Dict[str, Any]:
        """Get capabilities exposed by General Chat module."""
        return {
            "ask": {
                "description": "Ask general questions with built-in tool support",
                "parameters": {
                    "text": {"type": "string", "description": "Question or request"},
                    "use_tools": {"type": "boolean", "description": "Enable built-in tools", "default": True}
                },
                "admin_only": False
            },
            "calculate": {
                "description": "Perform mathematical calculations",
                "parameters": {
                    "expression": {"type": "string", "description": "Mathematical expression"}
                },
                "admin_only": False
            },
            "convert_units": {
                "description": "Convert between units",
                "parameters": {
                    "value": {"type": "number", "description": "Value to convert"},
                    "from_unit": {"type": "string", "description": "Source unit"},
                    "to_unit": {"type": "string", "description": "Target unit"}
                },
                "admin_only": False
            },
            "get_time": {
                "description": "Get current time in various formats",
                "parameters": {
                    "format": {"type": "string", "description": "Format: default, iso, timestamp, human, time, date"}
                },
                "admin_only": False
            }
        }
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action with parameters."""
        
        if action == "ask":
            return await self._handle_ask(params)
        elif action == "calculate":
            return await self._handle_calculate(params)
        elif action == "convert_units":
            return await self._handle_convert_units(params)
        elif action == "get_time":
            return await self._handle_get_time(params)
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "available_actions": ["ask", "calculate", "convert_units", "get_time"]
            }
    
    async def _handle_ask(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general questions with AI and tool integration."""
        
        text = params.get("text", "").strip()
        use_tools = params.get("use_tools", True)
        
        if not text:
            return {
                "success": False,
                "error": "No question provided"
            }
        
        try:
            # Check if we need to use built-in tools first
            tool_result = None
            
            if use_tools:
                tool_result = await self._try_builtin_tools(text)
            
            # Get AI agent for response generation
            from ..ai.agent import UmbraAIAgent
            from ..providers.openrouter import OpenRouterProvider
            
            # Check if we have OpenRouter configured
            if hasattr(self.config, 'OPENROUTER_API_KEY') and self.config.OPENROUTER_API_KEY:
                ai_agent = UmbraAIAgent(self.config)
                
                # Register OpenRouter provider if not already done
                openrouter_provider = OpenRouterProvider(self.config)
                if openrouter_provider.is_available():
                    ai_agent.register_provider("openrouter", openrouter_provider)
                
                # Build context
                context = {
                    "timezone": self.time_helper.timezone_name,
                    "tools_available": True
                }
                
                # Add tool result to context if available
                if tool_result:
                    context["tool_result"] = tool_result
                    text = f"{text}\n\nTool result: {tool_result}"
                
                # Generate AI response
                ai_response = await ai_agent.generate_response(
                    message=text,
                    user_id=params.get("user_id", 0),
                    context=context,
                    temperature=0.7,
                    max_tokens=800
                )
                
                if ai_response.success:
                    return {
                        "success": True,
                        "content": ai_response.content,
                        "provider": ai_response.provider,
                        "model": ai_response.model,
                        "tool_used": tool_result is not None
                    }
                else:
                    # Fall back to basic response if AI fails
                    return await self._generate_basic_response(text, tool_result)
            
            else:
                # No AI available, use basic response
                return await self._generate_basic_response(text, tool_result)
                
        except Exception as e:
            self.logger.error(
                "General chat error",
                extra={
                    "error": str(e),
                    "text_length": len(text)
                }
            )
            
            return {
                "success": False,
                "error": f"Failed to process question: {str(e)}"
            }
    
    async def _try_builtin_tools(self, text: str) -> Optional[str]:
        """Try to use built-in tools for the query."""
        
        text_lower = text.lower()
        
        # Calculator patterns
        calc_patterns = [
            r'calculate|compute|math|=|\+|\-|\*|\/|\^|\bsin\b|\bcos\b|\btan\b|\bsqrt\b|\blog\b',
            r'\d+\s*[\+\-\*\/\^]\s*\d+',
            r'what\s+is\s+\d+.*[\+\-\*\/]',
            r'how\s+much\s+is\s+\d+'
        ]
        
        if any(re.search(pattern, text_lower) for pattern in calc_patterns):
            # Extract mathematical expression
            math_match = re.search(r'([0-9+\-*/^().\s]+(?:sin|cos|tan|sqrt|log|pi|e|abs|round|min|max|pow|exp)[0-9+\-*/^().\s]*|[0-9+\-*/^().e\s]+)', text)
            if math_match:
                expression = math_match.group(1).strip()
                calc_result = self.calculator.evaluate(expression)
                if calc_result.success:
                    return f"Calculation: {expression} = {calc_result.result}"
        
        # Time patterns
        time_patterns = [
            r'what\s+time|current\s+time|time\s+now|what\s+is\s+the\s+time',
            r'today|date|when\s+is\s+it'
        ]
        
        if any(re.search(pattern, text_lower) for pattern in time_patterns):
            if 'date' in text_lower or 'today' in text_lower:
                time_result = self.time_helper.get_current_time("human")
            else:
                time_result = self.time_helper.get_current_time("default")
            
            if time_result.success:
                return f"Current time: {time_result.result}"
        
        # Unit conversion patterns
        convert_patterns = [
            r'convert|conversion|how\s+many',
            r'\d+\s*(mm|cm|m|km|inch|ft|mile|g|kg|lb|oz|c|f|k|ml|l|gal|cup|eur|usd|gbp|chf)'
        ]
        
        if any(re.search(pattern, text_lower) for pattern in convert_patterns):
            # Try to extract conversion request
            convert_match = re.search(r'(\d+(?:\.\d+)?)\s*([a-z]+)\s+(?:to|in|into)\s+([a-z]+)', text_lower)
            if convert_match:
                value = float(convert_match.group(1))
                from_unit = convert_match.group(2)
                to_unit = convert_match.group(3)
                
                convert_result = self.unit_converter.convert(value, from_unit, to_unit)
                if convert_result.success:
                    return f"Conversion: {value} {from_unit} = {convert_result.result} {to_unit}"
        
        return None
    
    async def _generate_basic_response(self, text: str, tool_result: Optional[str]) -> Dict[str, Any]:
        """Generate basic response when AI is not available."""
        
        if tool_result:
            response = f"{tool_result}\n\nIs there anything else I can help you calculate or look up?"
        else:
            # Basic pattern responses
            text_lower = text.lower()
            
            if any(word in text_lower for word in ['hello', 'hi', 'hey']):
                response = "Hello! I'm here to help with calculations, time, unit conversions, and general questions."
            elif any(word in text_lower for word in ['help', 'what can you do']):
                response = (
                    "I can help with:\n"
                    "• Mathematical calculations\n"
                    "• Unit conversions (length, weight, temperature, etc.)\n"
                    "• Current time and date\n"
                    "• General questions (with AI when available)\n\n"
                    "Try asking: 'What's 2+2?', 'Convert 10 km to miles', or 'What time is it?'"
                )
            elif any(word in text_lower for word in ['thanks', 'thank you']):
                response = "You're welcome! Feel free to ask me anything else."
            else:
                response = (
                    f"I understand you're asking: '{text}'\n\n"
                    "I'm currently in basic mode. I can help with calculations, "
                    "unit conversions, and time queries. For full AI conversation, "
                    "ensure OpenRouter is configured with OPENROUTER_API_KEY."
                )
        
        return {
            "success": True,
            "content": response,
            "provider": "builtin",
            "tool_used": tool_result is not None
        }
    
    async def _handle_calculate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle direct calculation requests."""
        
        expression = params.get("expression", "").strip()
        
        if not expression:
            return {
                "success": False,
                "error": "No expression provided"
            }
        
        result = self.calculator.evaluate(expression)
        
        if result.success:
            return {
                "success": True,
                "content": f"**Calculation:** {expression} = **{result.result}**",
                "result": result.result,
                "expression": expression
            }
        else:
            return {
                "success": False,
                "error": result.error or "Calculation failed"
            }
    
    async def _handle_convert_units(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle unit conversion requests."""
        
        try:
            value = float(params.get("value", 0))
            from_unit = params.get("from_unit", "").strip()
            to_unit = params.get("to_unit", "").strip()
            
            if not from_unit or not to_unit:
                return {
                    "success": False,
                    "error": "Both from_unit and to_unit must be specified"
                }
            
            result = self.unit_converter.convert(value, from_unit, to_unit)
            
            if result.success:
                return {
                    "success": True,
                    "content": f"**Conversion:** {value} {from_unit} = **{result.result} {to_unit}**",
                    "result": result.result,
                    "original_value": value,
                    "from_unit": from_unit,
                    "to_unit": to_unit
                }
            else:
                return {
                    "success": False,
                    "error": result.error or "Conversion failed"
                }
                
        except ValueError:
            return {
                "success": False,
                "error": "Invalid value for conversion"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Conversion error: {str(e)}"
            }
    
    async def _handle_get_time(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle time queries."""
        
        format_type = params.get("format", "default")
        
        result = self.time_helper.get_current_time(format_type)
        
        if result.success:
            return {
                "success": True,
                "content": f"**Current time ({format_type}):** {result.result}",
                "time": result.result,
                "format": format_type,
                "timezone": self.time_helper.timezone_name
            }
        else:
            return {
                "success": False,
                "error": result.error or "Failed to get time"
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the General Chat module."""
        
        checks = {}
        
        # Test calculator
        calc_test = self.calculator.evaluate("2 + 2")
        checks["calculator"] = {
            "status": "ok" if calc_test.success and calc_test.result == 4 else "error",
            "details": "Basic arithmetic working" if calc_test.success else calc_test.error
        }
        
        # Test time helper
        time_test = self.time_helper.get_current_time()
        checks["time_helper"] = {
            "status": "ok" if time_test.success else "error",
            "details": f"Timezone: {self.time_helper.timezone_name}" if time_test.success else time_test.error
        }
        
        # Test unit converter
        unit_test = self.unit_converter.convert(1, "m", "cm")
        checks["unit_converter"] = {
            "status": "ok" if unit_test.success and unit_test.result == 100 else "error",
            "details": "Basic conversions working" if unit_test.success else unit_test.error
        }
        
        # Overall status
        all_ok = all(check["status"] == "ok" for check in checks.values())
        
        return {
            "status": "healthy" if all_ok else "degraded",
            "components": checks,
            "tools_available": len([c for c in checks.values() if c["status"] == "ok"])
        }

# Export
__all__ = ["GeneralChatMCP"]
