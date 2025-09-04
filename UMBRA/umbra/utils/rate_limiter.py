"""
Rate limiting utilities for Umbra bot.
"""

import time
import logging
from typing import Dict, List
from collections import defaultdict, deque


class RateLimiter:
    """
    Token bucket rate limiter for bot users.
    """
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.logger = logging.getLogger(__name__)
        
        # Store request timestamps for each user
        self.user_requests: Dict[int, deque] = defaultdict(deque)
        
        self.logger.info(f"⏱️ Rate limiter initialized: {max_requests} requests per {window_seconds}s")
    
    def is_allowed(self, user_id: int) -> bool:
        """
        Check if user is allowed to make a request.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        user_queue = self.user_requests[user_id]
        
        # Remove old requests outside the window
        while user_queue and user_queue[0] <= now - self.window_seconds:
            user_queue.popleft()
        
        # Check if user has exceeded the limit
        if len(user_queue) >= self.max_requests:
            self.logger.warning(f"⏱️ Rate limit exceeded for user {user_id}")
            return False
        
        # Add current request
        user_queue.append(now)
        return True
    
    def get_remaining_requests(self, user_id: int) -> int:
        """
        Get remaining requests for user in current window.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Number of remaining requests
        """
        now = time.time()
        user_queue = self.user_requests[user_id]
        
        # Remove old requests outside the window
        while user_queue and user_queue[0] <= now - self.window_seconds:
            user_queue.popleft()
        
        return max(0, self.max_requests - len(user_queue))
    
    def get_reset_time(self, user_id: int) -> float:
        """
        Get time until rate limit resets for user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Seconds until reset (0 if not rate limited)
        """
        user_queue = self.user_requests[user_id]
        
        if not user_queue or len(user_queue) < self.max_requests:
            return 0.0
        
        # Time until oldest request expires
        oldest_request = user_queue[0]
        reset_time = oldest_request + self.window_seconds - time.time()
        
        return max(0.0, reset_time)
    
    def reset_user(self, user_id: int):
        """
        Reset rate limit for specific user.
        
        Args:
            user_id: Telegram user ID
        """
        if user_id in self.user_requests:
            self.user_requests[user_id].clear()
            self.logger.info(f"⏱️ Rate limit reset for user {user_id}")
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with stats
        """
        now = time.time()
        active_users = 0
        total_requests = 0
        
        for user_id, requests in self.user_requests.items():
            # Count requests in current window
            recent_requests = sum(1 for req_time in requests 
                                if req_time > now - self.window_seconds)
            if recent_requests > 0:
                active_users += 1
                total_requests += recent_requests
        
        return {
            'max_requests_per_window': self.max_requests,
            'window_seconds': self.window_seconds,
            'active_users': active_users,
            'total_recent_requests': total_requests,
            'tracked_users': len(self.user_requests)
        }
    
    def cleanup_old_data(self):
        """
        Clean up old request data to prevent memory leaks.
        """
        now = time.time()
        users_to_remove = []
        
        for user_id, requests in self.user_requests.items():
            # Remove old requests
            while requests and requests[0] <= now - self.window_seconds:
                requests.popleft()
            
            # If no recent requests, mark user for removal
            if not requests:
                users_to_remove.append(user_id)
        
        # Remove users with no recent activity
        for user_id in users_to_remove:
            del self.user_requests[user_id]
        
        if users_to_remove:
            self.logger.debug(f"⏱️ Cleaned up data for {len(users_to_remove)} inactive users")


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts limits based on user behavior.
    """
    
    def __init__(self, base_max_requests: int = 10, window_seconds: int = 60):
        super().__init__(base_max_requests, window_seconds)
        self.base_max_requests = base_max_requests
        
        # Track user behavior
        self.user_violations: Dict[int, int] = defaultdict(int)
        self.user_multipliers: Dict[int, float] = defaultdict(lambda: 1.0)
        
        self.logger.info("🧠 Adaptive rate limiter initialized")
    
    def is_allowed(self, user_id: int) -> bool:
        """
        Check if user is allowed with adaptive limits.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if request is allowed, False if rate limited
        """
        # Get user's current limit
        user_limit = int(self.base_max_requests * self.user_multipliers[user_id])
        
        now = time.time()
        user_queue = self.user_requests[user_id]
        
        # Remove old requests outside the window
        while user_queue and user_queue[0] <= now - self.window_seconds:
            user_queue.popleft()
        
        # Check if user has exceeded their limit
        if len(user_queue) >= user_limit:
            # Record violation
            self.user_violations[user_id] += 1
            self._adjust_user_limit(user_id)
            
            self.logger.warning(
                f"⏱️ Adaptive rate limit exceeded for user {user_id} "
                f"(limit: {user_limit}, violations: {self.user_violations[user_id]})"
            )
            return False
        
        # Add current request
        user_queue.append(now)
        
        # Gradually improve user's standing if they're behaving well
        self._improve_user_standing(user_id)
        
        return True
    
    def _adjust_user_limit(self, user_id: int):
        """
        Adjust user's rate limit based on violations.
        
        Args:
            user_id: Telegram user ID
        """
        violations = self.user_violations[user_id]
        
        if violations >= 5:
            # Severe restriction
            self.user_multipliers[user_id] = 0.2
        elif violations >= 3:
            # Moderate restriction
            self.user_multipliers[user_id] = 0.5
        elif violations >= 1:
            # Light restriction
            self.user_multipliers[user_id] = 0.8
    
    def _improve_user_standing(self, user_id: int):
        """
        Gradually improve user's standing if they're behaving well.
        
        Args:
            user_id: Telegram user ID
        """
        # Improve multiplier slightly over time
        current_multiplier = self.user_multipliers[user_id]
        if current_multiplier < 1.0:
            # Improve by 1% per good request
            self.user_multipliers[user_id] = min(1.0, current_multiplier + 0.01)
        
        # Reduce violation count over time
        if self.user_violations[user_id] > 0:
            # Reduce violations every 100 good requests
            if len(self.user_requests[user_id]) % 100 == 0:
                self.user_violations[user_id] = max(0, self.user_violations[user_id] - 1)
    
    def reset_user(self, user_id: int):
        """
        Reset rate limit and behavior tracking for specific user.
        
        Args:
            user_id: Telegram user ID
        """
        super().reset_user(user_id)
        self.user_violations[user_id] = 0
        self.user_multipliers[user_id] = 1.0
        self.logger.info(f"🧠 Adaptive rate limit and behavior reset for user {user_id}")
