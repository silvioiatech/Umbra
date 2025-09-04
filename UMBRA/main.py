#!/usr/bin/env python3
"""
Umbra - Claude Desktop-style AI with MCP Modules
Production entry point for Railway deployment
"""
import os
import sys
import asyncio
import logging
import signal
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class UmbraLauncher:
    """Production launcher for Umbra."""
    
    def __init__(self):
        self.bot = None
        self.health_server = None
        self.port = int(os.environ.get('PORT', 8000))
        
    def setup_environment(self):
        """Set up production environment."""
        os.environ.setdefault('ENVIRONMENT', 'production')
        os.environ.setdefault('LOG_LEVEL', 'INFO')
        os.environ.setdefault('PYTHONPATH', str(PROJECT_ROOT))
        
        logger.info("🤖 Umbra - Claude Desktop-style AI with MCP Modules")
        logger.info(f"🌍 Environment: {os.environ.get('ENVIRONMENT')}")
        logger.info(f"🏥 Health port: {self.port}")
        
        if os.environ.get('OPENROUTER_API_KEY'):
            logger.info("🧠 AI: Full Claude-style conversation enabled")
        else:
            logger.info("💭 AI: Pattern-based (add OPENROUTER_API_KEY for full AI)")
    
    def validate_config(self):
        """Validate configuration."""
        required = {
            'TELEGRAM_BOT_TOKEN': '@BotFather',
            'ALLOWED_USER_IDS': '@userinfobot',
            'ALLOWED_ADMIN_IDS': 'Admin user IDs'
        }
        
        missing = []
        for var, source in required.items():
            if not os.environ.get(var):
                missing.append(f"  {var} - Get from {source}")
        
        if missing:
            logger.error("❌ Missing required variables:")
            for msg in missing:
                logger.error(msg)
            return False
        
        logger.info("✅ Configuration validated")
        return True
    
    async def start_health_server(self):
        """Start health monitoring server."""
        try:
            from aiohttp import web
            
            async def health_handler(request):
                return web.json_response({
                    "status": "healthy",
                    "service": "umbra-mcp",
                    "version": "3.0.0",
                    "architecture": "Claude Desktop + MCP",
                    "modules": [
                        "concierge",
                        "finance", 
                        "business",
                        "production",
                        "creator"
                    ]
                })
            
            async def root_handler(request):
                return web.json_response({
                    "name": "Umbra MCP",
                    "description": "Claude Desktop-style AI with MCP modules",
                    "endpoints": {
                        "/": "Service info",
                        "/health": "Health check"
                    }
                })
            
            app = web.Application()
            app.router.add_get('/', root_handler)
            app.router.add_get('/health', health_handler)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', self.port)
            await site.start()
            
            self.health_server = runner
            logger.info(f"✅ Health server on port {self.port}")
            
        except Exception as e:
            logger.warning(f"Health server failed: {e}")
    
    async def start_bot(self):
        """Start the bot."""
        try:
            from umbra.bot import UmbraAIAgent
            from umbra.core.config import config
            
            logger.info("🚀 Starting Umbra MCP...")
            
            self.bot = UmbraAIAgent(config)
            bot_task = asyncio.create_task(self.bot.start())
            
            logger.info("✅ Umbra MCP started successfully")
            return bot_task
            
        except Exception as e:
            logger.error(f"❌ Failed to start: {e}")
            raise
    
    async def shutdown(self):
        """Clean shutdown."""
        logger.info("🛑 Shutting down...")
        
        if self.bot:
            try:
                await self.bot.shutdown()
            except Exception as e:
                logger.warning(f"Bot shutdown warning: {e}")
        
        if self.health_server:
            try:
                await self.health_server.cleanup()
            except Exception as e:
                logger.warning(f"Health shutdown warning: {e}")
        
        logger.info("✅ Shutdown complete")
    
    async def run(self):
        """Main run method."""
        try:
            await self.start_health_server()
            bot_task = await self.start_bot()
            
            def signal_handler(signum, frame):
                logger.info(f"Signal {signum} received")
                bot_task.cancel()
            
            try:
                signal.signal(signal.SIGTERM, signal_handler)
                signal.signal(signal.SIGINT, signal_handler)
            except ValueError:
                pass
            
            try:
                await bot_task
            except asyncio.CancelledError:
                logger.info("Bot cancelled")
                
        except Exception as e:
            logger.error(f"Runtime error: {e}")
            raise
        finally:
            await self.shutdown()

def main():
    """Main entry point."""
    print("="*60)
    print("🤖 Umbra MCP v3.0.0")
    print("💬 Claude Desktop-style AI with MCP Modules")
    print("🛠️ 5 specialized modules for complete control")
    print("="*60)
    
    try:
        launcher = UmbraLauncher()
        launcher.setup_environment()
        
        if not launcher.validate_config():
            logger.error("❌ Fix configuration and restart")
            return 1
        
        asyncio.run(launcher.run())
        return 0
        
    except KeyboardInterrupt:
        logger.info("👋 Stopped by user")
        return 0
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
