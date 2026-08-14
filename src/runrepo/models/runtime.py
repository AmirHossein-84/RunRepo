"""Runtime and package manager domain models."""

from pydantic import BaseModel, Field
from runrepo.models.evidence import DetectionEvidence


class RuntimeInfo(BaseModel):
    """Detected language/runtime information."""

    name: str = Field(description="Runtime name, e.g. 'node', 'python'")
    version: str | None = Field(
        default=None,
        description="Version requirement or detected version, e.g. '22', '>=3.11'",
    )
    version_raw: str | None = Field(
        default=None,
        description="Raw unparsed version string from source",
    )
    evidence: list[DetectionEvidence] = Field(
        default_factory=list,
        description="List of evidence sources supporting this runtime detection",
    )


class PackageManagerInfo(BaseModel):
    """Detected package manager information."""

    name: str = Field(description="Package manager name, e.g. 'pnpm', 'npm', 'yarn', 'uv', 'poetry', 'pip'")
    version: str | None = Field(
        default=None,
        description="Package manager version requirement if specified",
    )
    lockfile: str | None = Field(
        default=None,
        description="Associated lockfile name, e.g. 'pnpm-lock.yaml'",
    )
    evidence: list[DetectionEvidence] = Field(
        default_factory=list,
        description="Evidence sources supporting this package manager detection",
    )
