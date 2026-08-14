"""Generic lightweight verifiers for file existence and command exit codes."""

import time
from pathlib import Path
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import PlanStep
from runrepo.verification.models import VerificationResult, VerificationStatus, VerificationType
from runrepo.verification.verifiers.base import BaseVerifier


class FileVerifier(BaseVerifier):
    """Verifies that a required file or directory was generated."""

    def can_verify(self, step: PlanStep) -> bool:
        return step.verification is not None and step.verification.strategy == "file_exists"

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
        target = step.verification.target if step.verification else None

        if dry_run:
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.FILE_CHECK,
                status=VerificationStatus.PASSED,
                target=target,
                message=f"[dry-run] File presence verified ({target})",
                duration_ms=0.0,
            )

        if not target:
            passed = step_result.exit_code == 0
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.FILE_CHECK,
                status=VerificationStatus.PASSED if passed else VerificationStatus.FAILED,
                message="Exit code 0 confirmed",
                duration_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        file_path = (working_dir / target).resolve()
        exists = file_path.exists()
        elapsed = (time.perf_counter() - start_time) * 1000.0

        if exists:
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.FILE_CHECK,
                status=VerificationStatus.PASSED,
                target=str(file_path),
                message=f"Target exists: {file_path.name}",
                details={"file_path": str(file_path)},
                duration_ms=elapsed,
            )
        else:
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.FILE_CHECK,
                status=VerificationStatus.FAILED,
                target=str(file_path),
                message=f"Expected target does not exist: {file_path}",
                failure_reason="Required file or directory missing",
                duration_ms=elapsed,
            )


class ExitCodeVerifier(BaseVerifier):
    """Fallback verifier confirming command completed with exit code 0."""

    def can_verify(self, step: PlanStep) -> bool:
        return True  # Fallback verifier

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
        passed = step_result.exit_code == 0
        elapsed = (time.perf_counter() - start_time) * 1000.0

        status = VerificationStatus.PASSED if passed else VerificationStatus.FAILED
        msg = (
            f"Command exited cleanly (code 0)"
            if passed
            else f"Command failed with exit code {step_result.exit_code}"
        )

        return VerificationResult(
            step_id=step.id,
            verification_type=VerificationType.EXIT_CODE_CHECK,
            status=status,
            target="exit_code",
            message=msg,
            duration_ms=elapsed,
            failure_reason=None if passed else "Process exited with non-zero status",
            diagnostic_data={"exit_code": step_result.exit_code, "stderr": step_result.stderr},
        )
