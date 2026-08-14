"""Filesystem scan context with safe parsing and path normalization."""

import json
from pathlib import Path
import tomllib
from typing import Any
import yaml

from runrepo.models.project import AnalysisWarning

# Standard directories to ignore during repository scanning
IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        ".env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        ".nuxt",
        ".turbo",
        ".output",
        "target",
        "bin",
        "obj",
        ".idea",
        ".vscode",
    }
)


class ScanContext:
    """Encapsulates repository filesystem exploration, caching, and safe file parsing.

    Ensures all relative paths use forward slashes for deterministic cross-platform
    consistency (Windows 11 / Linux).
    """

    def __init__(self, root_path: Path | str, max_depth: int = 3) -> None:
        self.root_path = Path(root_path).resolve()
        self.max_depth = max_depth
        self._warnings: list[AnalysisWarning] = []
        self._file_cache: set[str] = set()
        self._dir_cache: set[str] = set()
        self._text_cache: dict[str, str] = {}
        self._json_cache: dict[str, Any] = {}
        self._toml_cache: dict[str, dict[str, Any]] = {}
        self._yaml_cache: dict[str, Any] = {}

        self._index_filesystem()

    def _normalize_rel_path(self, path: Path) -> str:
        """Convert a path relative to root_path to a forward-slash normalized string."""
        rel = path.relative_to(self.root_path)
        return rel.as_posix()

    def _index_filesystem(self) -> None:
        """Index directory structure up to max_depth while skipping ignored directories."""
        if not self.root_path.exists() or not self.root_path.is_dir():
            return

        def _scan(current_dir: Path, current_depth: int) -> None:
            if current_depth > self.max_depth:
                return

            try:
                for entry in current_dir.iterdir():
                    if entry.is_dir():
                        if entry.name in IGNORED_DIRS:
                            continue
                        rel_dir = self._normalize_rel_path(entry)
                        self._dir_cache.add(rel_dir)
                        _scan(entry, current_depth + 1)
                    elif entry.is_file():
                        rel_file = self._normalize_rel_path(entry)
                        self._file_cache.add(rel_file)
            except (PermissionError, OSError) as err:
                rel_err_path = (
                    self._normalize_rel_path(current_dir)
                    if current_dir != self.root_path
                    else "."
                )
                self.add_warning(
                    file_path=rel_err_path,
                    message=f"Could not read directory: {err}",
                    code="DIR_ACCESS_ERROR",
                )

        _scan(self.root_path, 0)

    @property
    def warnings(self) -> list[AnalysisWarning]:
        """Return all non-fatal warnings captured during file operations."""
        return list(self._warnings)

    def add_warning(self, file_path: str, message: str, code: str = "PARSE_ERROR") -> None:
        """Record an analysis warning."""
        self._warnings.append(AnalysisWarning(file_path=file_path, message=message, code=code))

    def has_file(self, rel_path: str) -> bool:
        """Check if a file exists relative to repository root."""
        normalized = rel_path.replace("\\", "/").strip("/")
        return normalized in self._file_cache

    def has_dir(self, rel_path: str) -> bool:
        """Check if a directory exists relative to repository root."""
        normalized = rel_path.replace("\\", "/").strip("/")
        return normalized in self._dir_cache

    def get_all_files(self) -> list[str]:
        """Return all discovered files in repository (normalized forward slash paths)."""
        return sorted(self._file_cache)

    def get_all_dirs(self) -> list[str]:
        """Return all discovered directories in repository."""
        return sorted(self._dir_cache)

    def find_files_by_name(self, filename: str) -> list[str]:
        """Find all files matching exact filename across repo, e.g. 'package.json'."""
        matches = [
            f
            for f in self._file_cache
            if f == filename or f.endswith(f"/{filename}")
        ]
        # Sort root matches first, then by path
        return sorted(matches, key=lambda x: (x.count("/"), x))

    def read_text(self, rel_path: str) -> str | None:
        """Safely read text content of a file with UTF-8 encoding."""
        normalized = rel_path.replace("\\", "/").strip("/")
        if normalized in self._text_cache:
            return self._text_cache[normalized]

        file_full_path = self.root_path / normalized
        if not file_full_path.is_file():
            return None

        try:
            content = file_full_path.read_text(encoding="utf-8", errors="replace")
            self._text_cache[normalized] = content
            return content
        except Exception as err:
            self.add_warning(
                file_path=normalized,
                message=f"Failed to read file: {err}",
                code="FILE_READ_ERROR",
            )
            return None

    def read_json(self, rel_path: str) -> Any | None:
        """Safely read and parse a JSON file. Returns None on parse error and logs warning."""
        normalized = rel_path.replace("\\", "/").strip("/")
        if normalized in self._json_cache:
            return self._json_cache[normalized]

        text = self.read_text(normalized)
        if text is None:
            return None

        try:
            data = json.loads(text)
            self._json_cache[normalized] = data
            return data
        except json.JSONDecodeError as err:
            self.add_warning(
                file_path=normalized,
                message=f"Malformed JSON in {normalized}: {err}",
                code="JSON_DECODE_ERROR",
            )
            return None

    def read_toml(self, rel_path: str) -> dict[str, Any] | None:
        """Safely read and parse a TOML file. Returns None on parse error and logs warning."""
        normalized = rel_path.replace("\\", "/").strip("/")
        if normalized in self._toml_cache:
            return self._toml_cache[normalized]

        text = self.read_text(normalized)
        if text is None:
            return None

        try:
            data = tomllib.loads(text)
            self._toml_cache[normalized] = data
            return data
        except tomllib.TOMLDecodeError as err:
            self.add_warning(
                file_path=normalized,
                message=f"Malformed TOML in {normalized}: {err}",
                code="TOML_DECODE_ERROR",
            )
            return None

    def read_yaml(self, rel_path: str) -> Any | None:
        """Safely read and parse a YAML file. Returns None on parse error and logs warning."""
        normalized = rel_path.replace("\\", "/").strip("/")
        if normalized in self._yaml_cache:
            return self._yaml_cache[normalized]

        text = self.read_text(normalized)
        if text is None:
            return None

        try:
            data = yaml.safe_load(text)
            self._yaml_cache[normalized] = data
            return data
        except yaml.YAMLError as err:
            self.add_warning(
                file_path=normalized,
                message=f"Malformed YAML in {normalized}: {err}",
                code="YAML_DECODE_ERROR",
            )
            return None
