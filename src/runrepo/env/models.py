"""Domain models for project environment variables and .env file representation."""

from enum import StrEnum
from pydantic import BaseModel, Field


class EnvClassification(StrEnum):
    """Classification of environment variables based on automation safety."""

    AUTO_GENERATABLE = "auto_generatable"  # Safe local secrets, database URLs
    LOCAL_DEFAULT = "local_default"        # Standard defaults (PORT, HOST, NODE_ENV)
    USER_REQUIRED = "user_required"        # Project-specific required variable
    EXTERNAL_SERVICE = "external_service"  # 3rd-party cloud keys (OPENAI, AWS, STRIPE)


class EnvRequirement(BaseModel):
    """A single environment variable requirement detected in the repository."""

    name: str = Field(description="Environment variable name, e.g. DATABASE_URL")
    classification: EnvClassification = Field(
        default=EnvClassification.USER_REQUIRED,
        description="Automation classification",
    )
    is_required: bool = Field(default=True, description="Whether this variable is mandatory")
    default_value: str | None = Field(default=None, description="Suggested or example default value")
    current_value: str | None = Field(default=None, description="Current value if already set")
    is_secret: bool = Field(default=False, description="Whether this variable is sensitive/secret")
    description: str | None = Field(default=None, description="Description or inline comment")
    source: str = Field(default="unknown", description="Detection source (e.g. .env.example, compose.yaml)")


class EnvEntryType(StrEnum):
    """Type of line in a .env file."""

    KEY_VALUE = "key_value"
    COMMENT = "comment"
    BLANK = "blank"


class EnvEntry(BaseModel):
    """Parsed single entry in a .env file to enable lossless round-tripping."""

    entry_type: EnvEntryType = Field(description="Type of entry")
    raw_line: str = Field(description="Exact original line text")
    key: str | None = Field(default=None, description="Variable name if KEY_VALUE")
    value: str | None = Field(default=None, description="Variable value if KEY_VALUE")
    comment: str | None = Field(default=None, description="Comment text if COMMENT or inline comment")


class EnvFile(BaseModel):
    """Structured representation of a .env file preserving ordering and comments."""

    entries: list[EnvEntry] = Field(default_factory=list)

    def get_value(self, key: str) -> str | None:
        """Get the value of a key if present."""
        for entry in self.entries:
            if entry.entry_type == EnvEntryType.KEY_VALUE and entry.key == key:
                return entry.value
        return None

    def has_key(self, key: str) -> bool:
        """Check if a key exists."""
        return any(e.entry_type == EnvEntryType.KEY_VALUE and e.key == key for e in self.entries)

    def set_value(self, key: str, value: str) -> None:
        """Update an existing key or append a new one."""
        for entry in self.entries:
            if entry.entry_type == EnvEntryType.KEY_VALUE and entry.key == key:
                entry.value = value
                entry.raw_line = f"{key}={value}"
                return
        # Append new
        self.entries.append(
            EnvEntry(
                entry_type=EnvEntryType.KEY_VALUE,
                raw_line=f"{key}={value}",
                key=key,
                value=value,
            )
        )

    def add_comment(self, comment_text: str) -> None:
        """Append a comment line."""
        prefix = "# " if not comment_text.startswith("#") else ""
        raw = f"{prefix}{comment_text}"
        self.entries.append(
            EnvEntry(
                entry_type=EnvEntryType.COMMENT,
                raw_line=raw,
                comment=comment_text,
            )
        )

    def add_blank(self) -> None:
        """Append a blank line."""
        self.entries.append(
            EnvEntry(
                entry_type=EnvEntryType.BLANK,
                raw_line="",
            )
        )

    def to_string(self) -> str:
        """Serialize entries back to a .env string format."""
        lines = [e.raw_line for e in self.entries]
        content = "\n".join(lines)
        if content and not content.endswith("\n"):
            content += "\n"
        return content
