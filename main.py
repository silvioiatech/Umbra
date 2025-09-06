#!/usr/bin/env python3
"""
Umbra MCP - Production entry point for Railway deployment
F1: Core runtime with HTTP health server, config validation, and structured logging
"""
import os
import sys
import asyncio
import signal
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import core components
from umbra.core.config import config
from umbra.core.logger import setup_logging, get_context_logger, set_request_context
from umbra.http.health import create_health_app

# Set up logging immediately
setup_logging(config.LOG_LEVEL)
logger = get_context_logger(__name__)

class UmbraLauncher:
    """Production launcher for Umbra MCP with Railway deployment support."""
    
    def __init__(self):
        self.bot = None
        self.health_server = None
        self.health_app_runner = None
        
        # Set startup context for logging
        set_request_context(
            module="launcher",
            action="startup"
        )
        
    def setup_environment(self):
        """Set up production environment with comprehensive logging."""
        
        # Set default environment variables
        os.environ.setdefault('ENVIRONMENT', 'production')
        os.environ.setdefault('LOG_LEVEL', config.LOG_LEVEL)
        os.environ.setdefault('PYTHONPATH', str(PROJECT_ROOT))
        
        logger.info(
            "Umbra MCP starting",
            extra={
                "version": "3.0.0",
                "environment": config.ENVIRONMENT,
                "port": config.PORT,
                "locale_tz": config.LOCALE_TZ,
                "privacy_mode": config.PRIVACY_MODE
            }
        )
        
        # Log feature status
        features = {
            "ai_integration": config.feature_ai_integration,
            "r2_storage": config.feature_r2_storage,
            "metrics_collection": config.feature_metrics_collection
        }
        
        logger.info("Feature flags configured", extra=features)
        
        # Log OpenRouter configuration
        if config.OPENROUTER_API_KEY:
            logger.info(
                "AI capabilities enabled",
                extra={
                    "provider": "OpenRouter",
                    "model": config.OPENROUTER_DEFAULT_MODEL,
                    "base_url": config.OPENROUTER_BASE_URL
                }
            )
        else:
            logger.info("AI capabilities disabled (pattern-based mode)")
        
        # Log R2 storage configuration
        if config.feature_r2_storage:
            logger.info(
                "R2 storage enabled",
                extra={
                    "bucket": config.R2_BUCKET,
                    "endpoint": config.R2_ENDPOINT
                }
            )
        else:
            logger.info("R2 storage disabled (using local SQLite)")
    
    def validate_config(self) -> bool:
        """Validate configuration with detailed error reporting."""
        
        logger.info("Validating configuration")
        
        try:
            # This will raise ValueError if required config is missing
            # The validation is done in UmbraConfig.__init__()
            
            # Additional validation checks
            validation_results = {
                "telegram_token": bool(config.TELEGRAM_BOT_TOKEN),
                "allowed_users": len(config.ALLOWED_USER_IDS) > 0,
                "admin_users": len(config.ALLOWED_ADMIN_IDS) > 0,
                "port_valid": 1 <= config.PORT <= 65535,
                "rate_limit_valid": config.RATE_LIMIT_PER_MIN > 0
            }
            
            failed_checks = [check for check, passed in validation_results.items() if not passed]
            
            if failed_checks:
                logger.error(
                    "Configuration validation failed",
                    extra={
                        "failed_checks": failed_checks,
                        "validation_results": validation_results
                    }
                )
                return False
            
            # Log successful validation
            logger.info(
                "Configuration validated successfully",
                extra={
                    "allowed_users_count": len(config.ALLOWED_USER_IDS),
                    "admin_users_count": len(config.ALLOWED_ADMIN_IDS),
                    "port": config.PORT,
                    "rate_limit_per_min": config.RATE_LIMIT_PER_MIN
                }
            )
            
            return True
            
        except ValueError as e:
            logger.error(
                "Configuration validation error",
                extra={
                    "error": str(e),
                    "missing_vars": str(e).split(': ')[1] if ': ' in str(e) else "Unknown"
                }
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected configuration error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            return False
    
    async def start_health_server(self):
        """Start HTTP health monitoring server."""
        
        try:
            logger.info("Starting health server", extra={"port": config.PORT})
            
            # Create health app
            app = create_health_app()
            
            # Create runner and site
            from aiohttp import web
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(runner, '0.0.0.0', config.PORT)
            await site.start()
            
            self.health_app_runner = runner
            
            logger.info(
                "Health server started successfully",
                extra={
                    "port": config.PORT,
                    "endpoints": ["/", "/health"],
                    "bind_address": "0.0.0.0"
                }
            )
            
        except Exception as e:
            logger.error(
                "Health server startup failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "port": config.PORT
                }
            )
            raise
    
    async def start_bot(self):
        """Start the Telegram bot."""
        
        try:
            logger.info("Starting Telegram bot")
            
            # Import bot here to avoid circular imports
            from umbra.bot import UmbraBot
            
            self.bot = UmbraBot(config)
            
            # Start the bot (this will run indefinitely until stopped)
            await self.bot.start()
            
            logger.info("Telegram bot stopped")
            
        except Exception as e:
            logger.error(
                "Bot startup failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise
    
    async def shutdown(self):
        """Clean shutdown with comprehensive cleanup."""
        
        logger.info("Shutdown initiated")
        
        shutdown_results = {}
        
        # Shutdown bot
        if self.bot:
            try:
                await self.bot.shutdown()
                shutdown_results["bot"] = "success"
                logger.info("Bot shutdown completed")
            except Exception as e:
                shutdown_results["bot"] = f"error: {e}"
                logger.warning("Bot shutdown error", extra={"error": str(e)})
        
        # Shutdown health server
        if self.health_app_runner:
            try:
                await self.health_app_runner.cleanup()
                shutdown_results["health_server"] = "success"
                logger.info("Health server shutdown completed")
            except Exception as e:
                shutdown_results["health_server"] = f"error: {e}"
                logger.warning("Health server shutdown error", extra={"error": str(e)})
        
        logger.info(
            "Shutdown completed",
            extra={"shutdown_results": shutdown_results}
        )
    
    async def run(self):
        """Main run method with proper error handling and graceful shutdown."""
        
        try:
            # Start health server first
            await self.start_health_server()
            
            # Set up signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                logger.info(
                    "Shutdown signal received",
                    extra={
                        "signal": signum,
                        "signal_name": signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
                    }
                )
                # Signal the bot to stop
                if self.bot:
                    self.bot.stop()
            
            # Register signal handlers (works on Unix systems)
            try:
                signal.signal(signal.SIGTERM, signal_handler)
                signal.signal(signal.SIGINT, signal_handler)
                logger.info("Signal handlers registered")
            except (ValueError, AttributeError):
                # Windows or other platforms might not support all signals
                logger.info("Signal handlers not available on this platform")
            
            logger.info("All services started, starting bot")
            
            # Start bot (this will run until stopped)
            await self.start_bot()
            
        except Exception as e:
            logger.error(
                "Runtime error in main loop",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise
        finally:
            await self.shutdown()

def main():
    """Main entry point with comprehensive error handling."""
    
    print("="*60)
    print("🤖 Umbra MCP v3.0.0")
    print("🏭 Railway Production Build")
    print("💬 Claude Desktop-style AI with MCP Modules")
    print("🛠️ 5 specialized modules for complete control")
    print("="*60)
    print()
    
    try:
        launcher = UmbraLauncher()
        
        # Setup environment
        launcher.setup_environment()
        
        # Validate configuration
        if not launcher.validate_config():
            logger.error("Fix configuration and restart")
            print("❌ Configuration validation failed. Check logs for details.")
            print("💡 Ensure TELEGRAM_BOT_TOKEN, ALLOWED_USER_IDS, and ALLOWED_ADMIN_IDS are set")
            return 1
        
        # Run the application
        asyncio.run(launcher.run())
        return 0
        
    except KeyboardInterrupt:
        logger.info("Stopped by user (KeyboardInterrupt)")
        print("👋 Stopped by user")
        return 0
    except Exception as e:
        logger.error(
            "Fatal startup error",
            extra={
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        print(f"❌ Fatal error: {e}")
        print("📋 Check logs for detailed error information")
        return 1

if __name__ == "__main__":
    sys.exit(main())
