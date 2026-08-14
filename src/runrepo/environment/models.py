"""Domain models for local machine environment inspection and status evaluation."""

from enum import StrEnum
from pydantic import BaseModel, Field

from runrepo.models.evidence import DetectionEvidence


class EnvironmentStatus(StrEnum):
    """Standardized operational status for an environment capability or tool."""

    OK = "OK"
    MISSING = "MISSING"
    WRONG_VERSION = "WRONG_VERSION"
    BROKEN = "BROKEN"
    UNKNOWN = "UNKNOWN"


class EnvironmentCheck(BaseModel):
    """Result of inspecting an individual tool or runtime in the local environment."""

    name: str = Field(description="Name of the inspected tool/runtime, e.g. 'node', 'python', 'docker'")
    status: EnvironmentStatus = Field(description="Operational status of the capability")
    required: bool = Field(
        default=False,
        description="Whether this capability is required by the analyzed project",
    )
    required_version: str | None = Field(
        default=None,
        description="Version constraint specified by the project, e.g. '>=22', '>=3.11'",
    )
    installed_version: str | None = Field(
        default=None,
        description="Discovered version of the installed executable",
    )
    executable_path: str | None = Field(
        default=None,
        description="Resolved filesystem path to the executable",
    )
    details: str | None = Field(
        default=None,
        description="Additional diagnostic detail, error message, or plugin information",
    )
    evidence: list[DetectionEvidence] = Field(
        default_factory=list,
        description="Evidence from repository analysis justifying why this tool is required",
    )


class EnvironmentState(BaseModel):
    """Comprehensive snapshot of host environment capabilities evaluated against project requirements."""

    checks: list[EnvironmentCheck] = Field(
        default_factory=list,
        description="List of all individual capability check results",
    )
    platform: str = Field(description="Host OS platform string, e.g. 'Windows 11', 'Linux'")
    architecture: str = Field(description="CPU architecture string, e.g. 'x86_64', 'arm64'")
    is_satisfied: bool = Field(
        default=True,
        description="True if all required project capabilities are satisfied (OK)",
    )
    missing_checks: list[str] = Field(
        default_factory=list,
        description="Names of required tools that are completely missing",
    )
    wrong_version_checks: list[str] = Field(
        default_factory=list,
        description="Names of required tools that have incompatible versions installed",
    )
    broken_checks: list[str] = Field(
        default_factory=list,
        description="Names of required tools that are installed but not functioning properly",
    )
    unknown_checks: list[str] = Field(
        default_factory=list,
        description="Names of required tools whose state could not be reliably determined",
    )
