"""Base detector contract and detection result container."""

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

from runrepo.analyzer.context import ScanContext
from runrepo.models import (
    DatabaseRequirement,
    DependencyInfo,
    DetectionEvidence,
    DockerInfo,
    EnvironmentVariable,
    FrameworkInfo,
    PackageManagerInfo,
    ProjectScript,
    RuntimeInfo,
    ServiceRequirement,
    SubprojectInfo,
)


class DetectorResult(BaseModel):
    """Normalized output from an individual detector."""

    languages: list[str] = Field(default_factory=list)
    runtimes: list[RuntimeInfo] = Field(default_factory=list)
    package_managers: list[PackageManagerInfo] = Field(default_factory=list)
    frameworks: list[FrameworkInfo] = Field(default_factory=list)
    dependencies: list[DependencyInfo] = Field(default_factory=list)
    scripts: list[ProjectScript] = Field(default_factory=list)
    environment_variables: list[EnvironmentVariable] = Field(default_factory=list)
    databases: list[DatabaseRequirement] = Field(default_factory=list)
    services: list[ServiceRequirement] = Field(default_factory=list)
    docker: DockerInfo | None = Field(default=None)
    subprojects: list[SubprojectInfo] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    is_monorepo: bool = Field(default=False)
    evidence: list[DetectionEvidence] = Field(default_factory=list)


class BaseDetector(ABC):
    """Abstract base class for deterministic domain detectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the detector."""
        pass

    @abstractmethod
    def detect(self, context: ScanContext) -> DetectorResult:
        """Analyze repository via ScanContext and produce facts with structured evidence."""
        pass
