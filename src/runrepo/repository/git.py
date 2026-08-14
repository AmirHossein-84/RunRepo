"""Git operations wrapper for safe, deterministic repository cloning and validation."""

import re
import shutil
import time
from pathlib import Path
from runrepo.executor.process import ProcessExecutor, SystemProcessExecutor
from runrepo.repository.models import CloneStatus, RepositoryResult, RepositoryTarget


class GitManager:
    """Safely executes git operations using RunRepo's ProcessExecutor architecture."""

    def __init__(self, executor: ProcessExecutor | None = None) -> None:
        self.executor = executor or SystemProcessExecutor()

    @classmethod
    def sanitize_git_output(cls, text: str | None) -> str | None:
        """Sanitize passwords, bearer tokens, or personal access tokens from git output."""
        if not text:
            return None

        # Mask embedded URL credentials: https://token@github.com or https://user:pass@github.com
        sanitized = re.sub(
            r"(https?://)([^:@\s]+(?::[^@\s]+)?)(@github\.com)",
            r"\1******\3",
            text,
        )
        # Mask GitHub PAT tokens (ghp_..., github_pat_...)
        sanitized = re.sub(
            r"(ghp_[A-Za-z0-9_]{36}|github_pat_[A-Za-z0-9_]{82})",
            "ghp_******",
            sanitized,
        )
        return sanitized

    def verify_git_installed(self) -> bool:
        """Check if git CLI is available and functional."""
        try:
            res = self.executor.execute(["git", "--version"])
            return res.exit_code == 0
        except Exception:
            return False

    def verify_repository_valid(self, path: Path) -> bool:
        """Verify that a path contains a valid, uncorrupted git repository."""
        if not path.exists() or not path.is_dir():
            return False

        git_dir = path / ".git"
        if not git_dir.exists():
            return False

        try:
            res = self.executor.execute(["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"])
            return res.exit_code == 0 and "true" in res.stdout.lower()
        except Exception:
            return False

    def clone(
        self,
        target: RepositoryTarget,
        destination: Path,
        depth: int | None = 1,
    ) -> RepositoryResult:
        """Clone a remote repository into the destination directory."""
        if not target.clone_url:
            return RepositoryResult(
                success=False,
                target=target,
                error_message="Missing clone URL on target repository.",
            )

        start_time = time.perf_counter()

        # Clean destination if incomplete directory exists
        if destination.exists() and not self.verify_repository_valid(destination):
            shutil.rmtree(destination, ignore_errors=True)

        destination.parent.mkdir(parents=True, exist_ok=True)

        cmd = ["git", "clone"]
        if depth and depth > 0:
            cmd.extend(["--depth", str(depth)])
        if target.branch:
            cmd.extend(["--branch", target.branch])

        cmd.extend([target.clone_url, str(destination)])

        try:
            exec_res = self.executor.execute(cmd, cwd=destination.parent)
        except Exception as e:
            if destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            return RepositoryResult(
                success=False,
                target=target,
                error_message=f"Failed to execute git clone: {e}",
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        combined_output = f"{exec_res.stdout}\n{exec_res.stderr}".strip()
        sanitized_output = self.sanitize_git_output(combined_output)

        if exec_res.exit_code == 0:
            target.status = CloneStatus.CLONED
            target.local_path = destination
            return RepositoryResult(
                success=True,
                target=target,
                local_path=destination,
                git_output=sanitized_output,
                exit_code=0,
                duration_ms=duration_ms,
            )

        # Clone failed - clean up partial artifacts to avoid corrupted states
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)

        target.status = CloneStatus.FAILED
        err_lower = (sanitized_output or "").lower()

        # Check for authentication or private repo errors
        if any(p in err_lower for p in ("authentication failed", "could not read username", "repository not found", "403", "401")):
            error_message = (
                f"Authentication failed for repository '{target.owner}/{target.name}'. "
                f"The repository may be private or deleted. Ensure your Git credentials or SSH keys are configured."
            )
        elif "remote branch" in err_lower and "not found" in err_lower:
            error_message = f"Branch or tag '{target.branch}' not found in repository '{target.owner}/{target.name}'."
        else:
            error_message = f"git clone failed with exit code {exec_res.exit_code}: {sanitized_output or 'Unknown git error'}"

        return RepositoryResult(
            success=False,
            target=target,
            error_message=error_message,
            git_output=sanitized_output,
            exit_code=exec_res.exit_code,
            duration_ms=duration_ms,
        )
