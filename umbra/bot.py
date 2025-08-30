"""
Main bot implementation for Umbra Bot - Phase 1.

This is the core bot class that handles Telegram interactions, module loading,
and command routing. Uses polling mode for Phase 1 implementation.
"""

import asyncio
import signal
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime

# Telegram Bot API
from telegram import Update, Bot
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters,
    ContextTypes
)

# Core Umbra imports
from .core.config import get_config, UmbraConfig
from .core.logger import get_logger, setup_logging
from .core.envelope import create_envelope, InternalEnvelope
from .core.module_base import ModuleBase
from .core.feature_flags import log_feature_status

# Module imports
from .modules.finance import FinanceModule
from .modules.monitoring import MonitoringModule


class UmbraBot:
    """
    Main Umbra Bot class - Phase 1 Implementation.
    
    Features:
    - Telegram polling mode
    - Dynamic module loading
    - Structured logging
    - Environment-based configuration
    - Graceful error handling
    """
    
    def __init__(self):
        """Initialize the Umbra Bot."""
        # Setup logging first
        setup_logging()
        self.logger = get_logger("umbra.bot")
        
        # Load configuration
        try:
            self.config = get_config()
            self.logger.info("Configuration loaded successfully")
        except Exception as e:
            self.logger.error("Failed to load configuration", error=str(e))
            raise
        
        # Initialize bot state
        self.application: Optional[Application] = None
        self.modules: Dict[str, ModuleBase] = {}
        self.is_running = False
        self.startup_time = datetime.utcnow()
        
        # Validate required configuration
        self._validate_configuration()
        
        # Log warnings for missing optional configuration
        self._log_optional_config_warnings()
        
        self.logger.info("Umbra Bot initialized", 
                        bot_token_configured=bool(self.config.telegram_bot_token),
                        allowed_users_count=len(self.config.allowed_user_ids))
    
    def _validate_configuration(self):
        """Validate required configuration and raise if invalid."""
        if not self.config.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        if not self.config.allowed_user_ids:
            raise ValueError("ALLOWED_USER_IDS is required")
        
        self.logger.info("Configuration validation passed")
    
    def _log_optional_config_warnings(self):
        """Log warnings for missing optional configuration."""
        missing_keys = self.config.get_missing_optional_keys()
        
        if missing_keys:
            self.logger.warning("Optional configuration missing - some features will be disabled",
                              missing_keys=missing_keys)
        
        # Log feature flag status
        log_feature_status()
    
    async def initialize(self) -> bool:
        """
        Initialize the bot and all modules.
        
        Returns:
            True if initialization successful
        """
        try:
            self.logger.info("Bot initialization starting")
            
            # Create Telegram application
            self.application = Application.builder().token(self.config.telegram_bot_token).build()
            
            # Load and initialize modules
            await self._load_modules()
            
            # Register command handlers
            await self._register_handlers()
            
            self.logger.info("Bot initialization completed successfully",
                           modules_loaded=len(self.modules))
            return True
            
        except Exception as e:
            self.logger.error("Bot initialization failed", error=str(e))
            return False
    
    async def _load_modules(self):
        """Load and initialize all bot modules."""
        self.logger.info("Loading bot modules")
        
        # Phase 1 modules
        modules_to_load = [
            ("finance", FinanceModule),
            ("monitoring", MonitoringModule)
        ]
        
        for module_name, module_class in modules_to_load:
            try:
                self.logger.info(f"Loading module: {module_name}")
                
                # Check if module should be enabled
                if not self.config.is_module_enabled(module_name):
                    self.logger.warning(f"Module {module_name} is disabled by configuration")
                    continue
                
                # Create and initialize module
                module = module_class()
                
                if await module._initialize_wrapper():
                    await module._register_handlers_wrapper()
                    self.modules[module_name] = module
                    self.logger.info(f"Module {module_name} loaded successfully",
                                   handlers=len(module.handlers))
                else:
                    self.logger.error(f"Failed to initialize module: {module_name}")
                    
            except Exception as e:
                self.logger.error(f"Error loading module {module_name}", error=str(e))
        
        self.logger.info("Module loading completed", 
                        loaded_modules=list(self.modules.keys()))
    
    async def _register_handlers(self):
        """Register Telegram command handlers."""
        if not self.application:
            raise RuntimeError("Application not initialized")
        
        # Core bot handlers
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        
        # Generic message handler (for module commands)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        
        # All other commands handler
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self._handle_command)
        )
        
        self.logger.info("Telegram handlers registered")
    
    async def start_polling(self):
        """Start the bot in polling mode."""
        if not self.application:
            raise RuntimeError("Bot not initialized. Call initialize() first.")
        
        self.logger.info("Starting bot in polling mode")
        
        try:
            # Start polling
            await self.application.initialize()
            await self.application.start()
            
            self.is_running = True
            self.logger.info("Bot started successfully", 
                           mode="polling",
                           uptime_start=self.startup_time.isoformat())
            
            # Start polling with error handling
            await self.application.updater.start_polling(
                poll_interval=1.0,
                timeout=30,
                bootstrap_retries=-1,
                drop_pending_updates=True
            )
            
            # Keep running until stopped
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error("Error in polling loop", error=str(e))
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown the bot."""
        self.logger.info("Bot shutdown initiated")
        
        self.is_running = False
        
        # Shutdown modules
        for module_name, module in self.modules.items():
            try:
                await module._shutdown_wrapper()
                self.logger.info(f"Module {module_name} shutdown completed")
            except Exception as e:
                self.logger.error(f"Error shutting down module {module_name}", error=str(e))
        
        # Shutdown Telegram application
        if self.application:
            try:
                await self.application.stop()
                await self.application.shutdown()
                self.logger.info("Telegram application shutdown completed")
            except Exception as e:
                self.logger.error("Error shutting down Telegram application", error=str(e))
        
        uptime = datetime.utcnow() - self.startup_time
        self.logger.info("Bot shutdown completed", 
                        uptime_seconds=uptime.total_seconds())
    
    # Command handlers
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = str(update.effective_user.id)
        
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized access.")
            return
        
        self.logger.info("Start command received", user_id=user_id)
        
        welcome_message = (
            "🤖 **Welcome to Umbra Bot!**\n\n"
            "I'm your intelligent assistant for finance, monitoring, and productivity.\n\n"
            "**Available Commands:**\n"
            "• `/help` - Show detailed help\n"
            "• `health` - Check system status\n"
            "• `status` - System information\n"
            "• `finance help` - Finance module help\n\n"
            "**Phase 1 Features:**\n"
            f"• 📊 Monitoring: {'✅ Active' if 'monitoring' in self.modules else '❌ Disabled'}\n"
            f"• 💰 Finance: {'✅ Active' if 'finance' in self.modules else '❌ Disabled'}\n\n"
            "Send me any command to get started!"
        )
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        user_id = str(update.effective_user.id)
        
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized access.")
            return
        
        self.logger.info("Help command received", user_id=user_id)
        
        # Build help message with available modules
        help_message = (
            "🤖 **Umbra Bot Help - Phase 1**\n\n"
            "**Core Commands:**\n"
            "• `/start` - Welcome message\n"
            "• `/help` - This help message\n\n"
            "**System Monitoring:**\n"
            "• `health` - System health check\n"
            "• `status` - Detailed system status\n"
            "• `uptime` - Bot and system uptime\n"
            "• `metrics` - Performance metrics\n\n"
        )
        
        if 'finance' in self.modules:
            help_message += (
                "**Finance Module:**\n"
                "• `receipt` - Process receipt images\n"
                "• `expense` - Track expenses\n"
                "• `budget` - Generate reports\n"
                "• `finance help` - Detailed finance help\n\n"
            )
        
        help_message += (
            "**About Phase 1:**\n"
            "This is the foundational implementation focusing on:\n"
            "• Core bot infrastructure\n"
            "• Module loading system\n"
            "• Basic health monitoring\n"
            "• Finance module structure\n\n"
            "**Coming in Phase 2:**\n"
            "• Full OCR document processing\n"
            "• AI integrations\n"
            "• Advanced reporting\n"
            "• Workflow automation\n\n"
            "Simply type commands without '/' prefix!"
        )
        
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages."""
        user_id = str(update.effective_user.id)
        message_text = update.message.text
        
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized access.")
            return
        
        self.logger.info("Message received", user_id=user_id, message=message_text)
        
        # Process message through modules
        response = await self._process_message(user_id, message_text)
        
        if response:
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "🤔 I didn't understand that command. Type `/help` for available commands.",
                parse_mode='Markdown'
            )
    
    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unknown commands."""
        user_id = str(update.effective_user.id)
        command = update.message.text
        
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized access.")
            return
        
        self.logger.info("Unknown command received", user_id=user_id, command=command)
        
        # Try to process as regular message (remove / prefix)
        if command.startswith('/'):
            command = command[1:]
        
        response = await self._process_message(user_id, command)
        
        if response:
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                f"❓ Unknown command: `{command}`\n\nType `/help` for available commands.",
                parse_mode='Markdown'
            )
    
    async def _process_message(self, user_id: str, message: str) -> Optional[str]:
        """Process a message through the module system."""
        # Create internal envelope
        envelope = create_envelope(
            user_id=user_id,
            action=message,
            context={
                "timestamp": datetime.utcnow().isoformat(),
                "processing_mode": "polling"
            }
        )
        
        # Try each module to see if it can handle the message
        for module_name, module in self.modules.items():
            try:
                if module.matches_command(message):
                    self.logger.info("Message routed to module", 
                                   module=module_name,
                                   req_id=envelope.req_id)
                    
                    response = await module._process_envelope_wrapper(envelope)
                    
                    if response:
                        # Log successful processing
                        duration = envelope.get_total_duration()
                        self.logger.info("Message processed successfully",
                                       module=module_name,
                                       req_id=envelope.req_id,
                                       duration_ms=duration)
                        return response
                        
            except Exception as e:
                self.logger.error("Module processing error",
                                module=module_name,
                                req_id=envelope.req_id,
                                error=str(e))
        
        return None
    
    def _is_user_allowed(self, user_id: str) -> bool:
        """Check if user is allowed to use the bot."""
        return user_id in self.config.allowed_user_ids
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        uptime = datetime.utcnow() - self.startup_time
        
        return {
            "is_running": self.is_running,
            "uptime_seconds": uptime.total_seconds(),
            "startup_time": self.startup_time.isoformat() + "Z",
            "modules_loaded": len(self.modules),
            "modules": {name: module.get_status() for name, module in self.modules.items()},
            "config": {
                "allowed_users_count": len(self.config.allowed_user_ids),
                "log_level": self.config.log_level,
                "features_enabled": {
                    "finance_ocr": self.config.feature_finance_ocr,
                    "metrics_collection": self.config.feature_metrics_collection
                }
            }
        }


async def main():
    """Main entry point for the bot."""
    bot = UmbraBot()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(bot.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize and start the bot
        if await bot.initialize():
            await bot.start_polling()
        else:
            print("Bot initialization failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Bot error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())