"""Git operations wrapper for safe, deterministic repository cloning and validation."""

import os
import re
import shutil
import stat
import time
from pathlib import Path
from runrepo.executor.process import ProcessExecutor, SystemProcessExecutor
from runrepo.repository.models import CloneStatus, PullRequestTarget, RepositoryResult, RepositorySource, RepositoryTarget


def _safe_rmtree(path: Path) -> None:
    """Safely delete directory trees, handling Windows read-only git file locks."""
    def _onerror(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass

    if path.exists():
        try:
            shutil.rmtree(path, onerror=_onerror)
        except Exception:
            pass


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
            _safe_rmtree(destination)

        destination.parent.mkdir(parents=True, exist_ok=True)

        cmd = ["git", "-c", "core.longpaths=true", "clone"]
        if depth and depth > 0:
            cmd.extend(["--depth", str(depth)])
        if target.branch:
            cmd.extend(["--branch", target.branch])

        cmd.extend([target.clone_url, str(destination)])

        git_env = {"GIT_TERMINAL_PROMPT": "0"}
        max_attempts = 3
        exec_res = None
        sanitized_output = ""

        for attempt in range(1, max_attempts + 1):
            if destination.exists():
                _safe_rmtree(destination)

            try:
                exec_res = self.executor.execute(cmd, cwd=destination.parent, env=git_env, timeout_s=300.0)
            except Exception as e:
                if destination.exists():
                    _safe_rmtree(destination)
                if attempt == max_attempts:
                    return RepositoryResult(
                        success=False,
                        target=target,
                        error_message=f"Failed to execute git clone: {e}",
                    )
                time.sleep(1.5 * attempt)
                continue

            combined_output = f"{exec_res.stdout}\n{exec_res.stderr}".strip()
            sanitized_output = self.sanitize_git_output(combined_output) or ""

            if exec_res.exit_code == 0:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
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

            # Check if failure is transient network error
            err_lower = sanitized_output.lower()
            is_transient = any(
                p in err_lower
                for p in (
                    "could not connect to server",
                    "connection reset",
                    "timed out",
                    "early eof",
                    "rpc failed",
                    "the remote end hung up unexpectedly",
                    "could not resolve host",
                    "failed to connect",
                )
            )
            if is_transient and attempt < max_attempts:
                time.sleep(2.0 * attempt)
                continue
            else:
                break

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        # Clone failed - clean up partial artifacts to avoid corrupted states
        if destination.exists():
            _safe_rmtree(destination)

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

    def clone_pull_request(
        self,
        pr_target: PullRequestTarget,
        destination: Path,
    ) -> RepositoryResult:
        """Clone and checkout a specific GitHub Pull Request ref into destination."""
        start_time = time.perf_counter()
        target_model = RepositoryTarget(
            source=RepositorySource.GITHUB_PR,
            raw_input=pr_target.raw_input,
            owner=pr_target.owner,
            name=pr_target.repo,
            branch=f"pr-{pr_target.pr_number}",
            clone_url=pr_target.clone_url,
        )

        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)

        destination.parent.mkdir(parents=True, exist_ok=True)

        # 1. Initialize repo
        init_res = self.executor.execute(["git", "-c", "core.longpaths=true", "init", str(destination)], cwd=destination.parent)
        if init_res.exit_code != 0:
            return RepositoryResult(
                success=False,
                target=target_model,
                error_message=f"Failed to initialize git repository: {init_res.stderr}",
            )
        self.executor.execute(["git", "-C", str(destination), "config", "core.longpaths", "true"])

        # 2. Add remote
        remote_res = self.executor.execute(
            ["git", "-C", str(destination), "remote", "add", "origin", pr_target.clone_url]
        )
        if remote_res.exit_code != 0:
            shutil.rmtree(destination, ignore_errors=True)
            return RepositoryResult(
                success=False,
                target=target_model,
                error_message=f"Failed to add git remote: {remote_res.stderr}",
            )

        # 3. Fetch PR ref: refs/pull/<id>/head:pr-<id>
        fetch_ref = f"refs/pull/{pr_target.pr_number}/head:pr-{pr_target.pr_number}"
        fetch_res = self.executor.execute(
            ["git", "-C", str(destination), "fetch", "--depth=1", "origin", fetch_ref]
        )
        if fetch_res.exit_code != 0:
            shutil.rmtree(destination, ignore_errors=True)
            return RepositoryResult(
                success=False,
                target=target_model,
                error_message=f"Failed to fetch PR ref '{fetch_ref}': {fetch_res.stderr}",
            )

        # 4. Checkout PR branch
        checkout_res = self.executor.execute(
            ["git", "-C", str(destination), "checkout", f"pr-{pr_target.pr_number}"]
        )
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        if checkout_res.exit_code != 0:
            shutil.rmtree(destination, ignore_errors=True)
            return RepositoryResult(
                success=False,
                target=target_model,
                error_message=f"Failed to checkout PR branch 'pr-{pr_target.pr_number}': {checkout_res.stderr}",
            )

        target_model.status = CloneStatus.CLONED
        target_model.local_path = destination
        return RepositoryResult(
            success=True,
            target=target_model,
            local_path=destination,
            exit_code=0,
            duration_ms=duration_ms,
        )
