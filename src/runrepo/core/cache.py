"""High-performance in-memory and mtime-based filesystem scan caching."""

import json
from pathlib import Path
from typing import Any
import tomllib


class ScanCache:
    """Memoizes filesystem parsing and traversal by tracking file modification timestamps."""

    def __init__(self) -> None:
        self._json_cache: dict[str, tuple[float, Any]] = {}
        self._toml_cache: dict[str, tuple[float, Any]] = {}
        self._file_exists_cache: dict[str, tuple[float, bool]] = {}

    def read_json(self, file_path: Path | str) -> Any | None:
        """Read and parse a JSON file with mtime-based caching."""
        p = Path(file_path).resolve()
        if not p.is_file():
            return None

        try:
            mtime = p.stat().st_mtime
            key = str(p)
            if key in self._json_cache:
                cached_mtime, cached_data = self._json_cache[key]
                if cached_mtime == mtime:
                    return cached_data

            data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            self._json_cache[key] = (mtime, data)
            return data
        except Exception:
            return None

    def read_toml(self, file_path: Path | str) -> Any | None:
        """Read and parse a TOML file with mtime-based caching."""
        p = Path(file_path).resolve()
        if not p.is_file():
            return None

        try:
            mtime = p.stat().st_mtime
            key = str(p)
            if key in self._toml_cache:
                cached_mtime, cached_data = self._toml_cache[key]
                if cached_mtime == mtime:
                    return cached_data

            with open(p, "rb") as f:
                data = tomllib.load(f)
            self._toml_cache[key] = (mtime, data)
            return data
        except Exception:
            return None

    def clear(self) -> None:
        """Clear all cached entries."""
        self._json_cache.clear()
        self._toml_cache.clear()
        self._file_exists_cache.clear()
