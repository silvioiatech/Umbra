#!/usr/bin/env python3
"""
UMBRA Telegram Bot MVP
A simple bot with polling, /start, /help commands, rate limiting, and logging.
"""
import asyncio
import logging
import os
import time
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pathlib import Path

# Add project root to path for imports
import sys
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import utilities directly without triggering config validation
import os
os.environ.setdefault('UMBRA_SKIP_VALIDATION', '1')

from umbra.utils.rate_limiter import RateLimiter
from umbra.core.logger import setup_logging, get_logger


class UmbraBotMVP:
    """Simple Telegram bot MVP with essential features."""
    
    def __init__(self, bot_token: str, allowed_user_ids: list = None):
        """
        Initialize the MVP bot.
        
        Args:
            bot_token: Telegram bot token from @BotFather
            allowed_user_ids: List of allowed user IDs (if None, allows all users)
        """
        self.bot_token = bot_token
        self.allowed_user_ids = allowed_user_ids or []
        self.application: Optional[Application] = None
        self.start_time = time.time()
        
        # Setup logging
        setup_logging(level="INFO")
        self.logger = get_logger(__name__)
        
        # Setup rate limiting (10 requests per minute per user)
        self.rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        self.logger.info("🤖 UMBRA Bot MVP initialized")
        if self.allowed_user_ids:
            self.logger.info(f"👥 Allowed users: {len(self.allowed_user_ids)}")
        else:
            self.logger.info("👥 Open access mode (no user restrictions)")
    
    def _is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        if not self.allowed_user_ids:
            return True  # Open access if no restrictions set
        return user_id in self.allowed_user_ids
    
    def _check_rate_limit(self, user_id: int) -> bool:
        """Check if user is within rate limits."""
        return self.rate_limiter.is_allowed(user_id)
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "User"
        
        self.logger.info(f"📱 /start command from user {user_id} ({user_name})")
        
        # Check if user is allowed
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Sorry, you're not authorized to use this bot.")
            self.logger.warning(f"🚫 Unauthorized access attempt by user {user_id}")
            return
        
        # Check rate limits
        if not self._check_rate_limit(user_id):
            remaining = self.rate_limiter.get_remaining_requests(user_id)
            await update.message.reply_text(
                f"⏱️ Rate limit exceeded. You can make {remaining} more requests in the next minute."
            )
            return
        
        # Send welcome message
        uptime = time.time() - self.start_time
        uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m"
        
        welcome_message = f"""🤖 **UMBRA Bot MVP** 

Hello {user_name}! I'm a simple Telegram bot with essential features:

✅ **Features Available:**
• Polling for real-time updates
• Rate limiting (10 requests/minute)
• Comprehensive logging
• User authorization

📊 **Bot Status:**
• Uptime: {uptime_str}
• Rate limit: {self.rate_limiter.get_remaining_requests(user_id)}/10 requests remaining

Use /help to see available commands!"""
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "User"
        
        self.logger.info(f"❓ /help command from user {user_id} ({user_name})")
        
        # Check if user is allowed
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Sorry, you're not authorized to use this bot.")
            return
        
        # Check rate limits
        if not self._check_rate_limit(user_id):
            remaining = self.rate_limiter.get_remaining_requests(user_id)
            await update.message.reply_text(
                f"⏱️ Rate limit exceeded. You can make {remaining} more requests in the next minute."
            )
            return
        
        help_message = """📖 **UMBRA Bot MVP - Help**

**Available Commands:**
• `/start` - Welcome message and bot status
• `/help` - Show this help message

**Bot Features:**
🔄 **Polling** - Real-time message processing
⏱️ **Rate Limiting** - 10 requests per minute per user
📝 **Logging** - All interactions are logged
🔐 **Authorization** - User access control

**Rate Limit Status:**
• Remaining requests: {}/10
• Window resets every 60 seconds

**About:**
This is the MVP (Minimum Viable Product) version of UMBRA bot, demonstrating core Telegram bot functionality with essential features for production use.

Need more features? Contact the bot administrator!"""
        
        remaining = self.rate_limiter.get_remaining_requests(user_id)
        formatted_message = help_message.format(remaining)
        
        await update.message.reply_text(formatted_message, parse_mode='Markdown')
    
    async def _handle_other_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle any other messages (not commands)."""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "User"
        message_text = update.message.text
        
        self.logger.info(f"💬 Message from user {user_id} ({user_name}): {message_text[:50]}...")
        
        # Check if user is allowed
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Sorry, you're not authorized to use this bot.")
            return
        
        # Check rate limits
        if not self._check_rate_limit(user_id):
            remaining = self.rate_limiter.get_remaining_requests(user_id)
            await update.message.reply_text(
                f"⏱️ Rate limit exceeded. You can make {remaining} more requests in the next minute."
            )
            return
        
        # Simple echo response for MVP
        response = f"""💭 Thanks for your message, {user_name}!

This is the MVP version of UMBRA bot. I can respond to:
• `/start` - Get started
• `/help` - Show help

Your message was: "{message_text[:100]}{'...' if len(message_text) > 100 else ''}"

Rate limit status: {self.rate_limiter.get_remaining_requests(user_id)}/10 requests remaining."""
        
        await update.message.reply_text(response)
    
    async def _register_handlers(self) -> None:
        """Register command and message handlers."""
        if not self.application:
            raise RuntimeError("Application not initialized")
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        
        # Message handler for non-command messages
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_other_messages)
        )
        
        self.logger.info("✅ Handlers registered")
    
    async def start(self) -> None:
        """Start the bot with polling."""
        try:
            self.logger.info("🚀 Starting UMBRA Bot MVP...")
            
            # Create application
            self.application = Application.builder().token(self.bot_token).build()
            
            # Register handlers
            await self._register_handlers()
            
            # Initialize and start
            await self.application.initialize()
            await self.application.start()
            
            # Start polling (this is the key requirement)
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "edited_message"]
            )
            
            self.logger.info("✅ UMBRA Bot MVP started successfully!")
            self.logger.info("🔄 Polling for updates...")
            
            # Keep the bot running
            await self._run_forever()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start bot: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def _run_forever(self) -> None:
        """Keep the bot running until interrupted."""
        try:
            # Create a stop event that waits indefinitely
            stop_event = asyncio.Event()
            await stop_event.wait()
        except asyncio.CancelledError:
            self.logger.info("🛑 Bot stopped by cancellation")
        except KeyboardInterrupt:
            self.logger.info("🛑 Bot stopped by user")
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the bot."""
        if self.application:
            self.logger.info("🛑 Shutting down bot...")
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                self.logger.info("✅ Bot shutdown complete")
            except Exception as e:
                self.logger.warning(f"⚠️ Shutdown warning: {e}")


async def main():
    """Main function to run the MVP bot."""
    # Get configuration from environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable is required")
        print("💡 Get your bot token from @BotFather on Telegram")
        return
    
    # Parse allowed user IDs (optional)
    allowed_users_str = os.getenv('ALLOWED_USER_IDS', '')
    allowed_user_ids = []
    if allowed_users_str:
        try:
            allowed_user_ids = [int(uid.strip()) for uid in allowed_users_str.split(',') if uid.strip()]
        except ValueError:
            print("⚠️ Warning: Invalid ALLOWED_USER_IDS format, allowing all users")
    
    # Create and start the bot
    bot = UmbraBotMVP(bot_token=bot_token, allowed_user_ids=allowed_user_ids)
    
    print("="*50)
    print("🤖 UMBRA Telegram Bot MVP")
    print("="*50)
    print("✅ Polling functionality")
    print("✅ /start and /help commands")
    print("✅ Rate limiting (10 req/min)")
    print("✅ Comprehensive logging")
    print("="*50)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())