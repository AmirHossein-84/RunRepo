"""Composite ProjectInfo and subproject models."""

from enum import StrEnum
from pydantic import BaseModel, Field

from runrepo.models.components import (
    DatabaseRequirement,
    DependencyInfo,
    DockerInfo,
    EnvironmentVariable,
    FrameworkInfo,
    ProjectScript,
    ServiceRequirement,
)
from runrepo.models.evidence import DetectionEvidence
from runrepo.models.runtime import PackageManagerInfo, RuntimeInfo


class AnalysisWarning(BaseModel):
    """Warning raised during repository analysis (e.g. invalid/malformed config file)."""

    file_path: str = Field(description="Relative path of file that caused warning")
    message: str = Field(description="Human-readable warning message")
    code: str = Field(default="SYNTAX_OR_PARSE_ERROR", description="Machine-readable error code")


class SubprojectInfo(BaseModel):
    """Discovered subproject / workspace package in polyglot or monorepo setups."""

    name: str = Field(description="Subproject name or directory name")
    path: str = Field(description="Relative path from repo root, e.g. 'frontend', 'apps/web'")
    languages: list[str] = Field(default_factory=list, description="Languages detected in subproject")
    runtimes: list[RuntimeInfo] = Field(default_factory=list, description="Runtimes used by subproject")
    package_managers: list[PackageManagerInfo] = Field(
        default_factory=list, description="Package managers used by subproject"
    )
    frameworks: list[FrameworkInfo] = Field(default_factory=list, description="Frameworks used by subproject")
    scripts: list[ProjectScript] = Field(default_factory=list, description="Scripts defined in subproject")
    dependencies: list[DependencyInfo] = Field(
        default_factory=list, description="Dependencies declared in subproject"
    )
    databases: list[DatabaseRequirement] = Field(
        default_factory=list, description="Databases used directly by subproject"
    )
    evidence: list[DetectionEvidence] = Field(default_factory=list)


class ProjectType(StrEnum):
    """High-level classification of the repository."""

    WEB_APPLICATION = "web_application"
    API_SERVICE = "api_service"
    CLI_TOOL = "cli_tool"
    LIBRARY = "library"
    POLYGLOT_FULLSTACK = "polyglot_fullstack"
    UNKNOWN = "unknown"


class ProjectInfo(BaseModel):
    """Complete, structured repository analysis result.

    Preserves structured evidence for every detected fact, distinguishes
    subprojects in polyglot / monorepo repositories, and captures all runtimes,
    package managers, frameworks, scripts, dependencies, databases, docker,
    and environment variables.
    """

    path: str = Field(description="Absolute path to analyzed repository")
    name: str = Field(description="Repository or project name")
    project_type: ProjectType = Field(
        default=ProjectType.UNKNOWN,
        description="Inferred primary project type",
    )
    is_monorepo: bool = Field(
        default=False,
        description="Whether repository contains multiple workspaces or subprojects",
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Distinct programming/markup languages detected",
    )
    runtimes: list[RuntimeInfo] = Field(
        default_factory=list,
        description="All detected runtimes and version requirements",
    )
    package_managers: list[PackageManagerInfo] = Field(
        default_factory=list,
        description="Detected package managers and lockfiles",
    )
    frameworks: list[FrameworkInfo] = Field(
        default_factory=list,
        description="Detected frameworks",
    )
    scripts: list[ProjectScript] = Field(
        default_factory=list,
        description="All runnable scripts from root or subprojects",
    )
    dependencies: list[DependencyInfo] = Field(
        default_factory=list,
        description="Direct and dev dependencies",
    )
    environment_variables: list[EnvironmentVariable] = Field(
        default_factory=list,
        description="Detected required or optional environment variables",
    )
    databases: list[DatabaseRequirement] = Field(
        default_factory=list,
        description="Databases detected via ORMs, compose, or env hints",
    )
    services: list[ServiceRequirement] = Field(
        default_factory=list,
        description="Auxiliary services (e.g. Redis, RabbitMQ)",
    )
    docker: DockerInfo = Field(
        default_factory=DockerInfo,
        description="Docker and Docker Compose definitions",
    )
    subprojects: list[SubprojectInfo] = Field(
        default_factory=list,
        description="Isolated subprojects in polyglot or monorepo setups",
    )
    entrypoints: list[str] = Field(
        default_factory=list,
        description="Discovered executable entrypoints (e.g. main.py, app.py)",
    )
    warnings: list[AnalysisWarning] = Field(
        default_factory=list,
        description="Non-fatal warnings encountered during analysis",
    )
    evidence: list[DetectionEvidence] = Field(
        default_factory=list,
        description="High-level project detection evidence",
    )
