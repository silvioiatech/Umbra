"""
Intent Router - F3R1: Enhanced rule-based routing with general_chat fallback.
Provides deterministic routing with AI-powered fallback via general_chat module.
"""
import re
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

from .core.logger import get_context_logger

logger = get_context_logger(__name__)

class RouteType(Enum):
    """Types of routing patterns."""
    EXACT_MATCH = "exact_match"
    REGEX_PATTERN = "regex_pattern"
    KEYWORD_MATCH = "keyword_match"
    COMMAND_PREFIX = "command_prefix"

@dataclass
class RoutePattern:
    """Represents a routing pattern."""
    pattern: str
    route_type: RouteType
    module: str
    action: str
    params_extractor: Optional[Callable] = None
    admin_only: bool = False
    description: str = ""

@dataclass
class RouteResult:
    """Result of route matching."""
    matched: bool
    module: Optional[str] = None
    action: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    pattern_used: Optional[str] = None
    requires_admin: bool = False

class UmbraRouter:
    """
    Intent router for deterministic command pattern matching.
    
    F3R1 Implementation: Rule-based routing with general_chat AI fallback.
    """
    
    def __init__(self):
        self.logger = get_context_logger(__name__)
        self.routes: List[RoutePattern] = []
        self.stats = {
            "total_requests": 0,
            "matched_requests": 0,
            "unmatched_requests": 0,
            "general_chat_fallbacks": 0,
            "pattern_usage": {}
        }
        
        # Initialize default routing patterns
        self._initialize_default_patterns()
        
        self.logger.info(
            "UmbraRouter F3R1 initialized",
            extra={
                "total_patterns": len(self.routes),
                "pattern_types": list(set(route.route_type.value for route in self.routes))
            }
        )
    
    def _initialize_default_patterns(self) -> None:
        """Initialize default routing patterns for F3/F3R1."""
        
        # System/Concierge patterns
        self.add_route(
            "/status", RouteType.EXACT_MATCH, "bot", "status",
            description="Show bot status"
        )
        
        self.add_route(
            "/help", RouteType.EXACT_MATCH, "bot", "help",
            description="Show help information"
        )
        
        # Concierge module patterns
        self.add_route(
            r"system status", RouteType.KEYWORD_MATCH, "concierge_mcp", "system_status",
            description="Get system status"
        )
        
        self.add_route(
            r"docker (status|ps|containers)", RouteType.REGEX_PATTERN, "concierge_mcp", "docker_status",
            description="Check Docker containers"
        )
        
        self.add_route(
            r"resource(s)? usage", RouteType.REGEX_PATTERN, "concierge_mcp", "resource_usage",
            description="Get resource usage"
        )
        
        self.add_route(
            r"execute (.+)", RouteType.REGEX_PATTERN, "concierge_mcp", "execute_command",
            params_extractor=lambda m: {"command": m.group(1)},
            admin_only=True,
            description="Execute shell command"
        )
        
        # Finance module patterns
        self.add_route(
            r"finance (status|summary)", RouteType.REGEX_PATTERN, "finance_mcp", "get_summary",
            description="Get financial summary"
        )
        
        self.add_route(
            r"upload (receipt|invoice)", RouteType.REGEX_PATTERN, "finance_mcp", "upload_document",
            description="Upload financial document"
        )
        
        # Business module patterns
        self.add_route(
            r"create instance (.+)", RouteType.REGEX_PATTERN, "business_mcp", "create_instance",
            params_extractor=lambda m: {"name": m.group(1)},
            admin_only=True,
            description="Create business instance"
        )
        
        self.add_route(
            r"list instances", RouteType.KEYWORD_MATCH, "business_mcp", "list_instances",
            description="List business instances"
        )
        
        # Creator module patterns
        self.add_route(
            r"create (image|video|audio) (.+)", RouteType.REGEX_PATTERN, "creator_mcp", "create_media",
            params_extractor=lambda m: {"type": m.group(1), "prompt": m.group(2)},
            description="Create media content"
        )
        
        # Production module patterns
        self.add_route(
            r"deploy (.+)", RouteType.REGEX_PATTERN, "production_mcp", "deploy",
            params_extractor=lambda m: {"target": m.group(1)},
            admin_only=True,
            description="Deploy to production"
        )
        
        # F3R1: Add patterns that should route to general_chat explicitly
        self.add_route(
            r"calculate (.+)", RouteType.REGEX_PATTERN, "general_chat_mcp", "calculate",
            params_extractor=lambda m: {"expression": m.group(1)},
            description="Perform calculations"
        )
        
        self.add_route(
            r"what time|current time|time now", RouteType.REGEX_PATTERN, "general_chat_mcp", "get_time",
            params_extractor=lambda m: {"format": "human"},
            description="Get current time"
        )
        
        self.add_route(
            r"convert (\d+(?:\.\d+)?)\s*([a-z]+)\s+(?:to|in|into)\s+([a-z]+)", 
            RouteType.REGEX_PATTERN, "general_chat_mcp", "convert_units",
            params_extractor=lambda m: {
                "value": float(m.group(1)),
                "from_unit": m.group(2),
                "to_unit": m.group(3)
            },
            description="Convert between units"
        )
        
        self.logger.info(
            "Default routing patterns initialized",
            extra={
                "total_patterns": len(self.routes),
                "admin_only_patterns": len([r for r in self.routes if r.admin_only])
            }
        )
    
    def add_route(
        self, 
        pattern: str, 
        route_type: RouteType, 
        module: str, 
        action: str,
        params_extractor: Optional[Callable] = None,
        admin_only: bool = False,
        description: str = ""
    ) -> None:
        """Add a new routing pattern."""
        
        route = RoutePattern(
            pattern=pattern,
            route_type=route_type,
            module=module,
            action=action,
            params_extractor=params_extractor,
            admin_only=admin_only,
            description=description
        )
        
        self.routes.append(route)
        
        self.logger.debug(
            "Route pattern added",
            extra={
                "pattern": pattern,
                "route_type": route_type.value,
                "module": module,
                "action": action,
                "admin_only": admin_only
            }
        )
    
    def route_message(self, message: str, user_id: int, is_admin: bool = False) -> RouteResult:
        """
        Route a message to appropriate module and action.
        
        Returns RouteResult with module, action, and parameters if matched.
        """
        
        self.stats["total_requests"] += 1
        
        message = message.strip()
        message_lower = message.lower()
        
        self.logger.debug(
            "Routing message",
            extra={
                "message_length": len(message),
                "user_id": user_id,
                "is_admin": is_admin
            }
        )
        
        # Try each routing pattern
        for route in self.routes:
            try:
                match_result = self._try_pattern_match(route, message, message_lower)
                
                if match_result.matched:
                    # Check admin requirements
                    if route.admin_only and not is_admin:
                        return RouteResult(
                            matched=False,
                            requires_admin=True,
                            pattern_used=route.pattern
                        )
                    
                    # Update statistics
                    self.stats["matched_requests"] += 1
                    pattern_key = f"{route.route_type.value}:{route.pattern}"
                    self.stats["pattern_usage"][pattern_key] = (
                        self.stats["pattern_usage"].get(pattern_key, 0) + 1
                    )
                    
                    self.logger.info(
                        "Message routed successfully",
                        extra={
                            "user_id": user_id,
                            "pattern": route.pattern,
                            "module": route.module,
                            "action": route.action,
                            "confidence": match_result.confidence
                        }
                    )
                    
                    return match_result
                    
            except Exception as e:
                self.logger.warning(
                    "Pattern matching error",
                    extra={
                        "pattern": route.pattern,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                continue
        
        # No match found
        self.stats["unmatched_requests"] += 1
        
        self.logger.debug(
            "No route match found - will try general_chat",
            extra={
                "user_id": user_id,
                "message_length": len(message)
            }
        )
        
        return RouteResult(matched=False)
    
    def _try_pattern_match(self, route: RoutePattern, message: str, message_lower: str) -> RouteResult:
        """Try to match a message against a specific route pattern."""
        
        if route.route_type == RouteType.EXACT_MATCH:
            if message.strip() == route.pattern:
                return RouteResult(
                    matched=True,
                    module=route.module,
                    action=route.action,
                    params={},
                    confidence=1.0,
                    pattern_used=route.pattern
                )
        
        elif route.route_type == RouteType.KEYWORD_MATCH:
            pattern_words = route.pattern.lower().split()
            if all(word in message_lower for word in pattern_words):
                return RouteResult(
                    matched=True,
                    module=route.module,
                    action=route.action,
                    params={},
                    confidence=0.8,
                    pattern_used=route.pattern
                )
        
        elif route.route_type == RouteType.REGEX_PATTERN:
            match = re.search(route.pattern, message_lower, re.IGNORECASE)
            if match:
                params = {}
                if route.params_extractor:
                    try:
                        params = route.params_extractor(match) or {}
                    except Exception as e:
                        self.logger.warning(
                            "Parameter extraction failed",
                            extra={
                                "pattern": route.pattern,
                                "error": str(e)
                            }
                        )
                
                return RouteResult(
                    matched=True,
                    module=route.module,
                    action=route.action,
                    params=params,
                    confidence=0.9,
                    pattern_used=route.pattern
                )
        
        elif route.route_type == RouteType.COMMAND_PREFIX:
            if message.startswith(route.pattern):
                remainder = message[len(route.pattern):].strip()
                params = {"args": remainder} if remainder else {}
                
                return RouteResult(
                    matched=True,
                    module=route.module,
                    action=route.action,
                    params=params,
                    confidence=0.95,
                    pattern_used=route.pattern
                )
        
        return RouteResult(matched=False)
    
    async def route_to_general_chat(self, message: str, user_id: int, module_registry) -> Optional[str]:
        """
        F3R1: Route unmatched messages to general_chat module.
        """
        
        try:
            self.stats["general_chat_fallbacks"] += 1
            
            # Execute general_chat.ask action
            result = await module_registry.execute_module_action(
                "general_chat_mcp",
                "ask",
                {
                    "text": message,
                    "use_tools": True,
                    "user_id": user_id
                },
                user_id
            )
            
            if result["success"]:
                content = None
                if isinstance(result["result"], dict):
                    content = result["result"].get("content", str(result["result"]))
                else:
                    content = str(result["result"])
                
                self.logger.info(
                    "General chat routing successful",
                    extra={
                        "user_id": user_id,
                        "response_length": len(content) if content else 0,
                        "provider": result["result"].get("provider") if isinstance(result["result"], dict) else None
                    }
                )
                
                return content
            else:
                self.logger.warning(
                    "General chat failed",
                    extra={
                        "error": result.get("error"),
                        "user_id": user_id
                    }
                )
                return None
                
        except Exception as e:
            self.logger.error(
                "General chat routing failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "user_id": user_id
                }
            )
            return None
    
    def get_fallback_response(self, message: str, user_id: int) -> str:
        """
        F3R1: Fallback response when general_chat is not available.
        This should rarely be used since general_chat handles most cases.
        """
        
        fallback_response = (
            f"I understand you're asking about: '{message[:100]}{'...' if len(message) > 100 else ''}'\n\n"
            "🤖 **F3R1 Mode**: Enhanced routing with AI conversation.\n\n"
            "**Available Commands:**\n"
            "• `/status` - Bot status\n"
            "• `/help` - Available commands\n"
            "• `system status` - VPS status\n"
            "• `docker status` - Container status\n"
            "• `resource usage` - System resources\n\n"
            "**AI Chat**: I can now understand natural language!\n"
            "_Try asking calculations, questions, or just chat naturally._"
        )
        
        return fallback_response
    
    def get_available_patterns(self, admin_only: bool = False) -> List[Dict[str, Any]]:
        """Get list of available routing patterns."""
        
        patterns = []
        for route in self.routes:
            if admin_only and not route.admin_only:
                continue
            
            patterns.append({
                "pattern": route.pattern,
                "type": route.route_type.value,
                "module": route.module,
                "action": route.action,
                "admin_only": route.admin_only,
                "description": route.description,
                "usage_count": self.stats["pattern_usage"].get(
                    f"{route.route_type.value}:{route.pattern}", 0
                )
            })
        
        return patterns
    
    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics (F3R1 enhanced)."""
        
        match_rate = (
            self.stats["matched_requests"] / self.stats["total_requests"]
            if self.stats["total_requests"] > 0 else 0
        )
        
        return {
            "total_requests": self.stats["total_requests"],
            "matched_requests": self.stats["matched_requests"],
            "unmatched_requests": self.stats["unmatched_requests"],
            "general_chat_fallbacks": self.stats["general_chat_fallbacks"],
            "match_rate": round(match_rate * 100, 2),
            "total_patterns": len(self.routes),
            "admin_patterns": len([r for r in self.routes if r.admin_only]),
            "most_used_patterns": sorted(
                self.stats["pattern_usage"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }
    
    def reset_stats(self) -> None:
        """Reset routing statistics."""
        self.stats = {
            "total_requests": 0,
            "matched_requests": 0,
            "unmatched_requests": 0,
            "general_chat_fallbacks": 0,
            "pattern_usage": {}
        }
        
        self.logger.info("Router statistics reset")

# Export
__all__ = ["UmbraRouter", "RouteResult", "RoutePattern", "RouteType"]
