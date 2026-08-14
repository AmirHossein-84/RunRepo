"""Domain models for RunRepo diagnostics, failure classification, and safe action recommendations."""

from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, Field


class DiagnosticSeverity(StrEnum):
    """Severity level of the diagnostic observation."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DiagnosticCategory(StrEnum):
    """Category classification of the identified failure or blocker."""

    ENVIRONMENT = "ENVIRONMENT"
    DEPENDENCY = "DEPENDENCY"
    PROCESS = "PROCESS"
    NETWORK = "NETWORK"
    SERVICE = "SERVICE"
    CONFIGURATION = "CONFIGURATION"
    PERMISSION = "PERMISSION"
    UNKNOWN = "UNKNOWN"


class SuggestedAction(BaseModel):
    """A safe, constructive recommendation or copyable command for the developer."""

    title: str = Field(description="Short human-readable title of the suggested action")
    command: str | None = Field(
        default=None,
        description="Optional safe terminal command suggestion for the developer to run",
    )
    description: str = Field(
        default="",
        description="Detailed instruction or context explaining how to resolve the issue",
    )
    is_safe_to_copy: bool = Field(
        default=True,
        description="Whether this command is completely non-destructive and safe to copy-paste",
    )


class Diagnostic(BaseModel):
    """Structured, explainable diagnostic report for a failure or blocked state."""

    id: str = Field(description="Unique deterministic diagnostic identifier")
    severity: DiagnosticSeverity = Field(
        default=DiagnosticSeverity.ERROR,
        description="Severity classification",
    )
    category: DiagnosticCategory = Field(
        default=DiagnosticCategory.UNKNOWN,
        description="Failure category",
    )
    title: str = Field(description="Clear, concise headline explaining what went wrong")
    explanation: str = Field(description="Detailed explanation of the root cause and why it occurred")
    affected_step_id: str | None = Field(
        default=None,
        description="ID of the execution or planning step where the failure occurred",
    )
    stdout_excerpt: str | None = Field(
        default=None,
        description="Sanitized and redacted snippet of relevant standard output",
    )
    stderr_excerpt: str | None = Field(
        default=None,
        description="Sanitized and redacted snippet of relevant error output",
    )
    exit_code: int | None = Field(
        default=None,
        description="Process exit code if failure was from command execution",
    )
    suggested_actions: list[SuggestedAction] = Field(
        default_factory=list,
        description="List of actionable, safe next steps to resolve the issue",
    )
    related_resources: list[str] = Field(
        default_factory=list,
        description="Referenced files, ports, services, or containers involved",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp",
    )
