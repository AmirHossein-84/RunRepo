"""Domain models for monorepo and workspace detection and resolution."""

from enum import StrEnum
from pydantic import BaseModel, Field


class WorkspaceType(StrEnum):
    """Classification of monorepo workspace orchestration."""

    PNPM = "pnpm"
    NPM = "npm"
    YARN = "yarn"
    TURBOREPO = "turborepo"
    NX = "nx"
    LERNA = "lerna"
    UV_WORKSPACE = "uv_workspace"
    POETRY_WORKSPACE = "poetry_workspace"
    DIRECTORY_SUBPROJECTS = "directory_subprojects"
    SINGLE_PROJECT = "single_project"


class WorkspacePackage(BaseModel):
    """Information about an individual package or application within a monorepo workspace."""

    name: str = Field(description="Package name from package.json or pyproject.toml")
    path: str = Field(description="Relative path from repository root, e.g. 'apps/web', 'packages/ui'")
    version: str | None = Field(default=None, description="Package version if specified")
    scripts: dict[str, str] = Field(
        default_factory=dict,
        description="Runnable scripts declared in this package (e.g. {'dev': 'next dev'})",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Internal and external dependencies referenced by this package",
    )
    is_runnable: bool = Field(
        default=False,
        description="Whether this package declares executable dev/start scripts",
    )
    is_application: bool = Field(
        default=False,
        description="Whether this package is classified as an application rather than a shared library",
    )
    framework: str | None = Field(
        default=None,
        description="Detected framework for this package (e.g. Next.js, FastAPI)",
    )


class MonorepoInfo(BaseModel):
    """Structured result of monorepo workspace detection."""

    is_monorepo: bool = Field(default=False, description="Whether a monorepo layout was detected")
    workspace_type: WorkspaceType = Field(
        default=WorkspaceType.SINGLE_PROJECT,
        description="Workspace tool or layout pattern detected",
    )
    root_path: str = Field(description="Absolute path to workspace root")
    packages: list[WorkspacePackage] = Field(
        default_factory=list,
        description="All discovered workspace packages and shared modules",
    )
    runnable_apps: list[WorkspacePackage] = Field(
        default_factory=list,
        description="Workspace packages identified as runnable applications (e.g. web, api)",
    )
