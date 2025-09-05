#!/usr/bin/env python3
"""
Umbra - Claude Desktop-style AI with MCP Modules
Production entry point for Railway deployment
"""
import os
import sys
import asyncio
import signal
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import our structured logging and config
from umbra.core.logger import setup_logging, get_logger
from umbra.core.config import UmbraConfig
from umbra.http.health import create_health_app

# Set up logging early
setup_logging(json_format=True)
logger = get_logger(__name__)


class UmbraLauncher:
    """Production launcher for Umbra."""
    
    def __init__(self):
        self.bot = None
        self.health_server = None
        self.config = UmbraConfig()
        self.port = self.config.PORT
        
    def setup_environment(self):
        """Set up production environment."""
        os.environ.setdefault('ENVIRONMENT', 'production')
        os.environ.setdefault('PYTHONPATH', str(PROJECT_ROOT))
        
        logger.info("🤖 Umbra - Claude Desktop-style AI with MCP Modules", 
                   action="startup", module="launcher")
        logger.info(f"🌍 Environment: {self.config.ENVIRONMENT}", 
                   action="env_info", environment=self.config.ENVIRONMENT)
        logger.info(f"🏥 Health port: {self.port}", 
                   action="port_info", port=self.port)
        
        if self.config.OPENROUTER_API_KEY:
            logger.info("🧠 AI: Full Claude-style conversation enabled", 
                       action="ai_status", ai_enabled=True)
        else:
            logger.info("💭 AI: Pattern-based (add OPENROUTER_API_KEY for full AI)", 
                       action="ai_status", ai_enabled=False)
    
    async def start_health_server(self):
        """Start health monitoring server using the new health module."""
        try:
            from aiohttp.web import AppRunner, TCPSite
            
            # Create health app using our new module
            app = create_health_app()
            
            runner = AppRunner(app)
            await runner.setup()
            site = TCPSite(runner, '0.0.0.0', self.port)
            await site.start()
            
            self.health_server = runner
            logger.info("✅ Health server started", 
                       action="health_server_start", port=self.port, 
                       endpoints=["/", "/health"])
            
        except Exception as e:
            logger.error("❌ Health server failed to start", 
                        action="health_server_error", error=str(e))
            raise
    
    async def start_bot(self):
        """Start the bot."""
        try:
            # Only import bot modules when actually needed to avoid import errors
            from umbra.bot import UmbraAIAgent
            
            logger.info("🚀 Starting Umbra MCP...", action="bot_start")
            
            self.bot = UmbraAIAgent(self.config)
            bot_task = asyncio.create_task(self.bot.start())
            
            logger.info("✅ Umbra MCP started successfully", action="bot_started")
            return bot_task
            
        except ImportError as e:
            logger.warning("⚠️ Bot module not available, running health server only", 
                          action="bot_import_error", error=str(e))
            # Return a dummy task that waits forever
            return asyncio.create_task(asyncio.sleep(float('inf')))
        except Exception as e:
            logger.error("❌ Failed to start bot", action="bot_start_error", error=str(e))
            raise
    
    async def shutdown(self):
        """Clean shutdown."""
        logger.info("🛑 Shutting down...", action="shutdown_start")
        
        if self.bot:
            try:
                await self.bot.shutdown()
                logger.info("✅ Bot shutdown complete", action="bot_shutdown")
            except Exception as e:
                logger.warning("⚠️ Bot shutdown warning", action="bot_shutdown_warning", error=str(e))
        
        if self.health_server:
            try:
                await self.health_server.cleanup()
                logger.info("✅ Health server shutdown complete", action="health_shutdown")
            except Exception as e:
                logger.warning("⚠️ Health shutdown warning", action="health_shutdown_warning", error=str(e))
        
        logger.info("✅ Shutdown complete", action="shutdown_complete")
    
    async def run(self):
        """Main run method."""
        try:
            # Start health server first
            await self.start_health_server()
            
            # Then start bot
            bot_task = await self.start_bot()
            
            def signal_handler(signum, frame):
                logger.info(f"Signal {signum} received", action="signal_received", signal=signum)
                bot_task.cancel()
            
            try:
                signal.signal(signal.SIGTERM, signal_handler)
                signal.signal(signal.SIGINT, signal_handler)
            except ValueError:
                # Signals not available in some environments
                pass
            
            try:
                await bot_task
            except asyncio.CancelledError:
                logger.info("Bot cancelled", action="bot_cancelled")
                
        except Exception as e:
            logger.error("❌ Runtime error", action="runtime_error", error=str(e))
            raise
        finally:
            await self.shutdown()


def main():
    """Main entry point."""
    print("="*60)
    print("🤖 Umbra MCP v3.0.0")
    print("💬 Claude Desktop-style AI with MCP Modules")
    print("🛠️ Railway deployment ready with structured logging")
    print("="*60)
    
    try:
        launcher = UmbraLauncher()
        launcher.setup_environment()
        
        logger.info("🚀 Starting Umbra launcher", action="main_start")
        asyncio.run(launcher.run())
        logger.info("✅ Umbra launcher completed", action="main_complete")
        return 0
        
    except KeyboardInterrupt:
        logger.info("👋 Stopped by user", action="user_interrupt")
        return 0
    except Exception as e:
        logger.error("❌ Fatal error", action="fatal_error", error=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
