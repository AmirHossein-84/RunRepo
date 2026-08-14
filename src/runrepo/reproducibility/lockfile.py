"""Manager for deterministic, secret-free runrepo.lock file serialization and loading."""

import json
from pathlib import Path
from pydantic import ValidationError
from runrepo.reproducibility.models import RunRepoLock


class LockfileManager:
    """Handles deterministic generation, formatting, and reading of runrepo.lock files."""

    LOCKFILE_NAME = "runrepo.lock"
    SUPPORTED_LOCK_VERSIONS = {1}

    @classmethod
    def get_lockfile_path(cls, repo_path: Path | str) -> Path:
        """Return canonical path to runrepo.lock for a repository."""
        return Path(repo_path).resolve() / cls.LOCKFILE_NAME

    @classmethod
    def exists(cls, repo_path: Path | str) -> bool:
        """Check if runrepo.lock exists in repository."""
        return cls.get_lockfile_path(repo_path).is_file()

    @classmethod
    def load(cls, repo_path: Path | str) -> RunRepoLock | None:
        """Load and validate runrepo.lock if present."""
        path = cls.get_lockfile_path(repo_path)
        if not path.is_file():
            return None

        try:
            raw_text = path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
        except json.JSONDecodeError as err:
            raise ValueError(f"Corrupted or invalid JSON in '{cls.LOCKFILE_NAME}': {err}") from err
        except Exception as err:
            raise ValueError(f"Error reading '{cls.LOCKFILE_NAME}': {err}") from err

        if not isinstance(data, dict):
            raise ValueError(f"'{cls.LOCKFILE_NAME}' must contain a JSON object.")

        lock_version = data.get("lock_version")
        if lock_version not in cls.SUPPORTED_LOCK_VERSIONS:
            raise ValueError(
                f"Unsupported lockfile version '{lock_version}' in '{cls.LOCKFILE_NAME}'. "
                f"Supported versions: {cls.SUPPORTED_LOCK_VERSIONS}"
            )

        try:
            return RunRepoLock.model_validate(data)
        except ValidationError as err:
            raise ValueError(f"Schema validation error in '{cls.LOCKFILE_NAME}':\n{err}") from err

    @classmethod
    def format_json(cls, lock: RunRepoLock) -> str:
        """Serialize RunRepoLock to deterministic, sorted JSON with 2-space indentation."""
        data = lock.model_dump(mode="json")
        return json.dumps(data, indent=2, sort_keys=True) + "\n"

    @classmethod
    def save(cls, repo_path: Path | str, lock: RunRepoLock) -> Path:
        """Save RunRepoLock to disk deterministically."""
        target_path = cls.get_lockfile_path(repo_path)
        json_content = cls.format_json(lock)
        target_path.write_text(json_content, encoding="utf-8")
        return target_path
