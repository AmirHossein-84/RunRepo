"""Environment manager providing safe, non-destructive .env merging and timestamped backups."""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from runrepo.env.detector import EnvDetector
from runrepo.env.generator import EnvGenerator
from runrepo.env.models import EnvClassification, EnvFile, EnvRequirement


class EnvManager:
    """Safely manages .env files with automated backups and non-destructive merges."""

    @classmethod
    def backup_env_file(cls, env_path: Path) -> Path | None:
        """Create a timestamped backup of the existing .env file."""
        if not env_path.exists() or not env_path.is_file():
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = env_path.parent / f"{env_path.name}.backup.{timestamp}"
        shutil.copy2(env_path, backup_path)
        return backup_path

    @classmethod
    def is_placeholder_value(cls, val: str | None) -> bool:
        """Check if a string is empty or a common template dummy placeholder."""
        if val is None or not val.strip():
            return True
        v = val.strip().lower().strip("'\"")
        if not v:
            return True
        if v in (
            "changeme",
            "change_me",
            "replace_me",
            "replaceme",
            "your_key",
            "your_secret",
            "your_token",
            "xxx",
            "yyy",
            "zzz",
            "todo",
            "fixme",
            "dummy",
            "test",
            "test_secret",
            "secret",
            "password",
            "123456",
            "admin",
        ):
            return True
        if (v.startswith("<") and v.endswith(">")) or (v.startswith("your_") and v.endswith(("_here", "_secret", "_key", "_token"))):
            return True
        return False

    @classmethod
    def apply_env_updates(
        cls,
        root_path: Path,
        requirements: list[EnvRequirement],
        postgres_config: Any | None = None,
        redis_config: Any | None = None,
        include_external_stubs: bool = True,
    ) -> tuple[bool, str, list[str]]:
        """Safely merge new values and local defaults into .env without overwriting user data."""
        env_path = root_path / ".env"
        backup_created = None
        has_existing_env = env_path.exists()

        if has_existing_env:
            backup_created = cls.backup_env_file(env_path)
            env_file = EnvDetector.parse_env_file(env_path)
        else:
            # Check if an example file exists as base
            example_path = root_path / ".env.example"
            if not example_path.exists():
                example_path = root_path / ".env.template"

            if example_path.exists():
                env_file = EnvDetector.parse_env_file(example_path)
            else:
                env_file = EnvFile()

        added_keys: list[str] = []
        external_stubs_added: list[str] = []

        for req in requirements:
            existing_val = env_file.get_value(req.name)
            is_placeholder = cls.is_placeholder_value(existing_val)

            # Never overwrite existing non-empty user variables in an existing .env
            if has_existing_env and existing_val is not None and not is_placeholder:
                continue

            if req.classification == EnvClassification.EXTERNAL_SERVICE:
                if include_external_stubs and not env_file.has_key(req.name):
                    env_file.add_comment(f"{req.name}=your_{req.name.lower()}_here")
                    external_stubs_added.append(req.name)
                continue

            generated_val = EnvGenerator.generate_value(
                req,
                postgres_config=postgres_config,
                redis_config=redis_config,
            )

            if generated_val is not None:
                env_file.set_value(req.name, generated_val)
                added_keys.append(req.name)

        # Write to .env
        env_path.write_text(env_file.to_string(), encoding="utf-8")

        summary_parts = []
        if backup_created:
            summary_parts.append(f"Backup created at {backup_created.name}")
        if added_keys:
            summary_parts.append(f"configured {len(added_keys)} variable(s): {', '.join(added_keys)}")
        if external_stubs_added:
            summary_parts.append(f"added placeholder stubs for {len(external_stubs_added)} external key(s)")

        msg = "Successfully prepared .env (" + "; ".join(summary_parts) + ")" if summary_parts else "No .env changes needed."
        return True, msg, added_keys
