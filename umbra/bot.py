"""
Umbra Bot - Claude Desktop-style AI with MCP-like modules
Natural conversation that intelligently uses specialized tools
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from .core.config import config
from .core.logging_mw import logging_middleware, get_structured_logger
from .core.metrics import metrics
from .core.audit import audit_logger
from .core.rbac import Module, Action
from .core.web_server import metrics_server

class UmbraAIAgent:
    """Claude Desktop-style AI agent with MCP-like module integration."""
    
    def __init__(self, config_obj=None):
        self.config = config_obj or config
        self.logger = get_structured_logger(__name__)
        self.application: Optional[Application] = None
        
        # Track start time for uptime
        self.start_time = time.time()
        
        # Initialize core systems
        self._init_systems()
        
        # Initialize AI as primary interface (like Claude Desktop)
        self._init_ai_agent()
        
        # Initialize MCP-style modules
        self._init_mcp_modules()
        
        # Initialize metrics server
        self._init_metrics_server()
    
    def _init_systems(self):
        """Initialize core systems."""
        try:
            from .core.permissions import PermissionManager
            from .storage.database import DatabaseManager
            from .storage.conversation import ConversationManager
            
            self.permission_manager = PermissionManager()
            self.db_manager = DatabaseManager(self.config.DATABASE_PATH)
            self.conversation_manager = ConversationManager(self.db_manager)
            
            # Initialize metrics with active user counts
            self._update_user_metrics()
            
            self.logger.info("✅ Core systems initialized")
            
        except Exception as e:
            self.logger.error(f"❌ Core systems error: {e}")
            raise
    
    def _update_user_metrics(self):
        """Update user metrics for monitoring."""
        try:
            role_counts = {}
            for user_id in self.permission_manager.allowed_users:
                role = self.permission_manager.get_user_role(user_id)
                role_counts[role] = role_counts.get(role, 0) + 1
            
            metrics.update_active_users(role_counts)
        except Exception as e:
            self.logger.error(f"Error updating user metrics: {e}")
    
    def _init_metrics_server(self):
        """Initialize metrics server."""
        try:
            # Configure metrics server port from config if available
            port = getattr(self.config, 'METRICS_PORT', 8080)
            if hasattr(self.config, 'PORT') and self.config.PORT:
                # Use bot port + 1 for metrics if bot port is configured
                try:
                    port = int(self.config.PORT) + 1
                except (ValueError, TypeError):
                    port = 8080
            
            metrics_server.port = port
            self.logger.info(f"Metrics server configured for port {port}")
        except Exception as e:
            self.logger.error(f"Error configuring metrics server: {e}")
    
    def _init_ai_agent(self):
        """Initialize Claude Desktop-style AI agent."""
        try:
            from .ai.claude_agent import ClaudeStyleAgent
            self.ai_agent = ClaudeStyleAgent(self.config, self.conversation_manager)
            
            if self.config.OPENROUTER_API_KEY:
                self.logger.info("🤖 Claude Desktop-style AI initialized with full capabilities")
            else:
                self.logger.info("🤖 AI initialized in pattern mode (add OPENROUTER_API_KEY for full AI)")
                
        except Exception as e:
            self.logger.warning(f"⚠️ AI initialization failed: {e}")
            self.ai_agent = None
    
    def _init_mcp_modules(self):
        """Initialize MCP-style modules."""
        self.modules = {}
        
        module_configs = {
            'concierge': {
                'name': 'VPS Manager',
                'capabilities': [
                    'System monitoring (CPU, RAM, disk, network)',
                    'Docker container management',
                    'Service control (start/stop/restart)',
                    'Package management',
                    'Log analysis',
                    'Process management',
                    'Firewall configuration',
                    'Backup operations',
                    'SSH command execution',
                    'File system operations'
                ]
            },
            'finance': {
                'name': 'Personal Accountant',
                'capabilities': [
                    'Expense tracking and categorization',
                    'Budget management with alerts',
                    'Financial reports and analytics',
                    'Receipt OCR and storage',
                    'Cloudflare R2 integration (future)',
                    'Tax preparation assistance',
                    'Investment tracking',
                    'Cash flow analysis'
                ]
            },
            'business': {
                'name': 'Business Manager',
                'capabilities': [
                    'Create client VPS instances',
                    'Client database management',
                    'Project tracking',
                    'Invoice generation',
                    'Resource allocation',
                    'Usage monitoring per client',
                    'Automated onboarding',
                    'Business KPIs'
                ]
            },
            'production': {
                'name': 'n8n Workflow Creator',
                'capabilities': [
                    'Create n8n workflows via MCP API',
                    'Deploy automation workflows',
                    'Monitor workflow execution',
                    'Manage workflow schedules',
                    'Integration with n8n MCP',
                    'Workflow templates',
                    'Error handling and alerts'
                ]
            },
            'creator': {
                'name': 'Content Creator',
                'capabilities': [
                    'Video creation via APIs',
                    'Document generation',
                    'Image creation (DALL-E, Stable Diffusion)',
                    'Code generation',
                    'File format conversions',
                    'Template management',
                    'Multi-API orchestration'
                ]
            }
        }
        
        for module_id, config in module_configs.items():
            try:
                module = self._load_mcp_module(module_id, config)
                if module:
                    self.modules[module_id] = module
                    self.logger.info(f"✅ MCP Module loaded: {config['name']}")
            except Exception as e:
                self.logger.warning(f"⚠️ {config['name']} module failed: {e}")
        
        self.logger.info(f"🛠️ {len(self.modules)} MCP modules ready")
    
    def _load_mcp_module(self, module_id: str, config: Dict) -> Optional[Dict]:
        """Load a module as MCP server."""
        try:
            if module_id == 'concierge':
                from .modules.concierge_mcp import ConciergeMCP
                module = ConciergeMCP(self.config, self.db_manager)
            elif module_id == 'finance':
                from .modules.finance_mcp import FinanceMCP
                module = FinanceMCP(self.config, self.db_manager)
            elif module_id == 'business':
                from .modules.business_mcp import BusinessMCP
                module = BusinessMCP(self.config, self.db_manager)
            elif module_id == 'production':
                from .modules.production_mcp import ProductionMCP
                module = ProductionMCP(self.config, self.db_manager)
            elif module_id == 'creator':
                from .modules.creator_mcp import CreatorMCP
                module = CreatorMCP(self.config, self.db_manager)
            else:
                return None
            
            return {
                'id': module_id,
                'name': config['name'],
                'capabilities': config['capabilities'],
                'module': module
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to load {module_id}: {e}")
            return None
    
    async def start(self) -> None:
        """Start the Claude Desktop-style bot."""
        try:
            self.logger.info("🤖 Starting Umbra (Claude Desktop mode)...")
            
            # Start metrics server first
            await metrics_server.start()
            
            # Create Telegram application
            self.application = Application.builder().token(self.config.TELEGRAM_BOT_TOKEN).build()
            
            # Register handlers
            await self._register_handlers()
            
            # Start application
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)
            
            # Log system startup
            audit_logger.log_event(
                user_id=0,  # System user
                module="system",
                action="bot_start",
                details={
                    "modules_loaded": len(self.modules),
                    "metrics_port": metrics_server.port
                }
            )
            
            self.logger.info("✅ Umbra started - Ready for natural conversation")
            self.logger.info(f"📊 Metrics available at http://localhost:{metrics_server.port}/metrics")
            
            # Keep running
            await self._run_forever()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start: {e}")
            audit_logger.log_error(
                user_id=0,
                module="system", 
                action="bot_start",
                error_type=type(e).__name__,
                error_message=str(e)
            )
            raise
        finally:
            await self.shutdown()
    
    async def _run_forever(self):
        """Keep the bot running."""
        try:
            stop_event = asyncio.Event()
            await stop_event.wait()
        except KeyboardInterrupt:
            self.logger.info("Stopped by user")
    
    async def shutdown(self) -> None:
        """Graceful shutdown."""
        self.logger.info("🛑 Shutting down...")
        
        # Log shutdown
        audit_logger.log_event(
            user_id=0,
            module="system",
            action="bot_shutdown",
            details={"uptime_seconds": time.time() - self.start_time}
        )
        
        # Stop metrics server
        try:
            await metrics_server.stop()
        except Exception as e:
            self.logger.warning(f"Metrics server shutdown warning: {e}")
        
        # Stop Telegram application
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                self.logger.warning(f"Application shutdown warning: {e}")
        
        self.logger.info("✅ Shutdown complete")
    
    async def _register_handlers(self) -> None:
        """Register handlers for natural conversation."""
        if not self.application:
            raise RuntimeError("Application not initialized")
        
        # Essential commands
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("modules", self._handle_modules))
        
        # All messages go to Claude-style AI
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_conversation)
        )
        
        self.logger.info("✅ Handlers registered")
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Welcome message - Claude Desktop style."""
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name or "there"
        
        # Use logging middleware and audit
        with logging_middleware.log_request(user_id, "system", "start"):
            if not self.permission_manager.is_user_allowed(user_id):
                # Log unauthorized access attempt
                audit_logger.log_access_attempt(
                    user_id=user_id,
                    module="system",
                    action="start",
                    granted=False,
                    reason="User not in allowed list"
                )
                metrics.record_permission_check("system", "start", "denied")
                await update.message.reply_text("❌ Unauthorized. Add your ID to ALLOWED_USER_IDS.")
                return
            
            # Log successful access
            audit_logger.log_access_attempt(
                user_id=user_id,
                module="system", 
                action="start",
                granted=True
            )
            metrics.record_permission_check("system", "start", "granted")
            
            # Add user to database
            self.db_manager.add_user(
                user_id, 
                update.effective_user.username, 
                first_name, 
                update.effective_user.last_name
            )
            
            # Log user activity
            audit_logger.log_event(
                user_id=user_id,
                module="system",
                action="start_session",
                details={"username": update.effective_user.username}
            )
            
            welcome = f"""Hi {first_name}! I'm Umbra, your AI assistant with specialized capabilities.

I work like Claude Desktop - just chat naturally and I'll use my modules when needed:

**🖥️ VPS Manager** - Monitor system, manage Docker, execute commands
**💰 Personal Accountant** - Track expenses, manage budgets, financial reports  
**🏢 Business Manager** - Create client instances, manage projects
**⚙️ n8n Workflows** - Create and deploy automation via MCP
**🎨 Content Creator** - Generate videos, images, documents

Just tell me what you need! Examples:
• "Check my server status"
• "I spent $50 on groceries"
• "Create a new client instance for John"
• "Generate an image of a sunset"
• "Create an n8n workflow for daily backups"

I understand English, French, and Portuguese. How can I help you today?"""

        await update.message.reply_text(welcome, parse_mode='Markdown')
    
    async def _handle_modules(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show available MCP modules."""
        user_id = update.effective_user.id
        
        with logging_middleware.log_request(user_id, "system", "list_modules"):
            if not self.permission_manager.is_user_allowed(user_id):
                audit_logger.log_access_attempt(
                    user_id=user_id,
                    module="system",
                    action="list_modules", 
                    granted=False
                )
                metrics.record_permission_check("system", "list_modules", "denied")
                await update.message.reply_text("❌ Unauthorized")
                return
            
            # Check specific permission for viewing modules
            if not self.permission_manager.check_module_permission(user_id, "system", "read"):
                audit_logger.log_access_attempt(
                    user_id=user_id,
                    module="system",
                    action="list_modules",
                    granted=False,
                    reason="Insufficient role for module listing"
                )
                metrics.record_permission_check("system", "list_modules", "denied")
                await update.message.reply_text("❌ Insufficient permissions to view modules")
                return
            
            audit_logger.log_access_attempt(
                user_id=user_id,
                module="system",
                action="list_modules",
                granted=True
            )
            metrics.record_permission_check("system", "list_modules", "granted")
            
            modules_text = "**🛠️ Available MCP Modules:**\n\n"
            
            for module_id, module in self.modules.items():
                modules_text += f"**{module['name']}**\n"
                for capability in module['capabilities'][:3]:  # Show first 3
                    modules_text += f"  • {capability}\n"
                modules_text += "\n"
            
            audit_logger.log_event(
                user_id=user_id,
                module="system",
                action="list_modules",
                details={"modules_count": len(self.modules)}
            )
            
            await update.message.reply_text(modules_text, parse_mode='Markdown')
    
    async def _handle_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all messages with Claude Desktop-style AI."""
        user_id = update.effective_user.id
        message_text = update.message.text
        first_name = update.effective_user.first_name or "User"
        
        with logging_middleware.log_request(user_id, "ai", "conversation", message_preview=message_text[:50]):
            if not self.permission_manager.is_user_allowed(user_id):
                audit_logger.log_access_attempt(
                    user_id=user_id,
                    module="ai",
                    action="conversation",
                    granted=False
                )
                metrics.record_permission_check("ai", "conversation", "denied")
                await update.message.reply_text("❌ Unauthorized")
                return
            
            audit_logger.log_access_attempt(
                user_id=user_id, 
                module="ai",
                action="conversation",
                granted=True
            )
            metrics.record_permission_check("ai", "conversation", "granted")
            
            try:
                # Show typing
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                
                # Log conversation start
                audit_logger.log_event(
                    user_id=user_id,
                    module="ai",
                    action="conversation_start",
                    details={"message_length": len(message_text)}
                )
                
                # Process with Claude-style AI
                if self.ai_agent:
                    response = await self.ai_agent.process(
                        user_id=user_id,
                        message=message_text,
                        user_name=first_name,
                        modules=self.modules,
                        context=context,
                        update=update
                    )
                    
                    if response:
                        # Store conversation
                        self.conversation_manager.add_message(
                            user_id, message_text, response, "ai"
                        )
                        
                        # Log successful response
                        audit_logger.log_event(
                            user_id=user_id,
                            module="ai", 
                            action="conversation_complete",
                            details={
                                "response_length": len(response),
                                "modules_available": len(self.modules)
                            }
                        )
                        
                        user_role = self.permission_manager.get_user_role(user_id)
                        metrics.record_request("ai", "conversation", "success", 0, user_role)
                        
                        await update.message.reply_text(response, parse_mode='Markdown')
                        return
                
                # Fallback
                audit_logger.log_event(
                    user_id=user_id,
                    module="ai",
                    action="conversation_fallback",
                    status="warning",
                    details={"reason": "AI agent not available"}
                )
                
                await update.message.reply_text(
                    "I'm having trouble processing that. Try rephrasing or check my configuration.",
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                # Log error with audit
                audit_logger.log_error(
                    user_id=user_id,
                    module="ai",
                    action="conversation",
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                
                user_role = self.permission_manager.get_user_role(user_id)
                metrics.record_request("ai", "conversation", "error", 0, user_role)
                metrics.record_error("ai", type(e).__name__)
                
                self.logger.error(f"Conversation error: {e}", exc_info=True)
                await update.message.reply_text(
                    "Sorry, I encountered an error. Please try again.",
                    parse_mode='Markdown'
                )

# Export
UmbraBot = UmbraAIAgent
