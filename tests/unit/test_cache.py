"""
Unit tests for the caching system.
"""

import os
import json
import time
import pytest
from unittest.mock import patch, MagicMock

from place2polygon.cache.sqlite_cache import SQLiteCache
from place2polygon.cache.cache_manager import CacheManager


class TestSQLiteCache:
    """Tests for the SQLiteCache class."""
    
    def test_init(self, temp_db_path):
        """Test initializing the cache."""
        cache = SQLiteCache(db_path=temp_db_path)
        
        assert cache.db_path == temp_db_path
        assert cache.default_ttl == 30
        assert os.path.exists(temp_db_path)
    
    def test_get_missing_key(self, temp_cache):
        """Test getting a non-existent key."""
        result = temp_cache.get("nonexistent_key")
        
        assert result is None
    
    def test_set_and_get(self, temp_cache):
        """Test setting and getting a value."""
        # Set a value
        test_data = {"name": "Seattle", "type": "city"}
        success = temp_cache.set("test_key", test_data)
        
        assert success is True
        
        # Get the value
        result = temp_cache.get("test_key")
        
        assert result == test_data
    
    def test_set_and_get_complex_data(self, temp_cache):
        """Test setting and getting a complex value with nested structures."""
        # Complex test data with nested structures and different data types
        test_data = {
            "name": "Seattle",
            "coordinates": [47.6062, -122.3321],
            "properties": {
                "population": 724305,
                "is_capital": False,
                "neighborhoods": ["Downtown", "Capitol Hill", "Ballard"]
            },
            "founded": None
        }
        
        # Set the value
        success = temp_cache.set("complex_key", test_data)
        assert success is True
        
        # Get the value
        result = temp_cache.get("complex_key")
        assert result == test_data
    
    def test_ttl_expiration(self, temp_db_path):
        """Test that values expire based on TTL."""
        # Create cache with a very short TTL
        cache = SQLiteCache(db_path=temp_db_path, default_ttl=0.001)  # ~0.1 seconds
        
        # Set a value
        test_data = {"name": "Seattle"}
        cache.set("expiring_key", test_data)
        
        # Verify it exists initially
        assert cache.get("expiring_key") is not None
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Value should be expired now
        assert cache.get("expiring_key") is None
    
    def test_custom_ttl(self, temp_cache):
        """Test setting a custom TTL for a specific entry."""
        # Set with custom TTL (very short)
        test_data = {"name": "Seattle"}
        temp_cache.set("custom_ttl_key", test_data, ttl=0.001)  # ~0.1 seconds
        
        # Verify it exists initially
        assert temp_cache.get("custom_ttl_key") is not None
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Value should be expired now
        assert temp_cache.get("custom_ttl_key") is None
    
    def test_invalidate(self, temp_cache):
        """Test invalidating a cache entry."""
        # Set a value
        test_data = {"name": "Seattle"}
        temp_cache.set("invalidate_key", test_data)
        
        # Verify it exists
        assert temp_cache.get("invalidate_key") is not None
        
        # Invalidate it
        result = temp_cache.invalidate("invalidate_key")
        
        assert result is True
        assert temp_cache.get("invalidate_key") is None
    
    def test_clear_expired(self, temp_db_path):
        """Test clearing expired entries."""
        # Create cache with a very short TTL
        cache = SQLiteCache(db_path=temp_db_path, default_ttl=0.001)
        
        # Set some values
        cache.set("expired1", {"name": "value1"})
        cache.set("expired2", {"name": "value2"})
        cache.set("not_expired", {"name": "value3"}, ttl=1)  # 1 day
        
        # Wait for some to expire
        time.sleep(0.2)
        
        # Clear expired entries
        cleared = cache.clear_expired()
        
        # Two entries should have been cleared
        assert cleared == 2
        
        # Verify expired entries are gone and the non-expired one remains
        assert cache.get("expired1") is None
        assert cache.get("expired2") is None
        assert cache.get("not_expired") is not None
    
    def test_clear_all(self, temp_cache):
        """Test clearing all cache entries."""
        # Set some values
        temp_cache.set("key1", {"name": "value1"})
        temp_cache.set("key2", {"name": "value2"})
        
        # Verify they exist
        assert temp_cache.get("key1") is not None
        assert temp_cache.get("key2") is not None
        
        # Clear all entries
        result = temp_cache.clear_all()
        
        assert result is True
        assert temp_cache.get("key1") is None
        assert temp_cache.get("key2") is None
    
    def test_get_stats(self, temp_cache):
        """Test getting cache statistics."""
        # Set some values
        temp_cache.set("stat_key1", {"name": "value1"})
        temp_cache.set("stat_key2", {"name": "value2"})
        
        # Get some values (to increment hit count)
        temp_cache.get("stat_key1")
        temp_cache.get("stat_key1")  # Second hit
        temp_cache.get("nonexistent")  # Miss
        
        # Record hits and misses
        temp_cache.record_hit()
        temp_cache.record_hit()
        temp_cache.record_miss()
        
        # Get statistics
        stats = temp_cache.get_stats()
        
        # Verify basic stats
        assert "total_entries" in stats
        assert stats["total_entries"] == 2
        assert "total_size_bytes" in stats
        assert "hit_count" in stats
        assert "miss_count" in stats


class TestCacheManager:
    """Tests for the CacheManager class."""
    
    def test_init(self, temp_cache):
        """Test initializing the cache manager."""
        manager = CacheManager(cache=temp_cache, auto_cleanup_interval=0)
        
        assert manager.cache == temp_cache
        assert manager.auto_cleanup_interval == 0
    
    def test_generate_key(self, temp_cache_manager):
        """Test generating cache keys."""
        # Generate key with simple args
        key1 = temp_cache_manager._generate_key("test_method", "arg1", "arg2")
        
        # Same args should generate the same key
        key2 = temp_cache_manager._generate_key("test_method", "arg1", "arg2")
        assert key1 == key2
        
        # Different args should generate different keys
        key3 = temp_cache_manager._generate_key("test_method", "arg1", "different")
        assert key1 != key3
        
        # kwargs should affect the key
        key4 = temp_cache_manager._generate_key("test_method", "arg1", "arg2", kwarg1="value")
        assert key1 != key4
        
        # Order of kwargs shouldn't matter
        key5 = temp_cache_manager._generate_key("test_method", "arg1", "arg2", kwarg2="value2", kwarg1="value")
        key6 = temp_cache_manager._generate_key("test_method", "arg1", "arg2", kwarg1="value", kwarg2="value2")
        assert key5 == key6
    
    def test_get_cached_result_miss(self, temp_cache_manager):
        """Test getting a cache miss."""
        result = temp_cache_manager.get_cached_result("test_method", "arg1")
        
        assert result is None
    
    def test_cache_and_get_result(self, temp_cache_manager):
        """Test caching and retrieving a result."""
        # Cache a result
        test_data = {"name": "Seattle", "type": "city"}
        temp_cache_manager.cache_result(test_data, None, "test_method", "arg1")
        
        # Get the result
        result = temp_cache_manager.get_cached_result("test_method", "arg1")
        
        assert result == test_data
    
    def test_invalidate_cached_result(self, temp_cache_manager):
        """Test invalidating a cached result."""
        # Cache a result
        test_data = {"name": "Seattle", "type": "city"}
        temp_cache_manager.cache_result(test_data, None, "test_method", "arg1")
        
        # Verify it exists
        assert temp_cache_manager.get_cached_result("test_method", "arg1") is not None
        
        # Invalidate it
        result = temp_cache_manager.invalidate_cached_result("test_method", "arg1")
        
        assert result is True
        assert temp_cache_manager.get_cached_result("test_method", "arg1") is None
    
    def test_wrapped_with_cache(self, temp_cache_manager):
        """Test the function wrapping functionality."""
        # Define a function to wrap
        call_count = 0
        
        def test_function(arg1, arg2=None):
            nonlocal call_count
            call_count += 1
            return {"result": f"{arg1}-{arg2}", "call_count": call_count}
        
        # Wrap the function
        wrapped_func = temp_cache_manager.wrapped_with_cache(test_function)
        
        # First call should execute the function
        result1 = wrapped_func("value1", arg2="value2")
        assert result1["call_count"] == 1
        
        # Second call with same args should use cache
        result2 = wrapped_func("value1", arg2="value2")
        assert result2["call_count"] == 1  # Still 1, not incremented
        
        # Different args should execute the function again
        result3 = wrapped_func("different", arg2="value2")
        assert result3["call_count"] == 2
        
        # Skip cache should execute the function again
        result4 = wrapped_func("value1", arg2="value2", skip_cache=True)
        assert result4["call_count"] == 3
    
    def test_get_cache_stats(self, temp_cache_manager):
        """Test getting cache statistics."""
        # Cache some data
        temp_cache_manager.cache_result({"data": 1}, None, "method1", "arg1")
        temp_cache_manager.cache_result({"data": 2}, None, "method2", "arg2")
        
        # Get and access data to record hits/misses
        temp_cache_manager.get_cached_result("method1", "arg1")
        temp_cache_manager.get_cached_result("nonexistent")
        
        # Get statistics
        stats = temp_cache_manager.get_cache_stats()
        
        assert "total_entries" in stats
        assert stats["total_entries"] >= 2 