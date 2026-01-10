"""Rate limiter for LLM API calls to prevent quota exceeded errors."""
import asyncio
import threading
import time
import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket / sliding window rate limiter for LLM API calls.
    
    This rate limiter tracks requests in a sliding window and ensures
    that the number of requests doesn't exceed the configured limit
    per minute.
    
    Thread-safe and async-compatible for use in both sync (Celery workers)
    and async (FastAPI) contexts.
    """
    
    def __init__(self, requests_per_minute: int):
        """
        Initialize the rate limiter.
        
        Args:
            requests_per_minute: Maximum number of requests allowed per minute
        """
        self.requests_per_minute = requests_per_minute
        self.window_size = 60.0  # 1 minute in seconds
        self._request_times: deque = deque()
        self._lock = threading.Lock()
        self._async_lock: Optional[asyncio.Lock] = None
        
        logger.info(f"Rate limiter initialized: {requests_per_minute} requests/minute")
    
    def _get_async_lock(self) -> asyncio.Lock:
        """Get or create the async lock (must be called from async context)."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock
    
    def _cleanup_old_requests(self) -> None:
        """Remove requests older than the window size."""
        current_time = time.time()
        cutoff_time = current_time - self.window_size
        
        while self._request_times and self._request_times[0] < cutoff_time:
            self._request_times.popleft()
    
    def _get_wait_time(self) -> float:
        """
        Calculate how long to wait before the next request can be made.
        
        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        self._cleanup_old_requests()
        
        if len(self._request_times) < self.requests_per_minute:
            return 0.0
        
        # Calculate when the oldest request will expire
        oldest_request = self._request_times[0]
        wait_time = oldest_request + self.window_size - time.time()
        
        return max(0.0, wait_time)
    
    def _record_request(self) -> None:
        """Record a new request timestamp."""
        self._request_times.append(time.time())
    
    def wait_sync(self) -> None:
        """
        Synchronous wait - blocks until a request slot is available.
        
        Use this in synchronous contexts like Celery workers.
        """
        with self._lock:
            wait_time = self._get_wait_time()
            
            if wait_time > 0:
                logger.info(f"Rate limit reached. Waiting {wait_time:.2f}s before next LLM request")
                time.sleep(wait_time)
                # Recalculate after sleep
                self._cleanup_old_requests()
            
            self._record_request()
            current_count = len(self._request_times)
            logger.debug(f"LLM request recorded. {current_count}/{self.requests_per_minute} in current window")
    
    async def wait_async(self) -> None:
        """
        Asynchronous wait - awaits until a request slot is available.
        
        Use this in async contexts like FastAPI endpoints.
        """
        async with self._get_async_lock():
            # Use the thread lock for the actual state manipulation
            with self._lock:
                wait_time = self._get_wait_time()
            
            if wait_time > 0:
                logger.info(f"Rate limit reached. Waiting {wait_time:.2f}s before next LLM request")
                await asyncio.sleep(wait_time)
                # Recalculate after sleep
                with self._lock:
                    self._cleanup_old_requests()
            
            with self._lock:
                self._record_request()
                current_count = len(self._request_times)
            
            logger.debug(f"LLM request recorded. {current_count}/{self.requests_per_minute} in current window")
    
    def get_current_usage(self) -> dict:
        """
        Get current rate limit usage statistics.
        
        Returns:
            Dictionary with usage stats
        """
        with self._lock:
            self._cleanup_old_requests()
            current_count = len(self._request_times)
            
            return {
                "requests_in_window": current_count,
                "requests_per_minute_limit": self.requests_per_minute,
                "remaining_requests": max(0, self.requests_per_minute - current_count),
                "window_size_seconds": self.window_size
            }


# Singleton instance - initialized lazily
_rate_limiter: Optional[RateLimiter] = None
_init_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """
    Get the singleton rate limiter instance.
    
    Initializes the rate limiter with settings from config on first call.
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        with _init_lock:
            if _rate_limiter is None:
                from app.config import settings
                _rate_limiter = RateLimiter(settings.llm_requests_per_minute)
    
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the rate limiter (useful for testing)."""
    global _rate_limiter
    with _init_lock:
        _rate_limiter = None

