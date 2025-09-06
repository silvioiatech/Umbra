"""
Umbra Bot - F3R1: Complete AI Telegram Bot with OpenRouter, Tools, and Smart Routing.
Features: F2 functionality + OpenRouter AI + built-in tools + module discovery + smart routing.
"""
import asyncio
import time
from typing import Optional, Dict, Any
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes
)
from telegram.error import TelegramError, Forbidden, BadRequest

from .core.config import config
from .core.permissions import PermissionManager
from .core.logger import (
    get_context_logger, set_request_context, clear_request_context,
    log_user_action
)
from .utils.rate_limiter import rate_limiter
from .storage.database import DatabaseManager
from .storage.conversation import ConversationManager

# F3 imports
from .ai.agent import UmbraAIAgent
from .modules.registry import ModuleRegistry
from .router import UmbraRouter
from .utils.error_utils import create_error_response, redact_sensitive_data

class UmbraBot:
    """
    Umbra Telegram Bot with F3R1 enhancements.
    
    F3R1 Features:
    - Full AI conversation via OpenRouter
    - Built-in tools (calculator, time, units)
    - Smart Router with AI fallback
    - Module Registry with automatic discovery
    - Enhanced error handling and redaction
    - Comprehensive status reporting
    
    F2 Features (maintained):
    - Railway-safe polling mode (no webhooks)
    - Per-user rate limiting
    - Permission-based access control
    - Request ID tracking and structured logging
    - Graceful shutdown handling
    """
    
    def __init__(self, config_obj=None):
        self.config = config_obj or config
        self.logger = get_context_logger(__name__)
        
        # Core systems
        self.permission_manager = PermissionManager()
        self.db_manager = DatabaseManager(self.config.DATABASE_PATH)
        self.conversation_manager = ConversationManager(self.db_manager)
        
        # F3 components
        self.ai_agent = UmbraAIAgent(self.config)
        self.module_registry = ModuleRegistry(self.config, self.db_manager)
        self.router = UmbraRouter()
        
        # Telegram application
        self.application: Optional[Application] = None
        self._shutdown_event = asyncio.Event()
        
        # Track start time for uptime
        self.start_time = time.time()
        
        # Module discovery flag
        self._modules_discovered = False
        
        self.logger.info(
            "UmbraBot F3R1 initialized",
            extra={
                "config_environment": self.config.ENVIRONMENT,
                "rate_limit_enabled": config.RATE_LIMIT_ENABLED,
                "rate_limit_per_min": config.RATE_LIMIT_PER_MIN,
                "allowed_users_count": len(self.config.ALLOWED_USER_IDS),
                "admin_users_count": len(self.config.ALLOWED_ADMIN_IDS),
                "f3r1_components": ["ai_agent", "module_registry", "router"]
            }
        )
    
    async def start(self) -> None:
        """Start the Telegram bot with F3 components and Railway-optimized polling."""
        
        self.logger.info("Starting Telegram bot in F3R1 mode")
        
        try:
            # Create Telegram application
            self.application = (
                Application.builder()
                .token(self.config.TELEGRAM_BOT_TOKEN)
                .build()
            )
            
            # Initialize F3 components
            await self._initialize_f3_components()
            
            # Register middleware and handlers
            self._register_handlers()
            
            # Initialize application
            await self.application.initialize()
            await self.application.start()
            
            # Start polling (Railway-safe)
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query'],
                timeout=30,
                pool_timeout=60
            )
            
            self.logger.info(
                "Telegram bot started successfully",
                extra={
                    "polling_mode": True,
                    "handlers_count": len(self.application.handlers[0]),
                    "drop_pending_updates": True,
                    "f3r1_mode": True
                }
            )
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
        except Exception as e:
            self.logger.error(
                "Failed to start Telegram bot",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise
        finally:
            await self.shutdown()
    
    async def _initialize_f3_components(self) -> None:
        """Initialize F3 components: AI agent, module registry, router."""
        
        self.logger.info("Initializing F3R1 components")
        
        try:
            # Discover modules
            if not self._modules_discovered:
                discovered_count = await self.module_registry.discover_modules()
                self._modules_discovered = True
                
                self.logger.info(
                    "Module discovery completed",
                    extra={
                        "discovered_modules": discovered_count,
                        "available_modules": len(self.module_registry.get_available_modules())
                    }
                )
            
            # AI agent is already initialized in __init__
            # Router is already initialized in __init__
            
            self.logger.info("F3R1 components initialized successfully")
            
        except Exception as e:
            self.logger.error(
                "F3R1 component initialization failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            # Continue startup even if F3 components fail
    
    async def shutdown(self) -> None:
        """Graceful shutdown of the Telegram bot."""
        
        self.logger.info("Shutting down Telegram bot")
        
        shutdown_results = {}
        
        if self.application:
            try:
                # Stop polling
                if self.application.updater.running:
                    await self.application.updater.stop()
                    shutdown_results["polling"] = "stopped"
                
                # Stop application
                await self.application.stop()
                await self.application.shutdown()
                shutdown_results["application"] = "shutdown"
                
            except Exception as e:
                self.logger.warning(
                    "Error during bot shutdown",
                    extra={"error": str(e), "error_type": type(e).__name__}
                )
                shutdown_results["application"] = f"error: {e}"
        
        # Close database connections
        try:
            await self.db_manager.close()
            shutdown_results["database"] = "closed"
        except Exception as e:
            shutdown_results["database"] = f"error: {e}"
        
        self.logger.info(
            "Telegram bot shutdown completed",
            extra={"shutdown_results": shutdown_results}
        )
    
    def stop(self) -> None:
        """Signal the bot to stop (called by signal handlers)."""
        self.logger.info("Stop signal received")
        self._shutdown_event.set()
    
    def _register_handlers(self) -> None:
        """Register all command and message handlers with middleware."""
        
        if not self.application:
            raise RuntimeError("Application not initialized")
        
        # Add command handlers
        self.application.add_handler(
            CommandHandler("start", self._with_middleware(self._handle_start))
        )
        
        self.application.add_handler(
            CommandHandler("help", self._with_middleware(self._handle_help))
        )
        
        # F3R1: Add /status command
        self.application.add_handler(
            CommandHandler("status", self._with_middleware(self._handle_status))
        )
        
        # F3R1: Enhanced text message handler with AI routing
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._with_middleware(self._handle_text_message)
            )
        )
        
        # Error handler
        self.application.add_error_handler(self._handle_error)
        
        self.logger.info(
            "Bot handlers registered",
            extra={
                "command_handlers": ["start", "help", "status"],
                "message_handlers": ["text"],
                "error_handler": True,
                "f3r1_components": True
            }
        )
    
    def _with_middleware(self, handler_func):
        """Wrap handler with middleware for permissions, rate limiting, and logging."""
        
        async def wrapped_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Middleware wrapper for all handlers."""
            
            # Extract user information
            user = update.effective_user
            chat = update.effective_chat
            message = update.message or update.callback_query
            
            if not user:
                self.logger.warning("Received update without user information")
                return
            
            user_id = user.id
            username = user.username or f"user_{user_id}"
            
            # Set request context for logging
            request_id = set_request_context(
                user_id=user_id,
                module="bot",
                action=handler_func.__name__
            )
            
            try:
                # 1. Permission check
                if not self.permission_manager.is_user_allowed(user_id):
                    await self._handle_unauthorized(update, context, user)
                    return
                
                # 2. Rate limiting check
                if not rate_limiter.is_allowed(user_id):
                    await self._handle_rate_limited(update, context, user)
                    return
                
                # 3. Log the request
                self.logger.info(
                    "Processing user request",
                    extra={
                        "user_id": user_id,
                        "username": username,
                        "chat_type": chat.type if chat else "unknown",
                        "message_type": type(message).__name__ if message else "unknown",
                        "handler": handler_func.__name__
                    }
                )
                
                # 4. Execute the actual handler
                start_time = time.time()
                await handler_func(update, context)
                duration_ms = (time.time() - start_time) * 1000
                
                # 5. Log successful completion
                log_user_action(
                    self.logger.logger,
                    user_id,
                    handler_func.__name__,
                    "bot",
                    True,
                    {"duration_ms": round(duration_ms, 2)}
                )
                
            except Exception as e:
                # Log error
                self.logger.error(
                    "Handler execution failed",
                    extra={
                        "user_id": user_id,
                        "handler": handler_func.__name__,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                
                # Send error message to user
                try:
                    await update.effective_message.reply_text(
                        "⚠️ Sorry, I encountered an error processing your request. Please try again."
                    )
                except Exception:
                    pass  # Don't fail on error message failure
                
            finally:
                # Clear request context
                clear_request_context()
        
        return wrapped_handler
    
    async def _handle_unauthorized(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user):
        """Handle unauthorized user access."""
        
        unauthorized_message = (
            f"🔒 Hello {user.first_name or 'there'}!\n\n"
            "I'm Umbra, a private AI assistant. You're not currently authorized to use me.\n\n"
            "To gain access, please contact the administrator and provide your Telegram ID: "
            f"`{user.id}`\n\n"
            "_Note: This is a security feature to protect private systems._"
        )
        
        try:
            await update.effective_message.reply_text(
                unauthorized_message,
                parse_mode='Markdown'
            )
        except Exception as e:
            self.logger.error(
                "Failed to send unauthorized message",
                extra={"error": str(e)}
            )
    
    async def _handle_rate_limited(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user):
        """Handle rate-limited user."""
        
        reset_time = rate_limiter.get_reset_time(user.id)
        wait_seconds = int(reset_time - time.time()) if reset_time else 60
        
        rate_limit_message = (
            f"⏱️ Slow down, {user.first_name or 'there'}!\n\n"
            f"You've exceeded the rate limit of {config.RATE_LIMIT_PER_MIN} messages per minute.\n"
            f"Please wait {wait_seconds} seconds before sending another message.\n\n"
            "_This helps keep the system responsive for everyone._"
        )
        
        try:
            await update.effective_message.reply_text(rate_limit_message)
        except Exception as e:
            self.logger.error(
                "Failed to send rate limit message",
                extra={"error": str(e)}
            )
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command with comprehensive welcome message."""
        
        user = update.effective_user
        first_name = user.first_name or "there"
        is_admin = self.permission_manager.is_user_admin(user.id)
        
        # Store user in database
        self.db_manager.add_user(
            user.id,
            user.username,
            user.first_name,
            user.last_name
        )
        
        # F3R1: Enhanced welcome message
        available_modules = self.module_registry.get_available_modules()
        
        welcome_message = (
            f"👋 Hello {first_name}!\n\n"
            "🤖 **I'm Umbra F3R1+BOT2** - your AI assistant with specialized modules.\n\n"
            "**F3R1+BOT2 Features:**\n"
            "🧠 Full AI conversation with OpenRouter\n"
            "🧮 Built-in tools (calculator, time, units)\n"
            "🔧 Advanced health monitoring & diagnostics\n"
            f"🛠️ {len(available_modules)} specialized modules available\n"
            "📊 Enhanced status and monitoring\n\n"
            "**Commands:**\n"
            "🔧 `/status` - Health dashboard & diagnostics\n"
            "❓ `/help` - Available commands and patterns\n"
            "💬 **Chat naturally** - I route to appropriate modules\n\n"
            f"**Environment:** {config.ENVIRONMENT.title()}\n"
            f"**Rate Limit:** {config.RATE_LIMIT_PER_MIN}/min\n\n"
            "_Try asking about system status, docker containers, or just chat!_"
        )
        
        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown'
        )
    
    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """F3R1: Enhanced help command with routing patterns."""
        
        user = update.effective_user
        is_admin = self.permission_manager.is_user_admin(user.id)
        
        # Get available patterns from router
        patterns = self.router.get_available_patterns(admin_only=False)
        admin_patterns = self.router.get_available_patterns(admin_only=True)
        
        help_message = [
            "📋 **Umbra F3R1+BOT2 - Help & Commands**\n\n",
            "**Basic Commands:**\n",
            "🔸 `/start` - Welcome and introduction\n",
            "🔸 `/help` - This help message\n", 
            "🔸 `/status` - System health dashboard\n",
            "🔸 `/status verbose` - Detailed diagnostics (admin)\n\n",
            
            "**Smart Routing Patterns:**\n"
        ]
        
        # Show some key patterns
        key_patterns = [p for p in patterns if not p['admin_only']][:8]
        for pattern in key_patterns:
            help_message.append(f"• `{pattern['pattern']}` - {pattern['description']}\n")
        
        if is_admin and admin_patterns:
            help_message.extend([
                "\n**Admin Patterns:**\n"
            ])
            for pattern in admin_patterns[:5]:
                help_message.append(f"• `{pattern['pattern']}` - {pattern['description']}\n")
        
        help_message.extend([
            "\n**Natural Chat:**\n",
            "💬 Just type your message! I understand:\n",
            "   • Questions about system status\n",
            "   • Docker and service management\n", 
            "   • General conversation\n\n",
            f"**Status:** F3R1+BOT2 Mode, {len(self.module_registry.get_available_modules())} modules active\n",
            f"**Locale:** {config.LOCALE_TZ}\n\n",
            "_F3R1+BOT2 Active: AI conversation + health monitoring!_"
        ])
        
        await update.message.reply_text(
            "".join(help_message),
            parse_mode='Markdown'
        )
    
    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """BOT2: Enhanced status command with comprehensive health monitoring."""
        
        user = update.effective_user
        is_admin = self.permission_manager.is_user_admin(user.id)
        
        # Check for verbose mode (admin only)
        message_text = update.message.text or ""
        verbose = "verbose" in message_text.lower() and is_admin
        
        # Show typing indicator for health checks
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        try:
            # Import health checker
            from ..core.health import HealthChecker, ServiceStatus
            
            # Run comprehensive health checks
            health_checker = HealthChecker(self.config)
            health_results = await health_checker.check_all_services(verbose=verbose)
            
            # Build status message
            status_msg = [
                "🤖 **Umbra Bot Status Dashboard**\n\n"
            ]
            
            # Core services status
            core_services = ["telegram", "openrouter", "r2_storage", "database"]
            status_msg.append("**🔧 Core Services:**\n")
            
            for service in core_services:
                if service in health_results:
                    result = health_results[service]
                    status_emoji = self._get_status_emoji(result.status)
                    configured_emoji = "🟢" if result.configured else "⚪"
                    
                    status_msg.append(
                        f"{status_emoji} {service.replace('_', ' ').title()}: "
                        f"{result.status.value} {configured_emoji}\n"
                    )
                    
                    if verbose and result.details:
                        status_msg.append(f"   ↳ {result.details}\n")
            
            status_msg.append("\n")
            
            # System components
            system_services = ["modules", "rate_limiter", "permissions"]
            status_msg.append("**⚙️ System Components:**\n")
            
            for service in system_services:
                if service in health_results:
                    result = health_results[service]
                    status_emoji = self._get_status_emoji(result.status)
                    
                    status_msg.append(
                        f"{status_emoji} {service.replace('_', ' ').title()}: "
                        f"{result.details}\n"
                    )
            
            # Verbose mode additional info
            if verbose:
                status_msg.append("\n**🔍 Detailed Diagnostics:**\n")
                
                verbose_services = ["system_resources", "network", "configuration"]
                for service in verbose_services:
                    if service in health_results:
                        result = health_results[service]
                        status_emoji = self._get_status_emoji(result.status)
                        
                        status_msg.append(
                            f"{status_emoji} {service.replace('_', ' ').title()}: "
                            f"{result.details}\n"
                        )
                        
                        if result.response_time_ms > 0:
                            status_msg.append(f"   ↳ Response time: {result.response_time_ms:.1f}ms\n")
            
            # Overall summary
            total_checks = len(health_results)
            active_checks = len([r for r in health_results.values() if r.status == ServiceStatus.ACTIVE])
            degraded_checks = len([r for r in health_results.values() if r.status == ServiceStatus.DEGRADED])
            error_checks = len([r for r in health_results.values() if r.status in [ServiceStatus.ERROR, ServiceStatus.INACTIVE]])
            
            if error_checks > 0:
                overall_emoji = "🔴"
                overall_status = "Degraded"
            elif degraded_checks > 0:
                overall_emoji = "🟡"
                overall_status = "Partial"
            else:
                overall_emoji = "🟢"
                overall_status = "Healthy"
            
            status_msg.extend([
                f"\n{overall_emoji} **Overall: {overall_status}** "
                f"({active_checks}/{total_checks} services active)\n\n"
            ])
            
            # Bot info
            uptime_seconds = time.time() - self.start_time
            uptime_hours = int(uptime_seconds / 3600)
            uptime_minutes = int((uptime_seconds % 3600) / 60)
            
            status_msg.extend([
                f"**📊 Bot Info:**\n",
                f"• Mode: F3R1+BOT2 (AI + Tools + Health)\n",
                f"• Uptime: {uptime_hours}h {uptime_minutes}m\n",
                f"• Environment: {self.config.ENVIRONMENT}\n",
                f"• Locale: {self.config.LOCALE_TZ}\n\n"
            ])
            
            if not verbose and is_admin:
                status_msg.append("_Use_ `/status verbose` _for detailed diagnostics._")
            elif not is_admin:
                status_msg.append("_Admin users can access verbose diagnostics._")
            else:
                status_msg.append("_Detailed diagnostics mode active._")
            
            await update.message.reply_text(
                "".join(status_msg),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            self.logger.error(
                "Enhanced status command failed",
                extra={"error": str(e), "user_id": user.id, "verbose": verbose}
            )
            
            # Fallback to basic status
            await update.message.reply_text(
                "⚠️ **Status System Error**\n\n"
                f"Failed to get comprehensive status: {str(e)[:100]}\n\n"
                "_Basic systems appear to be running._"
            )
    
    def _get_status_emoji(self, status) -> str:
        """Get emoji for service status."""
        emoji_map = {
            "active": "🟢",
            "degraded": "🟡", 
            "inactive": "⚪",
            "error": "🔴",
            "unknown": "❓"
        }
        return emoji_map.get(status.value if hasattr(status, 'value') else str(status), "❓")
    
    async def _handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """F3R1: Enhanced text message handler with routing and AI integration."""
        
        user = update.effective_user
        message_text = update.message.text
        is_admin = self.permission_manager.is_user_admin(user.id)
        
        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        try:
            # F3R1: Route message through router
            route_result = self.router.route_message(message_text, user.id, is_admin)
            
            if route_result.matched:
                # Execute module action
                response = await self._execute_module_action(
                    route_result.module,
                    route_result.action, 
                    route_result.params or {},
                    user.id
                )
            elif route_result.requires_admin:
                response = (
                    "🔒 **Admin Access Required**\n\n"
                    "This command requires administrator privileges.\n"
                    "Please contact an admin if you need access."
                )
            else:
                # F3R1: Route to general_chat for AI conversation
                response = await self.router.route_to_general_chat(message_text, user.id, self.module_registry)
                if not response:
                    response = self.router.get_fallback_response(message_text, user.id)
            
            # Store conversation
            self.conversation_manager.add_message(
                user.id, message_text, response, 
                "f3r1_router" if route_result.matched else "f3r1_ai_chat"
            )
            
            await update.message.reply_text(
                response,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            # F3R1: Enhanced error handling
            error_response = create_error_response(e, {"user_id": user.id})
            
            await update.message.reply_text(
                f"⚠️ {error_response['user_message']}\n\n"
                "Please try again or use `/help` for available commands."
            )
    
    async def _execute_module_action(
        self, 
        module_name: str, 
        action: str, 
        params: Dict[str, Any], 
        user_id: int
    ) -> str:
        """Execute action on a module through the registry."""
        
        try:
            result = await self.module_registry.execute_module_action(
                module_name, action, params, user_id
            )
            
            if result["success"]:
                if isinstance(result["result"], dict):
                    return result["result"].get("content", str(result["result"]))
                else:
                    return str(result["result"])
            else:
                return f"❌ **Module Error**: {result['error']}"
        
        except Exception as e:
            self.logger.error(
                "Module execution failed",
                extra={
                    "module": module_name,
                    "action": action,
                    "error": str(e)
                }
            )
            return f"❌ **Execution Failed**: {redact_sensitive_data(str(e))}"
    
    async def _handle_error(self, update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors in bot operations."""
        
        error = context.error
        
        # Log the error
        self.logger.error(
            "Telegram bot error",
            extra={
                "error": str(error),
                "error_type": type(error).__name__,
                "update_type": type(update).__name__ if update else None
            }
        )
        
        # Don't respond to certain types of errors
        if isinstance(error, (Forbidden, BadRequest)):
            return
        
        # Try to send a friendly error message
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "🔧 Oops! Something went wrong on my end. Please try again in a moment."
                )
            except Exception:
                pass  # Don't fail on error message failure
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive bot status information (F3R1 enhanced)."""
        
        uptime_seconds = time.time() - self.start_time
        
        return {
            "running": self.application is not None and self.application.running,
            "polling": self.application.updater.running if self.application else False,
            "uptime_seconds": uptime_seconds,
            "rate_limiter": rate_limiter.get_stats(),
            "permissions": self.permission_manager.get_status_summary(),
            "modules_discovered": self._modules_discovered,
            "ai_agent_available": self.ai_agent is not None,
            "database_connected": True,  # Simple check for F3R1
            "f3r1_mode": True,
            "components": {
                "ai_agent": "initialized",
                "module_registry": "initialized", 
                "router": "initialized"
            }
        }

# Legacy alias for backwards compatibility
UmbraAIAgent = UmbraBot

# Export
__all__ = ["UmbraBot", "UmbraAIAgent"]
