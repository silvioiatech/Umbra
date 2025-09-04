"""
Logging utilities for Umbra bot.
"""

import logging
import re
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: str | None = None):
    """
    Setup logging configuration for the bot.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    # Create formatters
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        try:
            # Create log directory if it doesn't exist
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
            root_logger.addHandler(file_handler)

        except Exception as e:
            root_logger.warning(f"Could not setup file logging: {e}")

    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    root_logger.info("🔧 Logging setup complete")


def setup_logger(log_level: str = "INFO", log_file: str | None = None):
    """Backward-compatible wrapper expected by other modules; delegates to setup_logging."""
    return setup_logging(log_level=log_level, log_file=log_file)


class SanitizedLogger:
    """
    Logger wrapper that sanitizes sensitive information.
    """

    def __init__(self, logger: logging.Logger, sanitize_sensitive: bool = True):
        self.logger = logger
        self.sanitize_sensitive = sanitize_sensitive
        self.sensitive_patterns = [
            "token",
            "key",
            "secret",
            "password",
            "auth",
            "api_key",
            "bot_token",
            "webhook",
        ]

    def _sanitize_message(self, message: str) -> str:
        """
        Sanitize sensitive information from log messages.
        """
        if not self.sanitize_sensitive:
            return message

        sanitized = message
        for pattern in self.sensitive_patterns:
            if pattern.lower() in sanitized.lower():
                # Replace potential sensitive values
                # Pattern to match key=value or key: value
                pattern_regex = rf"{pattern}[\s]*[=:][\s]*[\w\-_]+"
                sanitized = re.sub(pattern_regex, f"{pattern}=***", sanitized, flags=re.IGNORECASE)

        return sanitized

    def debug(self, message: str, *args, **kwargs):
        self.logger.debug(self._sanitize_message(message), *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self.logger.info(self._sanitize_message(message), *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self.logger.warning(self._sanitize_message(message), *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self.logger.error(self._sanitize_message(message), *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self.logger.critical(self._sanitize_message(message), *args, **kwargs)
