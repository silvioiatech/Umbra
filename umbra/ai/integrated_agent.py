"""
Integrated AI Agent for UMBRA - Provider-agnostic with intent routing and module registry.
Combines deterministic routing, LLM fallback, and dynamic module discovery.
"""
import logging
from typing import Dict, Any, Optional

from .provider_agnostic import ProviderAgnosticAI
from .intent_router import IntentRouter
from ..core.module_registry import ModuleRegistry


class IntegratedAIAgent:
    """
    Integrated AI agent that combines:
    - Provider-agnostic AI interface
    - Deterministic intent routing with LLM fallback
    - Dynamic module discovery and execution
    """
    
    def __init__(self, config, db_manager, conversation_manager=None):
        self.config = config
        self.db_manager = db_manager
        self.conversation_manager = conversation_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize core components
        self.ai_provider = ProviderAgnosticAI(config)
        self.module_registry = ModuleRegistry(config, db_manager)
        self.intent_router = IntentRouter(config, self.ai_provider)
        
        # State
        self._initialized = False
        
        self.logger.info("🤖 Integrated AI Agent initialized")
    
    async def initialize(self) -> bool:
        """Initialize the AI agent and discover modules."""
        try:
            # Discover and load modules
            await self.module_registry.discover_modules()
            
            # Update intent router with discovered capabilities
            capabilities = self.module_registry.get_module_capabilities()
            self.intent_router.set_module_capabilities(capabilities)
            
            self._initialized = True
            
            # Log initialization summary
            modules = self.module_registry.get_all_modules()
            providers = self.ai_provider.get_available_providers()
            
            self.logger.info(f"✅ AI Agent ready:")
            self.logger.info(f"   📦 {len(modules)} modules loaded")
            self.logger.info(f"   🧠 AI providers: {providers if providers else 'Fallback mode'}")
            self.logger.info(f"   🧭 Intent routing: Deterministic + LLM fallback")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ AI Agent initialization failed: {e}")
            return False
    
    async def process_message(
        self, 
        user_id: int, 
        message: str, 
        user_name: str = "User",
        context: Optional[Dict] = None
    ) -> str:
        """Process user message with full AI agent capabilities."""
        
        if not self._initialized:
            await self.initialize()
        
        try:
            self.logger.info(f"📝 Processing message from {user_name}: '{message}'")
            
            # Route the intent
            intent = await self.intent_router.route_intent(message, context)
            
            self.logger.info(f"🎯 Routed to: {intent.module_id}.{intent.action} (confidence: {intent.confidence})")
            
            # Handle special cases
            if intent.module_id == 'help':
                return await self._handle_help_request(intent, message)
            
            # Execute the action on the appropriate module
            result = await self.module_registry.execute_action(
                intent.module_id, 
                intent.action, 
                intent.params
            )
            
            # Generate response based on result
            if result.get('success'):
                response = await self._generate_success_response(intent, result, message)
            else:
                response = await self._generate_error_response(intent, result, message)
            
            # Save conversation context if manager available
            if self.conversation_manager:
                await self._save_conversation_context(user_id, message, response, intent)
            
            return response
            
        except Exception as e:
            self.logger.error(f"❌ Error processing message: {e}")
            return f"I encountered an error while processing your request: {str(e)}"
    
    async def _handle_help_request(self, intent, original_message: str) -> str:
        """Handle help and capability requests."""
        if 'modules' in original_message.lower():
            # Show available modules
            modules = self.module_registry.list_modules()
            response = "🛠️ **Available Modules:**\n\n"
            
            for module_info in modules:
                response += f"**{module_info['module_id'].title()}**\n"
                capabilities = module_info['capabilities'][:3]  # Show first 3
                for cap in capabilities:
                    response += f"  • {cap}\n"
                response += "\n"
            
            response += "💡 Just tell me what you'd like to do in natural language!"
            return response
        
        # General help
        return ("👋 Hi! I'm Umbra, your AI assistant.\n\n"
               "I can help you with:\n"
               "• 🖥️ **System Management** - Check server status, manage services\n"
               "• 💰 **Finance** - Track expenses, create budgets, generate reports\n" 
               "• 🏢 **Business** - Manage clients, create instances, track projects\n"
               "• ⚙️ **Automation** - Create workflows, deploy automations\n"
               "• 🎨 **Content Creation** - Generate images, documents, and content\n\n"
               "Just tell me what you need! For example:\n"
               "• 'Check system status'\n"
               "• 'I spent $50 on groceries'\n"
               "• 'Create a client instance'\n"
               "• 'Generate a financial report'")
    
    async def _generate_success_response(self, intent, result: Dict, original_message: str) -> str:
        """Generate a natural response for successful execution."""
        
        # Try to use AI to generate natural response if available
        if self.ai_provider.is_ai_available():
            try:
                system_prompt = f"""Generate a natural, conversational response for a successful action.

Action executed: {intent.module_id}.{intent.action}
Original request: {original_message}
Result data: {result.get('data', {})}

Be conversational, helpful, and acknowledge what was accomplished. Keep it concise but informative."""

                messages = [{"role": "user", "content": f"The action was successful. Here's what happened: {result}"}]
                
                ai_response = await self.ai_provider.generate_response(
                    messages=messages,
                    system_prompt=system_prompt,
                    max_tokens=300,
                    temperature=0.7
                )
                
                if ai_response:
                    return ai_response
                    
            except Exception as e:
                self.logger.warning(f"AI response generation failed: {e}")
        
        # Fallback to structured response
        module_name = intent.module_id.title()
        action_name = intent.action.replace('_', ' ').title()
        
        response = f"✅ **{action_name} completed successfully**\n\n"
        
        # Add result data if available
        data = result.get('data')
        if data:
            if isinstance(data, str):
                response += data
            elif isinstance(data, dict):
                # Format key results
                for key, value in data.items():
                    if key not in ['success', 'module', 'action']:
                        response += f"• **{key.replace('_', ' ').title()}**: {value}\n"
            else:
                response += str(data)
        
        return response
    
    async def _generate_error_response(self, intent, result: Dict, original_message: str) -> str:
        """Generate response for failed execution."""
        error_msg = result.get('error', 'Unknown error occurred')
        
        # Check if it's a "module not found" error
        if 'not found' in error_msg.lower():
            available_modules = result.get('available_modules', [])
            response = f"❌ I couldn't find a module to handle that request.\n\n"
            if available_modules:
                response += f"Available modules: {', '.join(available_modules)}\n\n"
            response += "Try asking for help to see what I can do!"
            return response
        
        # Check if it's an "action not supported" error
        if 'not supported' in error_msg.lower():
            available_actions = result.get('available_actions', [])
            response = f"❌ That action isn't available in the {intent.module_id} module.\n\n"
            if available_actions:
                response += f"Available actions: {', '.join(available_actions[:5])}\n\n"
            response += "Try rephrasing your request or ask for help!"
            return response
        
        # Generic error response
        return f"❌ Sorry, I encountered an issue: {error_msg}\n\nCould you try rephrasing your request?"
    
    async def _save_conversation_context(self, user_id: int, message: str, response: str, intent):
        """Save conversation context for future reference."""
        try:
            if hasattr(self.conversation_manager, 'add_message'):
                await self.conversation_manager.add_message(user_id, 'user', message)
                await self.conversation_manager.add_message(user_id, 'assistant', response)
        except Exception as e:
            self.logger.warning(f"Failed to save conversation context: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the AI agent."""
        return {
            "initialized": self._initialized,
            "modules": self.module_registry.get_registry_stats(),
            "ai_providers": self.ai_provider.get_available_providers(),
            "routing": self.intent_router.get_routing_stats()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        return {
            "agent_status": "healthy" if self._initialized else "not_initialized",
            "modules": await self.module_registry.health_check_all(),
            "ai_providers": self.ai_provider.get_available_providers(),
            "timestamp": self._get_timestamp()
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()