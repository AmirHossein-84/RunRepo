"""Handler for runtime and package manager verification steps."""

from datetime import datetime, timezone
from pathlib import Path
from runrepo.executor.handlers.base import BaseStepHandler
from runrepo.executor.models import ExecutionStatus, StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep


class VerifyStepHandler(BaseStepHandler):
    """Handles VERIFY_RUNTIME and VERIFY_PACKAGE_MANAGER plan steps."""

    def can_handle(self, step: PlanStep) -> bool:
        return step.action_type in (
            ActionType.VERIFY_RUNTIME,
            ActionType.VERIFY_PACKAGE_MANAGER,
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

        if dry_run:
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.SUCCESS,
                command=step.command,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=started_at,
                duration_ms=0.0,
                stdout="[dry-run] Runtime/package manager requirement verified",
                exit_code=0,
                verification_passed=True,
            )

        if step.is_satisfied:
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.SUCCESS,
                command=step.command,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=started_at,
                duration_ms=0.0,
                stdout=step.reason,
                exit_code=0,
                verification_passed=True,
            )

        if not step.command:
            # Missing without command
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.FAILED if step.is_blocked else ExecutionStatus.SUCCESS,
                command=None,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=started_at,
                duration_ms=0.0,
                stderr=step.reason,
                exit_code=1 if step.is_blocked else 0,
                verification_passed=not step.is_blocked,
            )

        working_dir = (repo_path / step.cwd).resolve() if step.cwd else repo_path.resolve()
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
