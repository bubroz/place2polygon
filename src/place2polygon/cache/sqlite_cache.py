"""
SQLite-based cache implementation for Nominatim query results.

This module provides a persistent cache using SQLite for storing
Nominatim query results, including polygon geometries.
"""

import json
import os
import sqlite3
import time
from typing import Dict, List, Optional, Any, Union, Tuple
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SQLiteCache:
    """
    SQLite-based cache for Nominatim query results.
    
    Args:
        db_path: Path to the SQLite database file.
        default_ttl: Default time-to-live in days.
    """
    
    def __init__(self, db_path: str = "polygon_cache.db", default_ttl: int = 30):
        """Initialize the SQLite cache."""
        self.db_path = db_path
        self.default_ttl = default_ttl
        self._initialize_db()
    
    def _initialize_db(self) -> None:
        """Initialize the database tables if they don't exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nominatim_cache (
                    query_key TEXT PRIMARY KEY,
                    result TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed_at INTEGER
                )
            """)
            
            # Create statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_stats (
                    stat_key TEXT PRIMARY KEY,
                    stat_value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            
            # Create index on expires_at for faster cleanup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at ON nominatim_cache(expires_at)
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"Initialized cache database at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error initializing cache database: {str(e)}")
            raise
    
    def get(self, query_key: str) -> Optional[Any]:
        """
        Get a result from the cache.
        
        Args:
            query_key: The cache key to look up.
            
        Returns:
            The cached result, or None if not found or expired.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get the cached result
            cursor.execute("""
                SELECT result, expires_at FROM nominatim_cache
                WHERE query_key = ? AND expires_at > ?
            """, (query_key, int(time.time())))
            
            row = cursor.fetchone()
            
            if row:
                result_json, expires_at = row
                
                # Update access statistics
                cursor.execute("""
                    UPDATE nominatim_cache
                    SET access_count = access_count + 1,
                        last_accessed_at = ?
                    WHERE query_key = ?
                """, (int(time.time()), query_key))
                
                conn.commit()
                conn.close()
                
                # Parse and return the result
                try:
                    return json.loads(result_json)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in cache for key: {query_key}")
                    return None
            else:
                conn.close()
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving from cache: {str(e)}")
            return None
    
    def set(self, query_key: str, result: Any, ttl: Optional[int] = None) -> bool:
        """
        Store a result in the cache.
        
        Args:
            query_key: The cache key to store under.
            result: The result to cache.
            ttl: Time-to-live in days, or None to use the default.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            ttl_days = ttl if ttl is not None else self.default_ttl
            now = int(time.time())
            expires_at = now + (ttl_days * 86400)  # Convert days to seconds
            
            # Serialize the result to JSON
            try:
                result_json = json.dumps(result)
            except (TypeError, ValueError) as e:
                logger.error(f"Error serializing result to JSON: {str(e)}")
                return False
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Store the result
            cursor.execute("""
                INSERT OR REPLACE INTO nominatim_cache
                (query_key, result, created_at, expires_at, access_count, last_accessed_at)
                VALUES (?, ?, ?, ?, 0, NULL)
            """, (query_key, result_json, now, expires_at))
            
            conn.commit()
            conn.close()
            
            # Update statistics asynchronously
            self._update_stats_async()
            
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error storing in cache: {str(e)}")
            return False
    
    def invalidate(self, query_key: str) -> bool:
        """
        Invalidate a cached result.
        
        Args:
            query_key: The cache key to invalidate.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM nominatim_cache WHERE query_key = ?", (query_key,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
            
            if deleted:
                logger.debug(f"Invalidated cache entry: {query_key}")
            
            return deleted
            
        except sqlite3.Error as e:
            logger.error(f"Error invalidating cache: {str(e)}")
            return False
    
    def clear_expired(self) -> int:
        """
        Clear expired cache entries.
        
        Returns:
            Number of entries cleared.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM nominatim_cache WHERE expires_at <= ?", (int(time.time()),))
            cleared = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if cleared > 0:
                logger.info(f"Cleared {cleared} expired cache entries")
                self._update_stats_async()
            
            return cleared
            
        except sqlite3.Error as e:
            logger.error(f"Error clearing expired cache: {str(e)}")
            return 0
    
    def clear_all(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM nominatim_cache")
            
            conn.commit()
            conn.close()
            
            logger.info("Cleared all cache entries")
            self._update_stats_async()
            
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary of cache statistics.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get statistics
            stats = {}
            
            # Total entries
            cursor.execute("SELECT COUNT(*) FROM nominatim_cache")
            stats['total_entries'] = cursor.fetchone()[0]
            
            # Total size
            cursor.execute("SELECT SUM(LENGTH(result)) FROM nominatim_cache")
            size_bytes = cursor.fetchone()[0] or 0
            stats['total_size_bytes'] = size_bytes
            stats['total_size_mb'] = round(size_bytes / (1024 * 1024), 2)
            
            # Expired entries
            cursor.execute("SELECT COUNT(*) FROM nominatim_cache WHERE expires_at <= ?", (int(time.time()),))
            stats['expired_entries'] = cursor.fetchone()[0]
            
            # Hit rate (from stored stats)
            cursor.execute("SELECT stat_value FROM cache_stats WHERE stat_key = 'hit_rate'")
            row = cursor.fetchone()
            stats['hit_rate'] = float(row[0]) if row else 0.0
            
            # Hit count and miss count
            cursor.execute("SELECT stat_value FROM cache_stats WHERE stat_key = 'hit_count'")
            row = cursor.fetchone()
            stats['hit_count'] = int(row[0]) if row else 0
            
            cursor.execute("SELECT stat_value FROM cache_stats WHERE stat_key = 'miss_count'")
            row = cursor.fetchone()
            stats['miss_count'] = int(row[0]) if row else 0
            
            # Most accessed entries
            cursor.execute("""
                SELECT query_key, access_count FROM nominatim_cache
                ORDER BY access_count DESC LIMIT 5
            """)
            stats['most_accessed'] = [{'key': row[0], 'access_count': row[1]} for row in cursor.fetchall()]
            
            # Recently added
            cursor.execute("""
                SELECT query_key, created_at FROM nominatim_cache
                ORDER BY created_at DESC LIMIT 5
            """)
            stats['recently_added'] = [
                {'key': row[0], 'added_at': datetime.fromtimestamp(row[1]).isoformat()}
                for row in cursor.fetchall()
            ]
            
            conn.close()
            
            return stats
            
        except sqlite3.Error as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {'error': str(e)}
    
    def _update_stats_async(self) -> None:
        """Update cache statistics in the background."""
        # In a real implementation, this would be done asynchronously.
        # For simplicity, we'll do it synchronously.
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = int(time.time())
            
            # Get current hit count and miss count
            cursor.execute("SELECT stat_value FROM cache_stats WHERE stat_key = 'hit_count'")
            row = cursor.fetchone()
            hit_count = int(row[0]) if row else 0
            
            cursor.execute("SELECT stat_value FROM cache_stats WHERE stat_key = 'miss_count'")
            row = cursor.fetchone()
            miss_count = int(row[0]) if row else 0
            
            # Calculate hit rate
            total_requests = hit_count + miss_count
            hit_rate = hit_count / total_requests if total_requests > 0 else 0.0
            
            # Update statistics
            cursor.execute("""
                INSERT OR REPLACE INTO cache_stats (stat_key, stat_value, updated_at)
                VALUES ('hit_rate', ?, ?)
            """, (str(hit_rate), now))
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            logger.error(f"Error updating cache stats: {str(e)}")
    
    def record_hit(self) -> None:
        """Record a cache hit."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get current hit count
            cursor.execute("SELECT stat_value FROM cache_stats WHERE stat_key = 'hit_count'")
            row = cursor.fetchone()
            hit_count = int(row[0]) if row else 0
            
            # Increment hit count
            hit_count += 1
            
            # Update hit count
            cursor.execute("""
                INSERT OR REPLACE INTO cache_stats (stat_key, stat_value, updated_at)
                VALUES ('hit_count', ?, ?)
            """, (str(hit_count), int(time.time())))
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            logger.error(f"Error recording cache hit: {str(e)}")
    
    def record_miss(self) -> None:
        """Record a cache miss."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get current miss count
            cursor.execute("SELECT stat_value FROM cache_stats WHERE stat_key = 'miss_count'")
            row = cursor.fetchone()
            miss_count = int(row[0]) if row else 0
            
            # Increment miss count
            miss_count += 1
            
            # Update miss count
            cursor.execute("""
                INSERT OR REPLACE INTO cache_stats (stat_key, stat_value, updated_at)
                VALUES ('miss_count', ?, ?)
            """, (str(miss_count), int(time.time())))
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            logger.error(f"Error recording cache miss: {str(e)}")

# Create a default instance
default_cache = SQLiteCache()
