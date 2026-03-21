"""SQLite-based API response cache for GIAE.

Caches API responses (UniProt, InterPro) keyed by sequence hash
to avoid redundant network calls. Uses only Python stdlib.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".giae"
DEFAULT_CACHE_FILE = DEFAULT_CACHE_DIR / "cache.db"
DEFAULT_TTL_SECONDS = 30 * 86400  # 30 days


@dataclass
class DiskCache:
    """
    SQLite-backed cache for API responses.

    Stores JSON-serializable data in a local database, keyed by a hash
    of the input (typically a protein sequence).

    Attributes:
        cache_file: Path to the SQLite database file.
        ttl_seconds: Time-to-live in seconds (default 30 days).
        enabled: Whether caching is active.
    """

    cache_file: Path = field(default_factory=lambda: DEFAULT_CACHE_FILE)
    ttl_seconds: int = DEFAULT_TTL_SECONDS
    enabled: bool = True

    def __post_init__(self) -> None:
        """Initialize the database schema."""
        if self.enabled:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS api_cache (
                        key TEXT PRIMARY KEY,
                        namespace TEXT,
                        data TEXT,
                        timestamp REAL
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_namespace ON api_cache(namespace)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON api_cache(timestamp)")

    def _connect(self) -> sqlite3.Connection:
        """Create a new SQLite connection."""
        return sqlite3.connect(self.cache_file, timeout=10.0)

    @staticmethod
    def hash_key(value: str) -> str:
        """Create a SHA-256 hash of the input string."""
        return hashlib.sha256(value.strip().upper().encode("utf-8")).hexdigest()

    def get(self, namespace: str, key: str) -> Any | None:
        """
        Read a cached value if it exists and hasn't expired.

        Args:
            namespace: Cache partition (e.g. "uniprot", "interpro").
            key: Raw key string (will be hashed).

        Returns:
            The cached data, or None if missing/expired.
        """
        if not self.enabled:
            return None

        key_hash = self.hash_key(key)
        
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "SELECT data, timestamp FROM api_cache WHERE key = ? AND namespace = ?",
                    (key_hash, namespace),
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                data_str, timestamp = row
                
                # Check expiration
                if time.time() - timestamp > self.ttl_seconds:
                    conn.execute("DELETE FROM api_cache WHERE key = ?", (key_hash,))
                    return None
                
                return json.loads(data_str)
                
        except (sqlite3.Error, json.JSONDecodeError) as e:
            key_preview = str(key_hash)
            logger.debug("Cache read failed for %s: %s", key_preview[:8], e)
            return None

    def put(self, namespace: str, key: str, data: Any) -> None:
        """
        Write a value to the cache.

        Args:
            namespace: Cache partition.
            key: Raw key string (will be hashed).
            data: JSON-serializable data to cache.
        """
        if not self.enabled:
            return

        key_hash = self.hash_key(key)
        
        try:
            data_str = json.dumps(data)
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO api_cache (key, namespace, data, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key_hash, namespace, data_str, time.time()),
                )
        except (sqlite3.Error, TypeError) as e:
            key_preview = str(key_hash)
            logger.debug("Cache write failed for %s: %s", key_preview[:8], e)

    def clear(self, namespace: str | None = None) -> int:
        """
        Remove cache entries.

        Args:
            namespace: If given, only clear that namespace. Otherwise clear all.

        Returns:
            Number of entries removed.
        """
        try:
            with self._connect() as conn:
                if namespace:
                    cursor = conn.execute("DELETE FROM api_cache WHERE namespace = ?", (namespace,))
                else:
                    cursor = conn.execute("DELETE FROM api_cache")
                return cursor.rowcount
        except sqlite3.Error:
            return 0

    def stats(self) -> dict[str, int]:
        """Return entry counts per namespace."""
        result: dict[str, int] = {}
        if not self.cache_file.exists():
            return result

        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "SELECT namespace, COUNT(*) FROM api_cache GROUP BY namespace"
                )
                for ns, count in cursor.fetchall():
                    result[ns] = count
        except sqlite3.Error:
            pass
            
        return result
