"""
Rate limiter module to ensure compliance with API usage policies.

This module provides rate limiting functionality with configurable limits,
ensuring that API calls respect the rate limits of external services.
For Nominatim, the limit is 1 request per second.
"""

import time
import threading
from typing import Dict, Optional, Callable
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Rate limiter implementation for API requests.
    
    Ensures that requests to APIs are made at a controlled rate,
    respecting the rate limits of external services.
    
    Args:
        requests_per_second: Number of requests allowed per second.
        retry_after: Number of seconds to wait before retrying if rate limit is hit.
    """
    
    def __init__(self, requests_per_second: float = 1.0, retry_after: int = 1):
        self.requests_per_second = requests_per_second
        self.retry_after = retry_after
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time: Dict[str, float] = {}
        self.lock = threading.RLock()
        
    def wait(self, key: str = "default") -> None:
        """
        Wait until a request is allowed based on the rate limit.
        
        Args:
            key: Identifier for different rate limiting contexts.
        """
        with self.lock:
            if key in self.last_request_time:
                elapsed = time.time() - self.last_request_time[key]
                if elapsed < self.min_interval:
                    sleep_time = self.min_interval - elapsed
                    logger.debug(f"Rate limiting: waiting {sleep_time:.2f}s for {key}")
                    time.sleep(sleep_time)
            
            self.last_request_time[key] = time.time()
    
    def limit(self, func: Callable) -> Callable:
        """
        Decorator to apply rate limiting to a function.
        
        Args:
            func: The function to wrap with rate limiting.
            
        Returns:
            The wrapped function with rate limiting applied.
        """
        def wrapper(*args, **kwargs):
            key = kwargs.get("rate_limit_key", "default")
            self.wait(key)
            return func(*args, **kwargs)
        return wrapper
    
    def execute_with_retry(self, func: Callable, *args, max_retries: int = 3, 
                         backoff_factor: float = 2.0, rate_limit_key: str = "default", 
                         **kwargs):
        """
        Execute a function with retries on rate limit errors.
        
        Args:
            func: The function to execute.
            *args: Arguments to pass to the function.
            max_retries: Maximum number of retries.
            backoff_factor: Exponential backoff factor.
            rate_limit_key: Key for rate limiting context.
            **kwargs: Keyword arguments to pass to the function.
            
        Returns:
            The result of the function call.
            
        Raises:
            Exception: The last exception encountered if all retries fail.
        """
        retries = 0
        while True:
            try:
                self.wait(rate_limit_key)
                return func(*args, **kwargs)
            except Exception as e:
                retries += 1
                if retries >= max_retries:
                    logger.error(f"Max retries ({max_retries}) exceeded, giving up.")
                    raise
                
                # Calculate backoff time
                wait_time = self.retry_after * (backoff_factor ** (retries - 1))
                logger.warning(f"Request failed, retrying in {wait_time:.2f}s ({retries}/{max_retries}): {str(e)}")
                time.sleep(wait_time)

# Default instance for Nominatim API with 1 request per second limit
nominatim_limiter = RateLimiter(requests_per_second=1.0)
