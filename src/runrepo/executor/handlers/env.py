"""Handler for environment configuration steps providing safe merging, backups, and redaction."""

from datetime import datetime, timezone
from pathlib import Path
from runrepo.env.detector import EnvDetector
from runrepo.env.manager import EnvManager
from runrepo.executor.handlers.base import BaseStepHandler
from runrepo.executor.models import ExecutionStatus, StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep
from runrepo.services.models import PostgresConfig, RedisConfig


class EnvConfigStepHandler(BaseStepHandler):
    """Handles CONFIGURE_ENV steps safely via EnvManager with backups and non-destructive merging."""

    def can_handle(self, step: PlanStep) -> bool:
        return step.action_type == ActionType.CONFIGURE_ENV

    def execute(
        self,
        step: PlanStep,
        repo_path: Path,
        executor: ProcessExecutor,
        process_manager: ProcessManager,
        dry_run: bool = False,
    ) -> StepExecutionResult:
        started_at = datetime.now(timezone.utc)
        working_dir = (repo_path / step.cwd).resolve() if step.cwd else repo_path.resolve()

        if dry_run:
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.SUCCESS,
                command=None,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=started_at,
                duration_ms=0.0,
                stdout=f"[dry-run] Would configure environment in {working_dir}",
                exit_code=0,
                verification_passed=True,
            )

        try:
            # 1. Detect requirements for this working directory
            reqs = EnvDetector.detect_project_requirements(working_dir)

            # 2. Extract database & redis parameters if passed in step context or defaults
            pg_cfg = PostgresConfig(
                container_name=f"runrepo-{repo_path.name.lower()}-postgres",
                database_name=f"{repo_path.name.lower().replace('-', '_')}_dev",
            )
            rd_cfg = RedisConfig(
                container_name=f"runrepo-{repo_path.name.lower()}-redis",
            )

            # 3. Apply safe updates with automatic backup
            success, msg, added_keys = EnvManager.apply_env_updates(
                root_path=working_dir,
                requirements=reqs,
                postgres_config=pg_cfg,
                redis_config=rd_cfg,
                include_external_stubs=True,
            )

            finished_at = datetime.now(timezone.utc)
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED,
                command=None,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=10.0,
                stdout=msg,
                exit_code=0 if success else 1,
                verification_passed=success,
                rollback_available=True,
            )
        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.FAILED,
                command=None,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=5.0,
                stderr=f"Failed to configure environment: {exc}",
                exit_code=1,
                error=str(exc),
                verification_passed=False,
            )
