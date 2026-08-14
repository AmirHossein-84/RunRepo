"""Loader and validator for user-editable runrepo.yaml configuration files."""

from pathlib import Path
from typing import Any
import yaml
from pydantic import ValidationError
from runrepo.reproducibility.models import RunRepoConfig


class ConfigLoader:
    """Discovers, parses, and validates repository configuration from runrepo.yaml."""

    CONFIG_FILENAMES = ("runrepo.yaml", "runrepo.yml")

    @classmethod
    def find_config_file(cls, repo_path: Path | str) -> Path | None:
        """Find runrepo.yaml or runrepo.yml in repository root."""
        root = Path(repo_path).resolve()
        for name in cls.CONFIG_FILENAMES:
            candidate = root / name
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    @classmethod
    def load(cls, repo_path: Path | str) -> RunRepoConfig | None:
        """Load and validate runrepo.yaml configuration if present."""
        config_path = cls.find_config_file(repo_path)
        if config_path is None:
            return None

        try:
            content = config_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
        except yaml.YAMLError as err:
            raise ValueError(f"Invalid YAML in '{config_path.name}': {err}") from err
        except Exception as err:
            raise ValueError(f"Error reading '{config_path.name}': {err}") from err

        if data is None:
            return RunRepoConfig()

        if not isinstance(data, dict):
            raise ValueError(f"Configuration in '{config_path.name}' must be a mapping/dictionary object.")

        try:
            return RunRepoConfig.model_validate(data)
        except ValidationError as err:
            raise ValueError(f"Configuration schema error in '{config_path.name}':\n{err}") from err
