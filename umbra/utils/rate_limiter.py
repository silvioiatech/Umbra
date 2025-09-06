"""
Rate limiting functionality for Umbra bot.
Implements per-user rate limiting with configurable limits and time windows.
"""
import time
import asyncio
from typing import Dict, Optional
from collections import defaultdict, deque
from dataclasses import dataclass
from contextlib import asynccontextmanager

from ..core.config import config
from ..core.logger import get_context_logger

logger = get_context_logger(__name__)

@dataclass
class RateLimitEntry:
    """Rate limit tracking entry for a user."""
    requests: deque
    last_reset: float
    
    def __post_init__(self):
        if not hasattr(self.requests, 'maxlen'):
            self.requests = deque(self.requests, maxlen=config.RATE_LIMIT_PER_MIN)

class RateLimiter:
    """Per-user rate limiter with time window tracking."""
    
    def __init__(self):
        self.limits: Dict[int, RateLimitEntry] = defaultdict(
            lambda: RateLimitEntry(deque(maxlen=config.RATE_LIMIT_PER_MIN), time.time())
        )
        self.window_seconds = 60  # 1 minute window
        self.cleanup_interval = 300  # Clean up old entries every 5 minutes
        self.last_cleanup = time.time()
        
        logger.info(
            "Rate limiter initialized",
            extra={
                "rate_limit_per_min": config.RATE_LIMIT_PER_MIN,
                "window_seconds": self.window_seconds,
                "enabled": config.RATE_LIMIT_ENABLED
            }
        )
    
    def is_allowed(self, user_id: int) -> bool:
        """Check if user is within rate limit."""
        
        # Skip rate limiting if disabled
        if not config.RATE_LIMIT_ENABLED:
            return True
        
        current_time = time.time()
        
        # Cleanup old entries periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(current_time)
            self.last_cleanup = current_time
        
        # Get or create user's rate limit entry
        user_limit = self.limits[user_id]
        
        # Remove requests older than the time window
        cutoff_time = current_time - self.window_seconds
        while user_limit.requests and user_limit.requests[0] < cutoff_time:
            user_limit.requests.popleft()
        
        # Check if user is within limits
        if len(user_limit.requests) >= config.RATE_LIMIT_PER_MIN:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "user_id": user_id,
                    "current_requests": len(user_limit.requests),
                    "limit": config.RATE_LIMIT_PER_MIN,
                    "window_seconds": self.window_seconds
                }
            )
            return False
        
        # Add current request
        user_limit.requests.append(current_time)
        
        logger.debug(
            "Rate limit check passed",
            extra={
                "user_id": user_id,
                "current_requests": len(user_limit.requests),
                "limit": config.RATE_LIMIT_PER_MIN
            }
        )
        
        return True
    
    def get_reset_time(self, user_id: int) -> Optional[float]:
        """Get when the rate limit resets for a user."""
        if user_id not in self.limits or not self.limits[user_id].requests:
            return None
        
        oldest_request = self.limits[user_id].requests[0]
        return oldest_request + self.window_seconds
    
    def get_remaining_requests(self, user_id: int) -> int:
        """Get remaining requests for a user in the current window."""
        if not config.RATE_LIMIT_ENABLED:
            return config.RATE_LIMIT_PER_MIN
        
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        if user_id not in self.limits:
            return config.RATE_LIMIT_PER_MIN
        
        user_limit = self.limits[user_id]
        
        # Count requests in current window
        current_requests = sum(1 for req_time in user_limit.requests if req_time > cutoff_time)
        return max(0, config.RATE_LIMIT_PER_MIN - current_requests)
    
    def _cleanup_old_entries(self, current_time: float):
        """Clean up rate limit entries for users who haven't made requests recently."""
        cutoff_time = current_time - (self.window_seconds * 2)  # Keep entries for 2x window
        
        users_to_remove = []
        for user_id, entry in self.limits.items():
            if not entry.requests or entry.requests[-1] < cutoff_time:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.limits[user_id]
        
        if users_to_remove:
            logger.debug(
                "Rate limiter cleanup completed",
                extra={
                    "removed_users": len(users_to_remove),
                    "remaining_users": len(self.limits)
                }
            )
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        active_users = 0
        total_requests_in_window = 0
        
        for entry in self.limits.values():
            requests_in_window = sum(1 for req_time in entry.requests if req_time > cutoff_time)
            if requests_in_window > 0:
                active_users += 1
                total_requests_in_window += requests_in_window
        
        return {
            "enabled": config.RATE_LIMIT_ENABLED,
            "limit_per_minute": config.RATE_LIMIT_PER_MIN,
            "window_seconds": self.window_seconds,
            "active_users": active_users,
            "total_tracked_users": len(self.limits),
            "requests_in_current_window": total_requests_in_window
        }

# Global rate limiter instance
rate_limiter = RateLimiter()

@asynccontextmanager
async def rate_limit_check(user_id: int):
    """Context manager for rate limit checking with logging."""
    
    if not rate_limiter.is_allowed(user_id):
        reset_time = rate_limiter.get_reset_time(user_id)
        wait_seconds = reset_time - time.time() if reset_time else 60
        
        logger.warning(
            "Rate limit exceeded for user",
            extra={
                "user_id": user_id,
                "wait_seconds": wait_seconds,
                "limit": config.RATE_LIMIT_PER_MIN
            }
        )
        
        # Could raise an exception here or return a specific error
        # For now, we'll let the caller handle it
        yield False
        return
    
    yield True

# Export
__all__ = ["RateLimiter", "rate_limiter", "rate_limit_check"]
