"""Handler for environment configuration steps."""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from runrepo.executor.handlers.base import BaseStepHandler
from runrepo.executor.models import ExecutionStatus, StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep


class EnvConfigStepHandler(BaseStepHandler):
    """Handles CONFIGURE_ENV steps (e.g. copying .env.example -> .env)."""

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
        target_env = working_dir / ".env"

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

        if target_env.exists():
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.SUCCESS,
                command=None,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=started_at,
                duration_ms=0.0,
                stdout=".env file already exists",
                exit_code=0,
                verification_passed=True,
            )

        # Look for templates
        template_names = [".env.example", ".env.template", ".env.sample", ".env.local.example"]
        source_template: Path | None = None
        for name in template_names:
            candidate = working_dir / name
            if candidate.exists():
                source_template = candidate
                break

        if source_template:
            try:
                shutil.copy2(source_template, target_env)
                finished_at = datetime.now(timezone.utc)
                return StepExecutionResult(
                    step_id=step.id,
                    status=ExecutionStatus.SUCCESS,
                    command=None,
                    cwd=step.cwd,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=5.0,
                    stdout=f"Created .env from {source_template.name}",
                    exit_code=0,
                    verification_passed=True,
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
                    stderr=f"Failed to copy template to .env: {exc}",
                    exit_code=1,
                    error=str(exc),
                    verification_passed=False,
                )

        # No template found, create empty or note
        try:
            target_env.write_text("# Created by RunRepo\n", encoding="utf-8")
            finished_at = datetime.now(timezone.utc)
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.SUCCESS,
                command=None,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=2.0,
                stdout="Initialized empty .env file",
                exit_code=0,
                verification_passed=True,
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
                duration_ms=2.0,
                stderr=f"Failed to initialize .env: {exc}",
                exit_code=1,
                error=str(exc),
                verification_passed=False,
            )
