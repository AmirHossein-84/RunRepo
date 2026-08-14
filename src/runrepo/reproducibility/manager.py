"""Central orchestrator for reproducibility config loading, lockfile creation, and drift checking."""

import platform
import subprocess
from pathlib import Path
from runrepo.environment.models import EnvironmentState
from runrepo.models import EnvVarCategory, ProjectInfo
from runrepo.planner.models import ActionType, ExecutionPlan
from runrepo.reproducibility.comparator import ReproducibilityComparator
from runrepo.reproducibility.config import ConfigLoader
from runrepo.reproducibility.lockfile import LockfileManager
from runrepo.reproducibility.models import (
    LockDiff,
    PlatformLockInfo,
    RepositoryLockInfo,
    ResolvedEnvLock,
    ResolvedServiceLock,
    ResolvedStartupLock,
    RunRepoConfig,
    RunRepoLock,
)


class ReproducibilityManager:
    """Coordinates runrepo.yaml configuration loading, runrepo.lock persistence, and drift analysis."""

    def __init__(self, repo_path: Path | str) -> None:
        self.repo_path = Path(repo_path).resolve()

    def load_config(self) -> RunRepoConfig | None:
        """Load and validate runrepo.yaml if present."""
        return ConfigLoader.load(self.repo_path)

    def load_lockfile(self) -> RunRepoLock | None:
        """Load and validate runrepo.lock if present."""
        return LockfileManager.load(self.repo_path)

    def check_drift(
        self,
        project_info: ProjectInfo,
        environment_state: EnvironmentState | None,
        execution_plan: ExecutionPlan | None,
    ) -> LockDiff | None:
        """Check for drift against existing lockfile if one is present."""
        lock = self.load_lockfile()
        if lock is None:
            return None
        return ReproducibilityComparator.compare(
            project_info=project_info,
            environment_state=environment_state,
            execution_plan=execution_plan,
            lock=lock,
        )

    def get_git_info(self) -> tuple[str | None, str | None, str | None]:
        """Inspect git commit, branch, and remote if inside a git repository."""
        commit_hash = None
        branch_ref = None
        remote_url = None

        git_dir = self.repo_path / ".git"
        if git_dir.exists():
            try:
                out = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if out.returncode == 0:
                    commit_hash = out.stdout.strip()
            except Exception:
                pass

            try:
                out = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if out.returncode == 0:
                    branch_ref = out.stdout.strip()
            except Exception:
                pass

            try:
                out = subprocess.run(
                    ["git", "config", "--get", "remote.origin.url"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if out.returncode == 0:
                    remote_url = out.stdout.strip()
            except Exception:
                pass

        return commit_hash, branch_ref, remote_url

    def generate_lockfile(
        self,
        project_info: ProjectInfo,
        environment_state: EnvironmentState,
        plan: ExecutionPlan,
    ) -> RunRepoLock:
        """Generate and save a deterministic runrepo.lock from resolved execution facts."""
        commit_hash, branch_ref, remote_url = self.get_git_info()

        repo_lock = RepositoryLockInfo(
            name=project_info.name,
            remote_url=remote_url,
            commit_hash=commit_hash,
            ref=branch_ref,
        )

        plat_lock = PlatformLockInfo(
            os=platform.system().lower(),
            arch=platform.machine().lower(),
        )

        resolved_runtimes: dict[str, str] = {}
        for check in environment_state.checks:
            clean_name = check.name.lower().split()[0]
            if check.installed_version:
                resolved_runtimes[clean_name] = check.installed_version

        resolved_pm = (
            project_info.package_managers[0].name if project_info.package_managers else None
        )

        # Extract resolved services from plan
        resolved_services: list[ResolvedServiceLock] = []
        for step in plan.steps:
            if step.action_type == ActionType.START_SERVICE:
                svc_name = step.id.replace("service-", "").replace("compose-", "")
                resolved_services.append(
                    ResolvedServiceLock(
                        name=svc_name,
                        image=None,
                        port=None,
                    )
                )

        # Extract environment metadata (STRICTLY NO VALUES)
        resolved_env: list[ResolvedEnvLock] = []
        for env_var in project_info.environment_variables:
            src = "generated" if env_var.category == EnvVarCategory.LOCAL_DEFAULT else "user_required"
            is_sec = env_var.category == EnvVarCategory.SECRET
            resolved_env.append(
                ResolvedEnvLock(
                    name=env_var.name,
                    category=env_var.category.value,
                    source=src,
                    is_secret=is_sec,
                )
            )

        # Extract startup command from plan
        startup_cmd: list[str] = []
        for step in plan.steps:
            if step.action_type == ActionType.START_APPLICATION and step.command:
                startup_cmd = step.command
                break

        if not startup_cmd and project_info.scripts:
            startup_cmd = project_info.scripts[0].command.split()

        resolved_startup = ResolvedStartupLock(
            command=startup_cmd,
            working_dir=None,
        )

        lock = RunRepoLock(
            repository=repo_lock,
            platform=plat_lock,
            resolved_runtimes=resolved_runtimes,
            resolved_package_manager=resolved_pm,
            resolved_services=resolved_services,
            resolved_environment=resolved_env,
            resolved_startup=resolved_startup,
            plan_steps=[s.id for s in plan.steps],
        )

        LockfileManager.save(self.repo_path, lock)
        return lock
