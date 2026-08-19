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

        # Set VIRTUAL_ENV if a local virtual environment exists
        venv_path = working_dir / ".venv"
        if not venv_path.exists() and (repo_path / ".venv").exists():
            venv_path = repo_path / ".venv"

        custom_env = {}
        if venv_path.exists():
            custom_env["VIRTUAL_ENV"] = str(venv_path)

        res = executor.execute(step.command, cwd=working_dir, env=custom_env if custom_env else None, timeout_s=600.0)

        # 1. Fallback for uv pip parser error (e.g. strict TOML parse or duplicate extra normalization in pyproject.toml)
        err_combined = f"{res.stdout or ''}\n{res.stderr or ''}"
        if res.exit_code != 0 and "uv" in step.command and any(err in err_combined for err in ("Failed to parse", "duplicate normalized extra", "TOML parse error")):
            import sys
            venv_py = venv_path / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            if venv_path.exists():
                # Ensure seed packages (pip) are available inside the virtualenv
                executor.execute(["uv", "venv", "--seed", "--clear", str(venv_path)], cwd=working_dir)
            if venv_py.exists():
                fallback_cmd = [str(venv_py), "-m", "pip", "install"]
                if "install" in step.command:
                    idx = step.command.index("install")
                    fallback_cmd.extend(step.command[idx + 1:])
                res = executor.execute(fallback_cmd, cwd=working_dir)

        # 2. Fallback for npm peer dependency resolution conflicts (ERESOLVE) & devEngines mismatch (EBADDEVENGINES)
        err_combined = f"{res.stdout or ''}\n{res.stderr or ''}"
        if res.exit_code != 0 and any(err in err_combined for err in ("ERESOLVE", "EBADDEVENGINES", "EBADENGINE", "Unsupported engine")):
            fallback_flags = []
            if "ERESOLVE" in err_combined:
                fallback_flags.append("--legacy-peer-deps")
            if any(err in err_combined for err in ("EBADDEVENGINES", "EBADENGINE", "Unsupported engine")):
                fallback_flags.append("--ignore-engines")
            fallback_cmd = list(step.command) + fallback_flags
            res = executor.execute(fallback_cmd, cwd=working_dir)

        # 3. Fallback for broken postinstall/lifecycle scripts (e.g. opencollective crashing libuv, Turbo recursive stack overflow)
        err_combined = f"{res.stdout or ''}\n{res.stderr or ''}"
        if res.exit_code != 0 and any(err in err_combined for err in ("Assertion failed", "postinstall", "post-install", "3221226505", "UV_HANDLE_CLOSING", "Maximum call stack size exceeded", "command finished with error: command")):
            fallback_flags = ["--ignore-scripts"]
            if "ERESOLVE" in err_combined:
                fallback_flags.append("--legacy-peer-deps")
            if any(err in err_combined for err in ("EBADDEVENGINES", "EBADENGINE", "Unsupported engine")):
                fallback_flags.append("--ignore-engines")
            fallback_cmd = list(step.command) + fallback_flags
            res = executor.execute(fallback_cmd, cwd=working_dir)

        # 4. Retry on transient network resets/timeouts
        if res.exit_code != 0:
            err_combined_lower = f"{res.stdout or ''}\n{res.stderr or ''}".lower()
            if any(net_err in err_combined_lower for net_err in ("econnreset", "etimedout", "socket hang up", "fetch failed", "connection reset", "network error")):
                res = executor.execute(step.command, cwd=working_dir)

        # 5. Fallback for C-extension build failures on Windows without MSVC (recreate venv with Python 3.12 where pre-built binary wheels exist)
        err_combined = f"{res.stdout or ''}\n{res.stderr or ''}"
        if res.exit_code != 0 and "uv" in step.command and any(err in err_combined for err in ("Microsoft Visual C++", "Failed to build", "error: command 'cl.exe' failed", "Building wheel for")):
            if venv_path.exists():
                recreate_res = executor.execute(["uv", "venv", "--python", "3.12", "--clear", str(venv_path)], cwd=working_dir)
                if recreate_res.exit_code == 0:
                    res = executor.execute(step.command, cwd=working_dir, env=custom_env if custom_env else None, timeout_s=600.0)

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
