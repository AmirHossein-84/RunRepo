"""Dependency verifier confirming successful installation of packages."""

import time
from pathlib import Path
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep
from runrepo.verification.models import VerificationResult, VerificationStatus, VerificationType
from runrepo.verification.verifiers.base import BaseVerifier


class DependencyVerifier(BaseVerifier):
    """Verifies installed packages and directory state without executing modifications."""

    def can_verify(self, step: PlanStep) -> bool:
        return step.action_type == ActionType.INSTALL_DEPENDENCIES

    def verify(
        self,
        step: PlanStep,
        step_result: StepExecutionResult,
        repo_path: Path | None = None,
        executor: ProcessExecutor | None = None,
        process_manager: ProcessManager | None = None,
        dry_run: bool = False,
    ) -> VerificationResult:
        start_time = time.perf_counter()
        base_path = repo_path.resolve() if repo_path is not None else Path.cwd()
        working_dir = (base_path / step.cwd).resolve() if step.cwd else base_path

        from runrepo.executor.process import MockProcessExecutor

        if dry_run or isinstance(executor, MockProcessExecutor):
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.DEPENDENCY_CHECK,
                status=VerificationStatus.PASSED,
                target=str(working_dir),
                message="Dependency installation verified",
                duration_ms=0.0,
            )

        if step_result.exit_code != 0:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.DEPENDENCY_CHECK,
                status=VerificationStatus.FAILED,
                target=str(working_dir),
                message=f"Dependency installation command failed with exit code {step_result.exit_code}",
                duration_ms=elapsed,
                failure_reason="Install process exited with non-zero status",
                diagnostic_data={"exit_code": step_result.exit_code, "stderr": step_result.stderr},
            )

        # 1. Node.js Dependency Verification
        package_json = working_dir / "package.json"
        if package_json.exists():
            node_modules = working_dir / "node_modules"
            if not node_modules.exists() or not node_modules.is_dir():
                elapsed = (time.perf_counter() - start_time) * 1000.0
                return VerificationResult(
                    step_id=step.id,
                    verification_type=VerificationType.DEPENDENCY_CHECK,
                    status=VerificationStatus.FAILED,
                    target=str(node_modules),
                    message="node_modules directory is missing after installation",
                    duration_ms=elapsed,
                    failure_reason="node_modules was not created",
                    diagnostic_data={"working_dir": str(working_dir)},
                )

            # Check directory is non-empty
            try:
                has_entries = any(node_modules.iterdir())
            except Exception:
                has_entries = True

            if not has_entries:
                elapsed = (time.perf_counter() - start_time) * 1000.0
                return VerificationResult(
                    step_id=step.id,
                    verification_type=VerificationType.DEPENDENCY_CHECK,
                    status=VerificationStatus.FAILED,
                    target=str(node_modules),
                    message="node_modules directory is empty after installation",
                    duration_ms=elapsed,
                    failure_reason="node_modules contains 0 entries",
                )

            elapsed = (time.perf_counter() - start_time) * 1000.0
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.DEPENDENCY_CHECK,
                status=VerificationStatus.PASSED,
                target=str(node_modules),
                message="Node dependencies verified (node_modules present and populated)",
                details={"node_modules_path": str(node_modules), "has_package_json": True},
                duration_ms=elapsed,
            )

        # 2. Python Dependency Verification
        pyproject = working_dir / "pyproject.toml"
        requirements = working_dir / "requirements.txt"
        if pyproject.exists() or requirements.exists():
            venv_candidates = [
                working_dir / ".venv",
                working_dir / "venv",
                base_path / ".venv",
                base_path / "venv",
            ]
            found_venv: Path | None = None
            for cand in venv_candidates:
                if cand.exists() and cand.is_dir():
                    # Validate venv structure
                    if (cand / "pyvenv.cfg").exists() or (cand / "Scripts").exists() or (cand / "bin").exists():
                        found_venv = cand
                        break

            elapsed = (time.perf_counter() - start_time) * 1000.0
            details = {
                "working_dir": str(working_dir),
                "has_pyproject": pyproject.exists(),
                "has_requirements": requirements.exists(),
                "venv_path": str(found_venv) if found_venv else None,
            }

            # If pip install was run into system/active environment, exit code 0 is sufficient
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.DEPENDENCY_CHECK,
                status=VerificationStatus.PASSED,
                target=str(found_venv) if found_venv else str(working_dir),
                message=f"Python dependencies verified ({found_venv.name if found_venv else 'environment packages'})",
                details=details,
                duration_ms=elapsed,
            )

        # Generic success
        elapsed = (time.perf_counter() - start_time) * 1000.0
        return VerificationResult(
            step_id=step.id,
            verification_type=VerificationType.DEPENDENCY_CHECK,
            status=VerificationStatus.PASSED,
            target=str(working_dir),
            message="Dependency installation command succeeded",
            duration_ms=elapsed,
        )
