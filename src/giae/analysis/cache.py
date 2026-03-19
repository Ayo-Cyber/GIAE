"""Disk-based API response cache for GIAE.

Caches API responses (UniProt, InterPro) keyed by sequence hash
to avoid redundant network calls. Uses only Python stdlib.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".giae" / "cache"
DEFAULT_TTL_SECONDS = 7 * 86400  # 7 days


@dataclass
class DiskCache:
    """
    Thread-safe, file-based cache for API responses.

    Stores JSON-serializable data on disk, keyed by a hash of the
    input (typically a protein sequence). Entries expire after a
    configurable TTL.

    Attributes:
        cache_dir: Root directory for cache files.
        ttl_seconds: Time-to-live in seconds (default 7 days).
        enabled: Whether caching is active.
    """

    cache_dir: Path = field(default_factory=lambda: DEFAULT_CACHE_DIR)
    ttl_seconds: int = DEFAULT_TTL_SECONDS
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def hash_key(value: str) -> str:
        """Create a SHA-256 hash of the input string."""
        return hashlib.sha256(value.strip().upper().encode("utf-8")).hexdigest()

    def _entry_path(self, namespace: str, key_hash: str) -> Path:
        """Build the file path for a cache entry: cache_dir/namespace/ab/abcdef....json"""
        prefix = key_hash[:2]
        return self.cache_dir / namespace / prefix / f"{key_hash}.json"

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
        path = self._entry_path(namespace, key_hash)

        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
            entry = json.loads(raw)
            timestamp = entry.get("timestamp", 0)

            if time.time() - timestamp > self.ttl_seconds:
                # Expired — remove silently
                path.unlink(missing_ok=True)
                logger.debug("Cache expired for %s/%s", namespace, key_hash[:8])
                return None

            logger.debug("Cache hit for %s/%s", namespace, key_hash[:8])
            return entry.get("data")

        except (json.JSONDecodeError, OSError, KeyError):
            # Corrupt entry — remove and return miss
            path.unlink(missing_ok=True)
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
        path = self._entry_path(namespace, key_hash)
        path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": time.time(),
            "data": data,
        }

        try:
            tmp_path = path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(entry), encoding="utf-8")
            tmp_path.replace(path)  # Atomic on POSIX
        except OSError as e:
            logger.debug("Cache write failed: %s", e)

    def clear(self, namespace: str | None = None) -> int:
        """
        Remove cache entries.

        Args:
            namespace: If given, only clear that namespace. Otherwise clear all.

        Returns:
            Number of entries removed.
        """
        count = 0
        if namespace:
            target = self.cache_dir / namespace
        else:
            target = self.cache_dir

        if not target.exists():
            return 0

        for json_file in target.rglob("*.json"):
            try:
                json_file.unlink()
                count += 1
            except OSError:
                pass

        # Clean up empty directories
        for dirpath in sorted(target.rglob("*"), reverse=True):
            if dirpath.is_dir():
                try:
                    dirpath.rmdir()
                except OSError:
                    pass  # Not empty

        return count

    def stats(self) -> dict[str, int]:
        """Return entry counts per namespace."""
        result: dict[str, int] = {}
        if not self.cache_dir.exists():
            return result

        for ns_dir in self.cache_dir.iterdir():
            if ns_dir.is_dir():
                count = sum(1 for _ in ns_dir.rglob("*.json"))
                if count:
                    result[ns_dir.name] = count
        return result
