"""Strict deterministic environment reproducer executing from runrepo.lock or runrepo.yaml."""

from pathlib import Path
from runrepo.analyzer import RepositoryAnalyzer
from runrepo.environment.checker import EnvironmentChecker
from runrepo.executor import ExecutionEngine
from runrepo.executor.confirmation import AutoConfirmationHandler
from runrepo.executor.models import ExecutionResult
from runrepo.executor.process import ProcessExecutor, SystemProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner import ExecutionPlanner
from runrepo.reproducibility import ReproducibilityComparator, ReproducibilityManager
from runrepo.reproducibility.config import RunRepoConfig


class EnvironmentReproducer:
    """Recreates verified environments from locked specifications."""

    def __init__(self, executor: ProcessExecutor | None = None) -> None:
        self.executor = executor or SystemProcessExecutor()
        self.analyzer = RepositoryAnalyzer()
        self.planner = ExecutionPlanner()

    def reproduce(
        self,
        repo_path: Path,
        lock_path: Path | None = None,
        dry_run: bool = False,
    ) -> tuple[bool, ExecutionResult | None, list[str]]:
        """Recreate the project environment matching the lockfile or config."""
        warnings: list[str] = []
        mgr = ReproducibilityManager(repo_path)
        lock = None
        if lock_path and lock_path.exists():
            lock = ReproducibilityManager(lock_path.parent).load_lockfile()
        elif (repo_path / "runrepo.lock").exists():
            lock = mgr.load_lockfile()

        project_info = self.analyzer.analyze(repo_path)
        checker = EnvironmentChecker()
        env_state = checker.check_environment(project_info)

        config = mgr.load_config()
        plan = self.planner.plan(project_info, env_state, config=config)

        # Check for drift against locked specifications
        if lock:
            diff = mgr.check_drift(project_info, env_state, plan)
            if diff and diff.has_changes:
                for w in diff.warnings:
                    warnings.append(f"Lockfile drift detected: {w}")

        pm = ProcessManager(state_dir=repo_path / ".runrepo_state")
        engine = ExecutionEngine(
            executor=self.executor,
            confirmation=AutoConfirmationHandler(),
            process_manager=pm,
        )

        result = engine.execute(plan, dry_run=dry_run)
        success = result.status.value == "SUCCESS"
        return success, result, warnings
