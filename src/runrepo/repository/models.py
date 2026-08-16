"""Domain models for repository identification, GitHub targets, and clone operations."""

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from pydantic import BaseModel, Field


class RepositorySource(StrEnum):
    """Source origin of the repository."""

    LOCAL = "LOCAL"
    GITHUB_HTTPS = "GITHUB_HTTPS"
    GITHUB_SSH = "GITHUB_SSH"
    GITHUB_SHORTHAND = "GITHUB_SHORTHAND"
    GITHUB_PR = "GITHUB_PR"


class PullRequestTarget(BaseModel):
    """Structured representation of a parsed GitHub Pull Request target."""

    raw_input: str = Field(description="Original user-provided PR URL")
    owner: str = Field(description="GitHub repository owner/organization")
    repo: str = Field(description="Repository name")
    pr_number: int = Field(description="Pull request issue number")
    clone_url: str = Field(description="Base GitHub HTTPS clone URL")
    ref: str = Field(description="Git ref to fetch, e.g. 'pull/123/head'")


class CloneStatus(StrEnum):
    """Status of repository clone/cache resolution."""

    NOT_CLONED = "NOT_CLONED"
    CLONED = "CLONED"
    CACHED = "CACHED"
    FAILED = "FAILED"


class RepositoryTarget(BaseModel):
    """Structured representation of a parsed repository target."""

    source: RepositorySource = Field(description="Origin category (local directory or GitHub reference)")
    raw_input: str = Field(description="Original user-provided path or URL string")
    owner: str | None = Field(default=None, description="GitHub repository owner/organization")
    name: str | None = Field(default=None, description="Repository project name")
    branch: str | None = Field(default=None, description="Target branch, tag, or commit reference if specified")
    clone_url: str | None = Field(default=None, description="Canonical HTTPS/SSH git clone URL")
    local_path: Path | None = Field(default=None, description="Resolved local directory path on disk")
    status: CloneStatus = Field(default=CloneStatus.NOT_CLONED, description="Clone or cache lifecycle status")


class RepositoryResult(BaseModel):
    """Outcome of repository acquisition or cache resolution."""

    success: bool = Field(description="Whether repository is ready on local filesystem")
    target: RepositoryTarget = Field(description="Parsed target metadata")
    local_path: Path | None = Field(default=None, description="Absolute local path to the repository on disk")
    error_message: str | None = Field(default=None, description="Sanitized failure explanation if acquisition failed")
    git_output: str | None = Field(default=None, description="Sanitized git stdout/stderr output")
    exit_code: int | None = Field(default=None, description="Git process return code")
    duration_ms: float = Field(default=0.0, description="Acquisition execution time in milliseconds")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp",
    )


class CachedRepository(BaseModel):
    """Metadata for a cached remote repository directory."""

    name: str = Field(description="Cache directory slug identifier")
    owner: str | None = Field(default=None, description="Repository owner")
    repo: str | None = Field(default=None, description="Repository name")
    path: Path = Field(description="Filesystem path to cached repository")
    size_bytes: int = Field(default=0, description="Total size in bytes on disk")
    last_used_at: str | None = Field(default=None, description="ISO timestamp of last access")
    is_valid: bool = Field(default=True, description="Whether .git structure is valid")
    commit_hash: str | None = Field(default=None, description="Current commit hash")
    ref: str | None = Field(default=None, description="Current branch/tag ref")


class CacheMetadata(BaseModel):
    """Aggregated metadata for the RunRepo repository cache."""

    total_repositories: int = Field(default=0, description="Number of cached repositories")
    total_size_bytes: int = Field(default=0, description="Total size of all cached repositories in bytes")
    cache_dir: str = Field(description="Root cache directory path")
    repositories: list[CachedRepository] = Field(
        default_factory=list,
        description="List of all cached repositories",
    )
