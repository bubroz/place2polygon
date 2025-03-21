"""
Cache manager module for storing and retrieving Nominatim API responses.

This module provides a cache manager class that uses SQLite to store API responses.
"""

import os
import sqlite3
import logging
import json
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

from place2polygon.utils import default_output_manager

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = 'place2polygon_cache.db'
DEFAULT_TTL_DAYS = 30  # 30 days default TTL

class CacheManager:
    """
    Cache manager for storing and retrieving Nominatim API responses.
    
    Uses SQLite to store responses and provides methods for managing the cache.
    """
    
    def __init__(self, db_path: Optional[str] = None, ttl_days: int = DEFAULT_TTL_DAYS):
        """
        Initialize the cache manager.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses place2polygon_output/cache directory.
            ttl_days: Default time-to-live in days for cached items.
        """
        # Use the output manager to get the cache directory
        if db_path is None:
            cache_dir = default_output_manager.get_cache_dir()
            db_path = str(cache_dir / DEFAULT_DB_PATH)
        
        self.db_path = db_path
        self.ttl_days = ttl_days
        self.conn = None
        
        # Initialize the database
        self._init_db()
        
        logger.info(f"Cache initialized at {self.db_path}")
    
    def _init_db(self) -> None:
        """Initialize the SQLite database if it doesn't exist."""
        # Create directory if it doesn't exist
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        # Connect to the database
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # Create the cache table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created REAL NOT NULL,
                expires REAL NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                name TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
        ''')
        
        # Initialize stats if they don't exist
        stats = ['hits', 'misses', 'size']
        for stat in stats:
            cursor.execute('INSERT OR IGNORE INTO stats (name, value) VALUES (?, 0)', (stat,))
        
        self.conn.commit()
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get an item from the cache by key.
        
        Args:
            key: The cache key.
            
        Returns:
            The cached item, or None if not found or expired.
        """
        if not self.conn:
            self._init_db()
        
        cursor = self.conn.cursor()
        
        # Get item from cache
        cursor.execute('SELECT value, expires FROM cache WHERE key = ?', (key,))
        result = cursor.fetchone()
        
        if result:
            value, expires = result
            
            # Check if expired
            if expires < time.time():
                # Remove expired item
                cursor.execute('DELETE FROM cache WHERE key = ?', (key,))
                self.conn.commit()
                
                # Update stats
                self._increment_stat('misses')
                self._decrement_stat('size')
                
                return None
            
            # Update stats
            self._increment_stat('hits')
            
            # Return the cached item
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode cached item: {key}")
                return None
        else:
            # Update stats
            self._increment_stat('misses')
            
            return None
    
    def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Set an item in the cache.
        
        Args:
            key: The cache key.
            value: The value to cache.
            ttl: Time-to-live in days. If None, uses the default TTL.
        """
        if not self.conn:
            self._init_db()
        
        cursor = self.conn.cursor()
        
        # Use default TTL if not specified
        if ttl is None:
            ttl = self.ttl_days
        
        # Calculate expiration time
        created = time.time()
        expires = created + (ttl * 24 * 60 * 60)  # Convert days to seconds
        
        # Serialize value to JSON
        try:
            json_value = json.dumps(value)
        except (TypeError, ValueError):
            logger.warning(f"Failed to encode value for cache key: {key}")
            return
        
        # Check if item already exists
        cursor.execute('SELECT 1 FROM cache WHERE key = ?', (key,))
        exists = cursor.fetchone() is not None
        
        # Update or insert item
        if exists:
            cursor.execute('UPDATE cache SET value = ?, created = ?, expires = ? WHERE key = ?',
                          (json_value, created, expires, key))
        else:
            cursor.execute('INSERT INTO cache (key, value, created, expires) VALUES (?, ?, ?, ?)',
                          (key, json_value, created, expires))
            self._increment_stat('size')
        
        self.conn.commit()
    
    def delete(self, key: str) -> bool:
        """
        Delete an item from the cache.
        
        Args:
            key: The cache key.
            
        Returns:
            True if the item was deleted, False otherwise.
        """
        if not self.conn:
            self._init_db()
        
        cursor = self.conn.cursor()
        
        # Delete item
        cursor.execute('DELETE FROM cache WHERE key = ?', (key,))
        deleted = cursor.rowcount > 0
        
        if deleted:
            self._decrement_stat('size')
        
        self.conn.commit()
        
        return deleted
    
    def clear(self) -> None:
        """Clear all items from the cache."""
        if not self.conn:
            self._init_db()
        
        cursor = self.conn.cursor()
        
        # Clear cache
        cursor.execute('DELETE FROM cache')
        
        # Reset stats
        cursor.execute('UPDATE stats SET value = 0')
        
        self.conn.commit()
    
    def clean_expired(self) -> int:
        """
        Remove all expired items from the cache.
        
        Returns:
            Number of items removed.
        """
        if not self.conn:
            self._init_db()
        
        cursor = self.conn.cursor()
        
        # Delete expired items
        cursor.execute('DELETE FROM cache WHERE expires < ?', (time.time(),))
        deleted_count = cursor.rowcount
        
        if deleted_count > 0:
            # Update size stat
            cursor.execute('UPDATE stats SET value = value - ? WHERE name = ?',
                          (deleted_count, 'size'))
        
        self.conn.commit()
        
        return deleted_count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics.
        """
        if not self.conn:
            self._init_db()
        
        cursor = self.conn.cursor()
        
        # Get all stats
        cursor.execute('SELECT name, value FROM stats')
        stats = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Calculate hit rate
        total_requests = stats.get('hits', 0) + stats.get('misses', 0)
        hit_rate = stats.get('hits', 0) / max(total_requests, 1)
        
        return {
            'hits': stats.get('hits', 0),
            'misses': stats.get('misses', 0),
            'hit_rate': hit_rate,
            'size': stats.get('size', 0),
            'db_path': self.db_path
        }
    
    def _increment_stat(self, name: str, amount: int = 1) -> None:
        """Increment a stat by the given amount."""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE stats SET value = value + ? WHERE name = ?',
                      (amount, name))
    
    def _decrement_stat(self, name: str, amount: int = 1) -> None:
        """Decrement a stat by the given amount."""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE stats SET value = value - ? WHERE name = ?',
                      (amount, name))
    
    def get_keys(self, pattern: Optional[str] = None) -> List[str]:
        """
        Get all cache keys matching the pattern.
        
        Args:
            pattern: SQL LIKE pattern to match keys.
            
        Returns:
            List of matching cache keys.
        """
        if not self.conn:
            self._init_db()
        
        cursor = self.conn.cursor()
        
        # Query keys
        if pattern:
            cursor.execute('SELECT key FROM cache WHERE key LIKE ?', (pattern,))
        else:
            cursor.execute('SELECT key FROM cache')
        
        return [row[0] for row in cursor.fetchall()]
    
    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __del__(self) -> None:
        """Clean up on object destruction."""
        self.close()

# Create default cache manager instance
default_manager = CacheManager()
