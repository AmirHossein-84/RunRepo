"""Handler for database migration and client generation steps."""

from datetime import datetime, timezone
from pathlib import Path
from runrepo.executor.handlers.base import BaseStepHandler
from runrepo.executor.models import ExecutionStatus, StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep


class MigrationStepHandler(BaseStepHandler):
    """Handles RUN_DATABASE_MIGRATION and GENERATE_CLIENT steps."""

    def can_handle(self, step: PlanStep) -> bool:
        return step.action_type in (
            ActionType.RUN_DATABASE_MIGRATION,
            ActionType.GENERATE_CLIENT,
        )

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
            cmd_str = " ".join(step.command) if step.command else step.action_type.value
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.SUCCESS,
                command=step.command,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=started_at,
                duration_ms=0.0,
                stdout=f"[dry-run] Would execute: {cmd_str} in {working_dir}",
                exit_code=0,
                verification_passed=True,
            )

        if not step.command:
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.FAILED,
                command=None,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=started_at,
                duration_ms=0.0,
                stderr=f"No command specified for {step.action_type.value} step",
                exit_code=1,
                verification_passed=False,
            )

        res = executor.execute(step.command, cwd=working_dir)
        finished_at = datetime.now(timezone.utc)
        status = ExecutionStatus.SUCCESS if res.exit_code == 0 else ExecutionStatus.FAILED

        return StepExecutionResult(
            step_id=step.id,
            status=status,
            command=step.command,
            cwd=step.cwd,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=res.duration_ms,
            stdout=res.stdout,
            stderr=res.stderr,
            exit_code=res.exit_code,
            verification_passed=res.exit_code == 0,
        )
