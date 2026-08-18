"""Handler for dependency installation steps."""

from datetime import datetime, timezone
from pathlib import Path
from runrepo.executor.handlers.base import BaseStepHandler
from runrepo.executor.models import ExecutionStatus, StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep


class InstallDepsStepHandler(BaseStepHandler):
    """Handles INSTALL_DEPENDENCIES steps (e.g. npm install, pnpm install, uv sync)."""

    def can_handle(self, step: PlanStep) -> bool:
        return step.action_type == ActionType.INSTALL_DEPENDENCIES

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
            cmd_str = " ".join(step.command) if step.command else "install dependencies"
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
                stderr="No install command specified for dependency step",
                exit_code=1,
                verification_passed=False,
            )

        res = executor.execute(step.command, cwd=working_dir)
        # 1. Fallback for npm peer dependency resolution conflicts (ERESOLVE)
        if res.exit_code != 0 and "ERESOLVE" in (res.stderr or ""):
            fallback_cmd = list(step.command) + ["--legacy-peer-deps"]
            res = executor.execute(fallback_cmd, cwd=working_dir)

        # 2. Fallback for broken postinstall/lifecycle scripts (e.g. opencollective crashing libuv on Windows)
        if res.exit_code != 0 and any(err in (res.stderr or "") for err in ("Assertion failed", "postinstall", "3221226505", "UV_HANDLE_CLOSING")):
            fallback_flags = ["--ignore-scripts"]
            if "ERESOLVE" in (res.stderr or ""):
                fallback_flags.append("--legacy-peer-deps")
            fallback_cmd = list(step.command) + fallback_flags
            res = executor.execute(fallback_cmd, cwd=working_dir)

        # 3. Retry on transient network resets/timeouts
        if res.exit_code != 0:
            err_combined = f"{res.stdout or ''}\n{res.stderr or ''}".lower()
            if any(net_err in err_combined for net_err in ("econnreset", "etimedout", "socket hang up", "fetch failed", "connection reset", "network error")):
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
            rollback_available=step.rollback is not None,
        )
