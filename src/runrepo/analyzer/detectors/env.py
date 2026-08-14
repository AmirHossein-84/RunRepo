"""Deterministic environment variable requirement detector."""

import re

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.models import (
    Confidence,
    DetectionEvidence,
    EnvVarCategory,
    EnvironmentVariable,
)

ENV_FILE_PATTERNS = (
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.dist",
    ".env.local.example",
    "example.env",
)

ENV_LINE_REGEX = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def categorize_env_var(name: str) -> EnvVarCategory:
    """Categorize an environment variable based on standard naming conventions."""
    upper = name.upper()
    if any(
        k in upper
        for k in (
            "STRIPE",
            "AWS",
            "OPENAI",
            "GITHUB",
            "GOOGLE",
            "AZURE",
            "SENTRY",
            "RESEND",
            "TWILIO",
            "SENDGRID",
            "PINECONE",
            "CLERK",
            "SUPABASE",
        )
    ):
        return EnvVarCategory.EXTERNAL_SERVICE
    if any(k in upper for k in ("DATABASE", "POSTGRES", "MYSQL", "MONGO", "REDIS", "DB_")):
        return EnvVarCategory.DATABASE
    if any(k in upper for k in ("SECRET", "KEY", "TOKEN", "PASSWORD", "PASS", "JWT", "AUTH_")):
        return EnvVarCategory.SECRET
    if upper in ("PORT", "HOST", "NODE_ENV", "DEBUG", "LOG_LEVEL", "APP_ENV", "PYTHONPATH"):
        return EnvVarCategory.LOCAL_DEFAULT
    return EnvVarCategory.GENERAL


class EnvironmentDetector(BaseDetector):
    """Parses .env.example/template files and Docker Compose env references to detect required variables."""

    @property
    def name(self) -> str:
        return "environment"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()
        vars_map: dict[str, EnvironmentVariable] = {}

        # 1. Discover and parse env template files
        discovered_env_files: list[str] = []
        for file_path in context.get_all_files():
            file_name = file_path.split("/")[-1]
            if file_name in ENV_FILE_PATTERNS or file_name.endswith(".example"):
                discovered_env_files.append(file_path)

        for env_file in discovered_env_files:
            text = context.read_text(env_file)
            if not text:
                continue

            last_comment: str | None = None
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    last_comment = None
                    continue

                if stripped.startswith("#"):
                    comment_body = stripped.lstrip("#").strip()
                    last_comment = comment_body if comment_body else None
                    continue

                match = ENV_LINE_REGEX.match(stripped)
                if match:
                    var_name = match.group(1).strip()
                    raw_val = match.group(2).strip().strip('"').strip("'")
                    category = categorize_env_var(var_name)

                    # Extract inline comment if any
                    description = last_comment
                    if " #" in raw_val:
                        val_part, comment_part = raw_val.split(" #", 1)
                        raw_val = val_part.strip().strip('"').strip("'")
                        description = (
                            f"{description}; {comment_part.strip()}"
                            if description
                            else comment_part.strip()
                        )

                    is_placeholder = raw_val.lower() in (
                        "",
                        "xxx",
                        "your-key",
                        "your_key",
                        "your-token",
                        "change-me",
                        "changeme",
                        "required",
                        "todo",
                        "<your_key>",
                        "replace_me",
                    )

                    default_val = None if is_placeholder else raw_val
                    is_required = is_placeholder or category in (
                        EnvVarCategory.SECRET,
                        EnvVarCategory.DATABASE,
                    )

                    evidence = [
                        DetectionEvidence(
                            source=env_file,
                            detail=f"{var_name}={raw_val}" if raw_val else var_name,
                            confidence=Confidence.HIGH,
                            path=env_file,
                        )
                    ]

                    if var_name not in vars_map:
                        vars_map[var_name] = EnvironmentVariable(
                            name=var_name,
                            description=description,
                            default_value=default_val,
                            is_required=is_required,
                            category=category,
                            evidence=evidence,
                        )
                    else:
                        vars_map[var_name].evidence.extend(evidence)
                        if not vars_map[var_name].default_value and default_val:
                            vars_map[var_name].default_value = default_val

                    last_comment = None

        result.environment_variables.extend(vars_map.values())
        return result
