"""Security utilities for detecting sensitive keys and redacting values in logs and output."""

import re

SENSITIVE_KEY_PATTERNS = [
    r"SECRET",
    r"PASSWORD",
    r"PASSWD",
    r"TOKEN",
    r"API_?KEY",
    r"AUTH",
    r"CREDENTIAL",
    r"PRIVATE",
    r"SIGNING",
    r"SALT",
    r"CERT",
    r"WEBHOOK",
    r"ACCESS_KEY",
    r"CLIENT_SECRET",
]

_COMPILED_SENSITIVE_REGEX = re.compile(
    "|".join(SENSITIVE_KEY_PATTERNS),
    re.IGNORECASE,
)


def is_sensitive_key(key: str) -> bool:
    """Determine whether an environment variable name indicates sensitive data/secrets."""
    if not key:
        return False
    return bool(_COMPILED_SENSITIVE_REGEX.search(key))


def redact_value(key: str, value: str | None) -> str:
    """Return a masked representation of a sensitive value for safe logging."""
    if not value:
        return ""
    if not is_sensitive_key(key):
        return value

    val_len = len(value)
    if val_len <= 6:
        return "******"

    # Show first 3 chars and mask rest with asterisks
    prefix = value[:3]
    return f"{prefix}{'*' * min(val_len - 3, 10)}"
