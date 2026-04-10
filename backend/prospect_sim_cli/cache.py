"""
ICP file cache — maps SHA256(icp_file_content) → project_id.

Stored at ~/.miroshark/cache.json.
This is the core performance feature: build the ICP graph once,
reuse it for all subsequent variant runs.

Rule 6 (idempotency): same ICP file → same project_id, no duplicate builds.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CACHE_DIR = Path.home() / ".miroshark"
CACHE_FILE = CACHE_DIR / "cache.json"
CONFIG_FILE = CACHE_DIR / "config.json"

# Default CLI config values
DEFAULT_CONFIG = {
    "api_url": "http://localhost:5001",
    "default_rounds": 8,
    "default_parallel": False,
}


class IcpCache:
    """
    Manages the local ICP graph cache.

    Format of cache.json:
    {
      "<sha256_hex>": {
        "project_id": "proj_abc123",
        "icp_file": "/absolute/path/to/icp.md",
        "created_at": "2026-04-08T21:00:00Z"
      }
    }
    """

    def __init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        """Load cache from disk. Returns empty dict if file missing."""
        if not CACHE_FILE.exists():
            return {}
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict) -> None:
        """Persist cache to disk atomically."""
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE_FILE)

    def hash_file(self, path: Path) -> str:
        """Return SHA256 hex digest of file contents."""
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()

    def get(self, file_hash: str) -> Optional[dict]:
        """
        Look up a cached project by ICP file hash.
        Returns the cache entry dict or None on miss.
        """
        return self._load().get(file_hash)

    def set(self, file_hash: str, project_id: str, icp_file: str) -> None:
        """Store a new cache entry."""
        data = self._load()
        data[file_hash] = {
            "project_id": project_id,
            "icp_file": icp_file,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)

    def delete(self, file_hash: str) -> None:
        """Remove a cache entry (e.g., when backend project no longer exists)."""
        data = self._load()
        data.pop(file_hash, None)
        self._save(data)

    def list_all(self) -> list[dict]:
        """Return all cache entries as a flat list for `project list`."""
        data = self._load()
        return [
            {"hash": h, **entry}
            for h, entry in data.items()
        ]

    def clear(self) -> None:
        """Remove all cache entries."""
        self._save({})


class CliConfig:
    """
    Manages ~/.prospect-sim/config.json.
    Stores API URL and default run parameters.
    """

    def __init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not CONFIG_FILE.exists():
            return dict(DEFAULT_CONFIG)
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            # Merge with defaults so new keys are always present
            return {**DEFAULT_CONFIG, **data}
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_CONFIG)

    def _save(self, data: dict) -> None:
        tmp = CONFIG_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CONFIG_FILE)

    def get(self, key: str):
        return self._load().get(key)

    def set(self, key: str, value) -> None:
        data = self._load()
        data[key] = value
        self._save(data)

    def all(self) -> dict:
        return self._load()
