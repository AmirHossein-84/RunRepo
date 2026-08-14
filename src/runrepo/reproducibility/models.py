"""Domain models for RunRepo reproducibility configuration and deterministic lockfiles."""

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Configuration Models (runrepo.yaml)
# ---------------------------------------------------------

class ServiceConfigOverride(BaseModel):
    """User configuration override for a specific service."""

    image: str | None = Field(default=None, description="Custom Docker image, e.g. 'postgres:16-alpine'")
    port: int | None = Field(default=None, description="Custom host port mapping")
    database_name: str | None = Field(default=None, description="Database name")
    environment: dict[str, str] = Field(default_factory=dict, description="Custom non-sensitive service environment variables")


class EnvConfig(BaseModel):
    """Configuration for environment variable handling."""

    auto_generate_local_secrets: bool = Field(
        default=True,
        description="Whether to generate random local secrets for development in .env",
    )
    defaults: dict[str, str] = Field(
        default_factory=dict,
        description="Default non-sensitive environment variables",
    )


class StartupConfig(BaseModel):
    """Configuration for startup command override."""

    command: str | list[str] | None = Field(
        default=None,
        description="Explicit startup command override string or tokens",
    )
    working_dir: str | None = Field(
        default=None,
        description="Relative subproject working directory",
    )


class RunRepoConfig(BaseModel):
    """User-editable configuration from runrepo.yaml."""

    version: int = Field(default=1, description="Configuration schema version")
    name: str | None = Field(default=None, description="Project name override")
    runtimes: dict[str, str] = Field(
        default_factory=dict,
        description="Required runtime versions (e.g. {'node': '>=20', 'python': '>=3.11'})",
    )
    package_manager: str | None = Field(
        default=None,
        description="Preferred package manager override (e.g. 'pnpm', 'uv')",
    )
    docker: bool = Field(
        default=True,
        description="Whether Docker infrastructure is enabled for this project",
    )
    services: dict[str, ServiceConfigOverride] = Field(
        default_factory=dict,
        description="Service configuration overrides keyed by service name",
    )
    environment: EnvConfig = Field(
        default_factory=EnvConfig,
        description="Environment variable configuration",
    )
    startup: StartupConfig = Field(
        default_factory=StartupConfig,
        description="Startup command configuration",
    )
    ai: bool | None = Field(
        default=None,
        description="Override for AI assistance (True/False/None for auto)",
    )


# ---------------------------------------------------------
# Lockfile Models (runrepo.lock)
# ---------------------------------------------------------

class RepositoryLockInfo(BaseModel):
    """Repository identity and revision tracking."""

    name: str = Field(description="Repository or project name")
    remote_url: str | None = Field(default=None, description="Sanitized git remote URL")
    commit_hash: str | None = Field(default=None, description="Git commit hash if in a git repository")
    ref: str | None = Field(default=None, description="Git branch or tag reference")


class PlatformLockInfo(BaseModel):
    """Host platform identity at the time of resolution."""

    os: str = Field(description="Operating system, e.g. 'windows', 'linux', 'darwin'")
    arch: str = Field(description="CPU architecture, e.g. 'x86_64', 'arm64'")


class ResolvedServiceLock(BaseModel):
    """Resolved service container and configuration."""

    name: str = Field(description="Service identifier, e.g. 'postgres', 'redis'")
    image: str | None = Field(default=None, description="Resolved Docker image tag")
    port: int | None = Field(default=None, description="Resolved host port")
    database_name: str | None = Field(default=None, description="Resolved database name")
    container_name: str | None = Field(default=None, description="Resolved container name")


class ResolvedEnvLock(BaseModel):
    """Metadata about resolved environment variables (STRICTLY NO SECRETS)."""

    name: str = Field(description="Environment variable name")
    category: str = Field(description="EnvVarCategory string")
    source: str = Field(description="Resolution source, e.g. 'generated', 'local_default', 'user_required'")
    is_secret: bool = Field(default=False, description="Whether this variable is classified as a secret")


class ResolvedStartupLock(BaseModel):
    """Resolved startup command and configuration."""

    command: list[str] = Field(default_factory=list, description="Resolved startup command token list")
    working_dir: str | None = Field(default=None, description="Resolved working directory")


class RunRepoLock(BaseModel):
    """Deterministic, secret-free record of resolved setup decisions."""

    lock_version: int = Field(default=1, description="Lockfile format version")
    runrepo_version: str = Field(default="0.1.0", description="RunRepo version that generated the lockfile")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp",
    )
    repository: RepositoryLockInfo = Field(description="Repository metadata")
    platform: PlatformLockInfo = Field(description="Host platform details")
    resolved_runtimes: dict[str, str] = Field(
        default_factory=dict,
        description="Resolved runtime versions, e.g. {'node': '20.11.0', 'python': '3.12.2'}",
    )
    resolved_package_manager: str | None = Field(
        default=None,
        description="Resolved package manager, e.g. 'pnpm', 'uv'",
    )
    resolved_services: list[ResolvedServiceLock] = Field(
        default_factory=list,
        description="Resolved service dependencies and ports",
    )
    resolved_environment: list[ResolvedEnvLock] = Field(
        default_factory=list,
        description="Resolved environment variables metadata (no values)",
    )
    resolved_startup: ResolvedStartupLock = Field(
        default_factory=ResolvedStartupLock,
        description="Resolved startup command",
    )
    plan_steps: list[str] = Field(
        default_factory=list,
        description="Ordered list of resolved plan step IDs",
    )


# ---------------------------------------------------------
# Comparator / Drift Models
# ---------------------------------------------------------

class LockDiff(BaseModel):
    """Structured diff between current environment/repository state and runrepo.lock."""

    has_changes: bool = Field(default=False, description="Whether any difference was detected")
    is_compatible: bool = Field(default=True, description="Whether current state is compatible with the lockfile")
    runtime_diffs: dict[str, tuple[str | None, str | None]] = Field(
        default_factory=dict,
        description="Runtime version differences (locked_version, current_version)",
    )
    package_manager_diff: tuple[str | None, str | None] | None = Field(
        default=None,
        description="Package manager difference (locked_pm, current_pm)",
    )
    service_diffs: dict[str, tuple[Any, Any]] = Field(
        default_factory=dict,
        description="Service configuration differences",
    )
    startup_diff: tuple[list[str] | None, list[str] | None] | None = Field(
        default=None,
        description="Startup command difference (locked_cmd, current_cmd)",
    )
    env_diffs: list[str] = Field(
        default_factory=list,
        description="New or missing environment variables",
    )
    commit_diff: tuple[str | None, str | None] | None = Field(
        default=None,
        description="Git commit difference (locked_commit, current_commit)",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Human-readable warning messages about detected drift",
    )
