"""
Cache manager module for managing the Nominatim cache.

This module provides high-level cache management functions that use
the SQLiteCache implementation for storing and retrieving Nominatim results.
"""

import hashlib
import json
from typing import Dict, List, Optional, Any, Union, Callable
import logging
import threading
import time
import os

from place2polygon.cache.sqlite_cache import SQLiteCache, default_cache

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Manager for the Nominatim cache.
    
    Args:
        cache: The cache implementation to use.
        auto_cleanup_interval: Interval for automatic cleanup in seconds (0 to disable).
        cache_prefix: Prefix for cache keys.
    """
    
    def __init__(
        self,
        cache: SQLiteCache = default_cache,
        auto_cleanup_interval: int = 3600 * 24,  # Once per day
        cache_prefix: str = "nominatim_"
    ):
        """Initialize the cache manager."""
        self.cache = cache
        self.auto_cleanup_interval = auto_cleanup_interval
        self.cache_prefix = cache_prefix
        self._cleanup_thread = None
        self._stop_cleanup = threading.Event()
        
        # Start auto-cleanup if enabled
        if auto_cleanup_interval > 0:
            self._start_auto_cleanup()
    
    def _start_auto_cleanup(self) -> None:
        """Start the automatic cleanup thread."""
        def cleanup_task():
            while not self._stop_cleanup.is_set():
                try:
                    # Sleep first to avoid immediate cleanup on startup
                    self._stop_cleanup.wait(self.auto_cleanup_interval)
                    if not self._stop_cleanup.is_set():
                        cleared = self.cache.clear_expired()
                        logger.info(f"Auto-cleanup cleared {cleared} expired cache entries")
                except Exception as e:
                    logger.error(f"Error in auto-cleanup task: {str(e)}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        self._cleanup_thread.start()
    
    def stop(self) -> None:
        """Stop the cache manager (cleanup thread)."""
        if self._cleanup_thread:
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=1.0)
            self._cleanup_thread = None
    
    def _generate_key(self, *args, **kwargs) -> str:
        """
        Generate a cache key from the arguments.
        
        Args:
            *args: Positional arguments to include in the key.
            **kwargs: Keyword arguments to include in the key.
            
        Returns:
            The generated cache key.
        """
        # Create a hashable representation of the arguments
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        
        # Generate a consistent JSON string
        key_json = json.dumps(key_data, sort_keys=True)
        
        # Generate an MD5 hash of the JSON string
        key_hash = hashlib.md5(key_json.encode('utf-8')).hexdigest()
        
        # Combine prefix and hash
        return f"{self.cache_prefix}{key_hash}"
    
    def get_cached_result(self, *args, **kwargs) -> Optional[Any]:
        """
        Get a cached result.
        
        Args:
            *args: Positional arguments used to generate the cache key.
            **kwargs: Keyword arguments used to generate the cache key.
            
        Returns:
            The cached result, or None if not found or expired.
        """
        key = self._generate_key(*args, **kwargs)
        result = self.cache.get(key)
        
        if result is not None:
            self.cache.record_hit()
            logger.debug(f"Cache hit for key: {key}")
            return result
        else:
            self.cache.record_miss()
            logger.debug(f"Cache miss for key: {key}")
            return None
    
    def cache_result(self, result: Any, ttl: Optional[int] = None, *args, **kwargs) -> None:
        """
        Cache a result.
        
        Args:
            result: The result to cache.
            ttl: Time-to-live in days, or None to use the default.
            *args: Positional arguments used to generate the cache key.
            **kwargs: Keyword arguments used to generate the cache key.
        """
        key = self._generate_key(*args, **kwargs)
        success = self.cache.set(key, result, ttl)
        if success:
            logger.debug(f"Cached result for key: {key}")
        else:
            logger.warning(f"Failed to cache result for key: {key}")
    
    def invalidate_cached_result(self, *args, **kwargs) -> bool:
        """
        Invalidate a cached result.
        
        Args:
            *args: Positional arguments used to generate the cache key.
            **kwargs: Keyword arguments used to generate the cache key.
            
        Returns:
            True if the result was invalidated, False otherwise.
        """
        key = self._generate_key(*args, **kwargs)
        return self.cache.invalidate(key)
    
    def wrapped_with_cache(self, func: Callable, ttl: Optional[int] = None) -> Callable:
        """
        Wrap a function with caching.
        
        Args:
            func: The function to wrap.
            ttl: Time-to-live in days, or None to use the default.
            
        Returns:
            The wrapped function.
        """
        def wrapper(*args, **kwargs):
            # Check if skip_cache flag is set
            skip_cache = kwargs.pop('skip_cache', False)
            
            if not skip_cache:
                # Try to get from cache
                cached_result = self.get_cached_result(func.__name__, *args, **kwargs)
                if cached_result is not None:
                    return cached_result
            
            # Call the function
            result = func(*args, **kwargs)
            
            # Cache the result (unless skip_cache is set)
            if not skip_cache:
                self.cache_result(result, ttl, func.__name__, *args, **kwargs)
            
            return result
        
        return wrapper
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary of cache statistics.
        """
        return self.cache.get_stats()
    
    def clear_expired_entries(self) -> int:
        """
        Clear expired cache entries.
        
        Returns:
            Number of entries cleared.
        """
        return self.cache.clear_expired()
    
    def clear_all_entries(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if successful, False otherwise.
        """
        return self.cache.clear_all()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache by key.
        
        Args:
            key: Cache key.
            
        Returns:
            The cached value, or None if not found or expired.
        """
        return self.cache.get(f"{self.cache_prefix}{key}")
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store a value in the cache.
        
        Args:
            key: Cache key.
            value: Value to store.
            ttl: Time-to-live in days.
        """
        self.cache.set(f"{self.cache_prefix}{key}", value, ttl=ttl)

# Create a default instance
default_manager = CacheManager()
