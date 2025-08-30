"""Retry utilities for Umbra services."""

import asyncio
import random
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from functools import wraps
from .logger import UmbraLogger

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry logic."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


class RetryUtils:
    """Utility class for retry logic."""
    
    def __init__(self):
        self.logger = UmbraLogger("RetryUtils")
    
    @staticmethod
    def create_retry_config(config_type: str = "default") -> RetryConfig:
        """Create predefined retry configurations."""
        configs = {
            "default": RetryConfig(max_attempts=3, base_delay=1.0),
            "api": RetryConfig(max_attempts=3, base_delay=2.0, max_delay=30.0),
            "critical": RetryConfig(max_attempts=5, base_delay=1.0, max_delay=60.0),
            "fast": RetryConfig(max_attempts=2, base_delay=0.5, max_delay=5.0)
        }
        return configs.get(config_type, configs["default"])
    
    def calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for a given attempt."""
        delay = config.base_delay * (config.exponential_base ** (attempt - 1))
        delay = min(delay, config.max_delay)
        
        if config.jitter:
            # Add jitter (±25% of delay)
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    async def retry_async(
        self,
        func: Callable[..., T],
        config: Optional[RetryConfig] = None,
        retryable_exceptions: tuple = (Exception,),
        *args,
        **kwargs
    ) -> T:
        """Retry an async function with exponential backoff."""
        if config is None:
            config = self.create_retry_config()
        
        last_exception = None
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                result = await func(*args, **kwargs)
                if attempt > 1:
                    self.logger.info(f"Function succeeded on attempt {attempt}")
                return result
                
            except retryable_exceptions as e:
                last_exception = e
                
                if attempt == config.max_attempts:
                    self.logger.error(
                        f"Function failed after {config.max_attempts} attempts",
                        error=str(e),
                        function_name=getattr(func, '__name__', 'unknown')
                    )
                    break
                
                delay = self.calculate_delay(attempt, config)
                self.logger.warning(
                    f"Attempt {attempt} failed, retrying in {delay:.2f}s",
                    error=str(e),
                    function_name=getattr(func, '__name__', 'unknown')
                )
                
                await asyncio.sleep(delay)
        
        # Re-raise the last exception
        if last_exception:
            raise last_exception
        
        raise RuntimeError("Retry logic failed unexpectedly")
    
    def retry_sync(
        self,
        func: Callable[..., T],
        config: Optional[RetryConfig] = None,
        retryable_exceptions: tuple = (Exception,),
        *args,
        **kwargs
    ) -> T:
        """Retry a sync function with exponential backoff."""
        if config is None:
            config = self.create_retry_config()
        
        last_exception = None
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                result = func(*args, **kwargs)
                if attempt > 1:
                    self.logger.info(f"Function succeeded on attempt {attempt}")
                return result
                
            except retryable_exceptions as e:
                last_exception = e
                
                if attempt == config.max_attempts:
                    self.logger.error(
                        f"Function failed after {config.max_attempts} attempts",
                        error=str(e),
                        function_name=getattr(func, '__name__', 'unknown')
                    )
                    break
                
                delay = self.calculate_delay(attempt, config)
                self.logger.warning(
                    f"Attempt {attempt} failed, retrying in {delay:.2f}s",
                    error=str(e),
                    function_name=getattr(func, '__name__', 'unknown')
                )
                
                import time
                time.sleep(delay)
        
        # Re-raise the last exception
        if last_exception:
            raise last_exception
        
        raise RuntimeError("Retry logic failed unexpectedly")


def retry_async(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple = (Exception,)
):
    """Decorator for async functions with retry logic."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            retry_utils = RetryUtils()
            return await retry_utils.retry_async(
                func, config, retryable_exceptions, *args, **kwargs
            )
        return wrapper
    return decorator


def retry_sync(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple = (Exception,)
):
    """Decorator for sync functions with retry logic."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            retry_utils = RetryUtils()
            return retry_utils.retry_sync(
                func, config, retryable_exceptions, *args, **kwargs
            )
        return wrapper
    return decorator