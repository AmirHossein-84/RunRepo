"""Repository manager orchestrating target resolution, cache validation, and safe acquisition."""

import shutil
from pathlib import Path
import platformdirs
from runrepo.executor.process import ProcessExecutor
from runrepo.repository.git import GitManager
from runrepo.repository.github import GitHubUrlParser
from runrepo.repository.models import CloneStatus, RepositoryResult, RepositorySource, RepositoryTarget


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
