"""Domain models for step verification, statuses, and diagnostic telemetry."""

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class VerificationStatus(StrEnum):
    """Outcome status of a verification check."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


class VerificationType(StrEnum):
    """Categorized type of verification check performed."""

    DEPENDENCY_CHECK = "DEPENDENCY_CHECK"
    SERVICE_CHECK = "SERVICE_CHECK"
    PROCESS_CHECK = "PROCESS_CHECK"
    PORT_CHECK = "PORT_CHECK"
    HTTP_CHECK = "HTTP_CHECK"
    FILE_CHECK = "FILE_CHECK"
    ENVIRONMENT_CHECK = "ENVIRONMENT_CHECK"
    EXIT_CODE_CHECK = "EXIT_CODE_CHECK"


class VerificationResult(BaseModel):
    """Structured telemetry and outcome of a post-execution verification."""

    step_id: str = Field(description="Associated PlanStep identifier")
    verification_type: VerificationType = Field(description="Classification of verification check")
    status: VerificationStatus = Field(default=VerificationStatus.PASSED, description="Outcome status")
    target: str | None = Field(default=None, description="Target probed (e.g. file, port, URL, container)")
    message: str = Field(description="Human-readable verification outcome message")

    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured verification metrics and observations",
    )
    duration_ms: float = Field(default=0.0, description="Verification execution time in milliseconds")
    failure_reason: str | None = Field(default=None, description="Diagnostic explanation if verification failed")
    diagnostic_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Low-level debug data (HTTP status, error codes, exit codes)",
    )

    @property
    def passed(self) -> bool:
        """Helper returning boolean success status."""
        return self.status == VerificationStatus.PASSED
