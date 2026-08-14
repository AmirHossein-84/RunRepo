"""Deterministic environment variable detector and .env parser supporting edge cases."""

import re
from pathlib import Path
import yaml
from runrepo.env.classifier import EnvClassifier
from runrepo.env.models import EnvClassification, EnvEntry, EnvEntryType, EnvFile, EnvRequirement
from runrepo.env.redactor import is_sensitive_key

ENV_FILENAMES = [
    ".env",
    ".env.local",
    ".env.development",
    ".env.example",
    ".env.template",
    ".env.sample",
    ".env.dist",
]

# Regex for stripping unescaped inline comments (e.g. `KEY=val # note`)
_INLINE_COMMENT_REGEX = re.compile(r"\s+#.*$")

# Source scanning regex patterns
_NODE_PROCESS_ENV_REGEX = re.compile(r"process\.env(?:\.([A-Za-z0-9_]+)|\[['\"]([A-Za-z0-9_]+)['\"]\])")
_PYTHON_OS_ENV_REGEX = re.compile(
    r"os\.(?:getenv|environ\.get)\(['\"]([A-Za-z0-9_]+)['\"](?:\s*,\s*['\"]([^'\"]*)['\"])?\)|os\.environ\[['\"]([A-Za-z0-9_]+)['\"]\]"
)


class EnvDetector:
    """Detects environment variable requirements across .env files, Compose, and code entrypoints."""

    @classmethod
    def parse_env_file(cls, path: Path) -> EnvFile:
        """Parse a .env or .env.example file into structured EnvEntries preserving comments."""
        if not path.exists() or not path.is_file():
            return EnvFile()

        content = path.read_text(encoding="utf-8", errors="replace")
        return cls.parse_env_content(content)

    @classmethod
    def parse_env_content(cls, content: str) -> EnvFile:
        """Parse raw .env content supporting quotes, spaces, inline comments, escapes, and multiline values."""
        entries: list[EnvEntry] = []
        lines = content.splitlines()

        i = 0
        n = len(lines)

        while i < n:
            raw_line = lines[i]
            stripped = raw_line.strip()

            # 1. Blank line
            if not stripped:
                entries.append(EnvEntry(entry_type=EnvEntryType.BLANK, raw_line=raw_line))
                i += 1
                continue

            # 2. Pure Comment
            if stripped.startswith("#"):
                comment_text = stripped[1:].strip()
                entries.append(
                    EnvEntry(
                        entry_type=EnvEntryType.COMMENT,
                        raw_line=raw_line,
                        comment=comment_text,
                    )
                )
                i += 1
                continue

            # 3. Key=Value line
            if "=" in raw_line:
                # Handle `export KEY=VALUE`
                line_to_parse = raw_line
                if line_to_parse.strip().startswith("export "):
                    line_to_parse = line_to_parse.strip()[7:]

                key, _, raw_val = line_to_parse.partition("=")
                key = key.strip()

                # Parse value, handling multiline quotes if open quote without close
                val_str = raw_val.strip()
                comment_part = None

                # Check if value starts with a quote
                if val_str.startswith(('"', "'")):
                    quote_char = val_str[0]
                    # Check if matching quote is on the same line
                    # Note: we need to handle escaped quotes inside
                    if len(val_str) > 1 and val_str.endswith(quote_char) and not val_str.endswith(f"\\{quote_char}"):
                        val_content = val_str[1:-1]
                        parsed_val = cls._unescape_string(val_content, quote_char)
                    elif quote_char in val_str[1:]:
                        # Quote ends mid-line (e.g. `KEY="val" # comment`)
                        close_idx = cls._find_closing_quote(val_str, quote_char)
                        if close_idx != -1:
                            val_content = val_str[1:close_idx]
                            parsed_val = cls._unescape_string(val_content, quote_char)
                            rest = val_str[close_idx + 1 :].strip()
                            if rest.startswith("#"):
                                comment_part = rest[1:].strip()
                        else:
                            parsed_val = val_str[1:]
                    else:
                        # Multiline string: read subsequent lines until closing quote
                        val_lines = [val_str[1:]]
                        i += 1
                        while i < n:
                            curr_line = lines[i]
                            if quote_char in curr_line:
                                close_idx = cls._find_closing_quote(curr_line, quote_char)
                                if close_idx != -1:
                                    val_lines.append(curr_line[:close_idx])
                                    break
                                else:
                                    val_lines.append(curr_line)
                            else:
                                val_lines.append(curr_line)
                            i += 1
                        parsed_val = cls._unescape_string("\n".join(val_lines), quote_char)
                else:
                    # Unquoted value: check for inline comments
                    if " #" in val_str:
                        val_part, _, comment_part = val_str.partition(" #")
                        parsed_val = val_part.strip()
                        comment_part = comment_part.strip()
                    elif val_str.startswith("#"):
                        parsed_val = ""
                        comment_part = val_str[1:].strip()
                    else:
                        parsed_val = val_str

                entries.append(
                    EnvEntry(
                        entry_type=EnvEntryType.KEY_VALUE,
                        raw_line=raw_line,
                        key=key,
                        value=parsed_val,
                        comment=comment_part,
                    )
                )

            i += 1

        return EnvFile(entries=entries)

    @classmethod
    def _find_closing_quote(cls, s: str, quote_char: str) -> int:
        """Find index of unescaped closing quote starting after index 0."""
        for idx in range(1, len(s)):
            if s[idx] == quote_char and s[idx - 1] != "\\":
                return idx
        return -1

    @classmethod
    def _unescape_string(cls, s: str, quote_char: str) -> str:
        """Unescape common escape characters inside quoted strings."""
        if quote_char == '"':
            return (
                s.replace('\\"', '"')
                .replace("\\n", "\n")
                .replace("\\r", "\r")
                .replace("\\t", "\t")
                .replace("\\\\", "\\")
            )
        return s.replace(f"\\{quote_char}", quote_char)

    @classmethod
    def detect_project_requirements(
        cls,
        root_path: Path,
        has_local_postgres: bool = False,
        has_local_redis: bool = False,
    ) -> list[EnvRequirement]:
        """Detect all environment variable requirements for a project repository."""
        requirements_map: dict[str, EnvRequirement] = {}

        # 1. Scan .env and template files
        for filename in [".env.example", ".env.template", ".env.sample", ".env.dist", ".env.local.example"]:
            env_path = root_path / filename
            if env_path.exists() and env_path.is_file():
                env_file = cls.parse_env_file(env_path)
                for entry in env_file.entries:
                    if entry.entry_type == EnvEntryType.KEY_VALUE and entry.key:
                        name = entry.key
                        if name not in requirements_map:
                            has_default = bool(entry.value and entry.value.strip())
                            classification = EnvClassifier.classify(
                                name,
                                has_local_postgres=has_local_postgres,
                                has_local_redis=has_local_redis,
                                has_default=has_default,
                            )
                            requirements_map[name] = EnvRequirement(
                                name=name,
                                classification=classification,
                                is_required=True,
                                default_value=entry.value,
                                is_secret=is_sensitive_key(name),
                                description=entry.comment,
                                source=filename,
                            )

        # 2. Check existing .env file for current values
        active_env_path = root_path / ".env"
        if active_env_path.exists() and active_env_path.is_file():
            active_env = cls.parse_env_file(active_env_path)
            for entry in active_env.entries:
                if entry.entry_type == EnvEntryType.KEY_VALUE and entry.key:
                    name = entry.key
                    if name in requirements_map:
                        requirements_map[name].current_value = entry.value
                    else:
                        classification = EnvClassifier.classify(
                            name,
                            has_local_postgres=has_local_postgres,
                            has_local_redis=has_local_redis,
                            has_default=bool(entry.value),
                        )
                        requirements_map[name] = EnvRequirement(
                            name=name,
                            classification=classification,
                            is_required=False,
                            current_value=entry.value,
                            is_secret=is_sensitive_key(name),
                            source=".env",
                        )

        # 3. Check Docker Compose files
        for compose_name in ["compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"]:
            compose_path = root_path / compose_name
            if compose_path.exists() and compose_path.is_file():
                try:
                    data = yaml.safe_load(compose_path.read_text(encoding="utf-8", errors="replace"))
                    if isinstance(data, dict) and "services" in data and isinstance(data["services"], dict):
                        for _, s_cfg in data["services"].items():
                            if isinstance(s_cfg, dict) and "environment" in s_cfg:
                                env_data = s_cfg["environment"]
                                if isinstance(env_data, dict):
                                    for k, v in env_data.items():
                                        if k not in requirements_map:
                                            requirements_map[k] = EnvRequirement(
                                                name=k,
                                                classification=EnvClassifier.classify(
                                                    k,
                                                    has_local_postgres=has_local_postgres,
                                                    has_local_redis=has_local_redis,
                                                    has_default=bool(v),
                                                ),
                                                is_required=True,
                                                default_value=str(v) if v is not None else None,
                                                is_secret=is_sensitive_key(k),
                                                source=compose_name,
                                            )
                                elif isinstance(env_data, list):
                                    for item in env_data:
                                        if isinstance(item, str) and "=" in item:
                                            k, _, v = item.partition("=")
                                            k = k.strip()
                                            if k and k not in requirements_map:
                                                requirements_map[k] = EnvRequirement(
                                                    name=k,
                                                    classification=EnvClassifier.classify(
                                                        k,
                                                        has_local_postgres=has_local_postgres,
                                                        has_local_redis=has_local_redis,
                                                        has_default=bool(v),
                                                    ),
                                                    is_required=True,
                                                    default_value=v.strip() if v else None,
                                                    is_secret=is_sensitive_key(k),
                                                    source=compose_name,
                                                )
                except Exception:
                    pass

        # 4. Scoped source-code scanning (entrypoints & configs)
        cls._scan_source_code_references(
            root_path,
            requirements_map,
            has_local_postgres=has_local_postgres,
            has_local_redis=has_local_redis,
        )

        return sorted(requirements_map.values(), key=lambda r: r.name)

    @classmethod
    def _scan_source_code_references(
        cls,
        root_path: Path,
        requirements_map: dict[str, EnvRequirement],
        has_local_postgres: bool,
        has_local_redis: bool,
    ) -> None:
        """Scan top-level config files and entrypoints for deterministic env var accesses."""
        config_files = [
            "settings.py",
            "config.py",
            "main.py",
            "app.py",
            "server.py",
            "index.ts",
            "index.js",
            "server.ts",
            "server.js",
            "app.ts",
            "app.js",
            "next.config.js",
            "next.config.mjs",
            "next.config.ts",
            "vite.config.ts",
            "vite.config.js",
        ]

        # Scan root files and src/ immediate files
        candidate_paths: list[Path] = []
        for name in config_files:
            p = root_path / name
            if p.exists() and p.is_file():
                candidate_paths.append(p)
            src_p = root_path / "src" / name
            if src_p.exists() and src_p.is_file():
                candidate_paths.append(src_p)

        for p in candidate_paths:
            try:
                # Cap file size to 256KB to avoid reading bundles
                if p.stat().st_size > 256 * 1024:
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
                rel_path = str(p.relative_to(root_path))

                # Node patterns
                for match in _NODE_PROCESS_ENV_REGEX.finditer(text):
                    key = match.group(1) or match.group(2)
                    if key and key not in requirements_map:
                        requirements_map[key] = EnvRequirement(
                            name=key,
                            classification=EnvClassifier.classify(
                                key,
                                has_local_postgres=has_local_postgres,
                                has_local_redis=has_local_redis,
                            ),
                            is_required=True,
                            is_secret=is_sensitive_key(key),
                            source=rel_path,
                        )

                # Python patterns
                for match in _PYTHON_OS_ENV_REGEX.finditer(text):
                    key = match.group(1) or match.group(3)
                    default_val = match.group(2)
                    if key and key not in requirements_map:
                        requirements_map[key] = EnvRequirement(
                            name=key,
                            classification=EnvClassifier.classify(
                                key,
                                has_local_postgres=has_local_postgres,
                                has_local_redis=has_local_redis,
                                has_default=bool(default_val),
                            ),
                            is_required=True,
                            default_value=default_val,
                            is_secret=is_sensitive_key(key),
                            source=rel_path,
                        )
            except Exception:
                pass
