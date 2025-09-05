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

class UmbraAIAgent:
    """Claude Desktop-style AI agent with MCP-like module integration."""
    
    def __init__(self, config_obj=None):
        self.config = config_obj or config
        self.logger = logging.getLogger(__name__)
        self.application: Optional[Application] = None
        
        # Track start time for uptime
        self.start_time = time.time()
        
        # Initialize core systems
        self._init_systems()
        
        # Initialize AI as primary interface (like Claude Desktop)
        self._init_ai_agent()
        
        # Initialize MCP-style modules
        self._init_mcp_modules()
    
    def _init_systems(self):
        """Initialize core systems."""
        try:
            from .core.permissions import PermissionManager
            from .storage.database import DatabaseManager
            from .storage.conversation import ConversationManager
            
            self.permission_manager = PermissionManager()
            self.db_manager = DatabaseManager(self.config.DATABASE_PATH)
            self.conversation_manager = ConversationManager(self.db_manager)
            
            self.logger.info("✅ Core systems initialized")
            
        except Exception as e:
            self.logger.error(f"❌ Core systems error: {e}")
            raise
    
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
                from .modules.creator import CreatorMCP
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
            
            # Create Telegram application
            self.application = Application.builder().token(self.config.TELEGRAM_BOT_TOKEN).build()
            
            # Register handlers
            await self._register_handlers()
            
            # Start application
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)
            
            self.logger.info("✅ Umbra started - Ready for natural conversation")
            
            # Keep running
            await self._run_forever()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start: {e}")
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
        
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                self.logger.warning(f"Shutdown warning: {e}")
        
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
        
        if not self.permission_manager.is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized. Add your ID to ALLOWED_USER_IDS.")
            return
        
        # Add user to database
        self.db_manager.add_user(
            user_id, 
            update.effective_user.username, 
            first_name, 
            update.effective_user.last_name
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
        
        if not self.permission_manager.is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        modules_text = "**🛠️ Available MCP Modules:**\n\n"
        
        for module_id, module in self.modules.items():
            modules_text += f"**{module['name']}**\n"
            for capability in module['capabilities'][:3]:  # Show first 3
                modules_text += f"  • {capability}\n"
            modules_text += "\n"
        
        await update.message.reply_text(modules_text, parse_mode='Markdown')
    
    async def _handle_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all messages with Claude Desktop-style AI."""
        user_id = update.effective_user.id
        message_text = update.message.text
        first_name = update.effective_user.first_name or "User"
        
        if not self.permission_manager.is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        try:
            # Show typing
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
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
                    
                    await update.message.reply_text(response, parse_mode='Markdown')
                    return
            
            # Fallback
            await update.message.reply_text(
                "I'm having trouble processing that. Try rephrasing or check my configuration.",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            self.logger.error(f"Conversation error: {e}", exc_info=True)
            await update.message.reply_text(
                "Sorry, I encountered an error. Please try again.",
                parse_mode='Markdown'
            )

# Export
UmbraBot = UmbraAIAgent
