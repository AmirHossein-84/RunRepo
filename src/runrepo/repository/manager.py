"""Repository manager orchestrating target resolution, cache validation, and safe acquisition."""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import platformdirs
from runrepo.executor.process import ProcessExecutor
from runrepo.repository.git import GitManager
from runrepo.repository.github import GitHubUrlParser
from runrepo.repository.models import (
    CachedRepository,
    CacheMetadata,
    CloneStatus,
    RepositoryResult,
    RepositorySource,
    RepositoryTarget,
)


class RepositoryManager:
    """Acquires and manages local and remote GitHub repositories."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        git_manager: GitManager | None = None,
        executor: ProcessExecutor | None = None,
    ) -> None:
        self.cache_dir = cache_dir or (Path(platformdirs.user_data_dir("runrepo")) / "repositories")
        self.git_manager = git_manager or GitManager(executor=executor)

    def resolve(
        self,
        input_target: str | Path,
        refresh: bool = False,
        depth: int | None = 1,
    ) -> RepositoryResult:
        """Resolve a local path or remote GitHub target to a verified local directory."""
        target_str = str(input_target).strip()
        try:
            target = GitHubUrlParser.parse(target_str)
        except ValueError as e:
            dummy_target = RepositoryTarget(
                source=RepositorySource.LOCAL,
                raw_input=target_str,
            )
            return RepositoryResult(
                success=False,
                target=dummy_target,
                error_message=str(e),
            )

        # 1. Local filesystem path
        if target.source == RepositorySource.LOCAL:
            if not target.local_path or not target.local_path.exists():
                return RepositoryResult(
                    success=False,
                    target=target,
                    error_message=f"Directory '{target.raw_input}' does not exist.",
                )
            if not target.local_path.is_dir():
                return RepositoryResult(
                    success=False,
                    target=target,
                    error_message=f"Path '{target.raw_input}' is not a directory.",
                )
            return RepositoryResult(
                success=True,
                target=target,
                local_path=target.local_path,
            )

        # 2. Remote GitHub repository
        dest_folder_name = f"{target.owner}_{target.name}"
        if target.branch:
            # Suffix branch slug to cache path if a specific branch is specified
            branch_slug = target.branch.replace("/", "_")
            dest_folder_name = f"{dest_folder_name}_{branch_slug}"

        destination = (self.cache_dir / dest_folder_name).resolve()

        # Check existing cache
        if destination.exists():
            if not refresh and self.git_manager.verify_repository_valid(destination):
                target.status = CloneStatus.CACHED
                target.local_path = destination
                return RepositoryResult(
                    success=True,
                    target=target,
                    local_path=destination,
                )
            # Remove invalid or refresh-requested cache
            shutil.rmtree(destination, ignore_errors=True)

        # Clone remote repository
        return self.git_manager.clone(target, destination, depth=depth)

    def list_cached(self) -> CacheMetadata:
        """List all cached repositories, disk usage, and health status."""
        if not self.cache_dir.exists():
            return CacheMetadata(cache_dir=str(self.cache_dir))

        cached_repos: list[CachedRepository] = []
        total_size = 0

        for entry in sorted(self.cache_dir.iterdir()):
            if not entry.is_dir():
                continue

            size = self._compute_directory_size(entry)
            total_size += size

            is_valid = self.git_manager.verify_repository_valid(entry)
            mtime_dt = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc).isoformat()

            parts = entry.name.split("_")
            owner = parts[0] if len(parts) >= 1 else None
            repo = parts[1] if len(parts) >= 2 else None

            cached_repos.append(
                CachedRepository(
                    name=entry.name,
                    owner=owner,
                    repo=repo,
                    path=entry,
                    size_bytes=size,
                    last_used_at=mtime_dt,
                    is_valid=is_valid,
                )
            )

        return CacheMetadata(
            total_repositories=len(cached_repos),
            total_size_bytes=total_size,
            cache_dir=str(self.cache_dir),
            repositories=cached_repos,
        )

    def clean_cache(
        self,
        target: str | None = None,
        older_than_days: int | None = None,
    ) -> list[str]:
        """Safely remove cached repository directories inside the RunRepo cache directory."""
        if not self.cache_dir.exists():
            return []

        removed: list[str] = []
        now_ts = datetime.now(timezone.utc).timestamp()

        for entry in self.cache_dir.iterdir():
            if not entry.is_dir():
                continue

            # Target filter
            if target is not None:
                slug_target = target.replace("/", "_")
                if entry.name != target and entry.name != slug_target and not entry.name.startswith(f"{slug_target}_"):
                    continue

            # Age filter
            if older_than_days is not None:
                age_days = (now_ts - entry.stat().st_mtime) / (24 * 3600)
                if age_days < older_than_days:
                    continue

            # Safe removal strictly within cache_dir
            try:
                shutil.rmtree(entry, ignore_errors=True)
                removed.append(entry.name)
            except Exception:
                pass

        return removed

    @classmethod
    def _compute_directory_size(cls, directory: Path) -> int:
        """Calculate total size of a directory in bytes."""
        total = 0
        try:
            for root, _, files in os.walk(directory):
                for f in files:
                    fp = Path(root) / f
                    try:
                        total += fp.stat().st_size
                    except OSError:
                        pass
        except Exception:
            pass
        return total
