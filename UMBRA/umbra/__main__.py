"""Main entry point for Umbra bot."""
import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to Python path for development
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from umbra.bot import UmbraBot
from umbra.core.config import config
from umbra.core.logger import setup_logging
from umbra.core.config_validation import ConfigValidator

def validate_startup_environment():
    """Validate environment variables and configuration before starting bot."""
    logger = logging.getLogger(__name__)
    
    try:
        # Run comprehensive config validation
        validator = ConfigValidator()
        issues = validator.validate_all()
        
        # Count issues by severity
        errors = [i for i in issues if i.level == 'error']
        warnings = [i for i in issues if i.level == 'warning']
        
        # Log summary
        if issues:
            logger.info(f"Configuration validation: {len(errors)} errors, {len(warnings)} warnings")
        else:
            logger.info("Configuration validation: All checks passed")
        
        # Log errors and warnings
        for issue in errors:
            logger.error(f"Config {issue.component}: {issue.message}")
            if issue.suggestion:
                logger.error(f"  Suggestion: {issue.suggestion}")
        
        for issue in warnings:
            logger.warning(f"Config {issue.component}: {issue.message}")
            if issue.suggestion:
                logger.warning(f"  Suggestion: {issue.suggestion}")
        
        # Stop on critical errors
        if errors:
            logger.error("Critical configuration errors found. Please fix them before starting the bot.")
            sys.exit(1)
        
        return True
        
    except Exception as e:
        logger.exception("Failed to validate configuration")
        sys.exit(1)

async def main():
    """Main entry point for the bot."""
    # Setup logging
    setup_logging(config.LOG_LEVEL)
    logger = logging.getLogger(__name__)
    
    # Validate environment before proceeding
    logger.info("Starting Umbra Bot v2.0.0 - Production Mode")
    validate_startup_environment()
    
    try:
        logger.info("Environment validation passed, initializing bot...")
        
        # Initialize and start the bot
        # The bot now manages its own lifecycle including idle() and shutdown
        bot = UmbraBot(config)
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception("Bot crashed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
