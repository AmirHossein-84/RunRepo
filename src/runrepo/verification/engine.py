"""Unified VerificationEngine coordinating non-destructive outcome validation across all action types."""

from pathlib import Path
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import PlanStep
from runrepo.verification.models import VerificationResult, VerificationStatus, VerificationType
from runrepo.verification.verifiers import (
    BaseVerifier,
    DependencyVerifier,
    EnvVerifier,
    ExitCodeVerifier,
    FileVerifier,
    HttpVerifier,
    ProcessVerifier,
    ServiceVerifier,
)


class VerificationEngine:
    """Read-only verification engine confirming execution outcomes and operational readiness."""

    def __init__(self, verifiers: list[BaseVerifier] | None = None) -> None:
        self.verifiers = verifiers or [
            DependencyVerifier(),
            EnvVerifier(),
            ServiceVerifier(),
            ProcessVerifier(),
            HttpVerifier(),
            FileVerifier(),
            ExitCodeVerifier(),
        ]

    def verify_step(
        self,
        step: PlanStep,
        step_result: StepExecutionResult,
        repo_path: Path | None = None,
        executor: ProcessExecutor | None = None,
        process_manager: ProcessManager | None = None,
        dry_run: bool = False,
    ) -> VerificationResult:
        """Route step outcome to the most specific verifier."""
        # Find matching specialized verifier (excluding fallback ExitCodeVerifier initially)
        for verifier in self.verifiers:
            if not isinstance(verifier, ExitCodeVerifier) and verifier.can_verify(step):
                res = verifier.verify(
                    step=step,
                    step_result=step_result,
                    repo_path=repo_path,
                    executor=executor,
                    process_manager=process_manager,
                    dry_run=dry_run,
                )
                return res

        # Fallback to ExitCodeVerifier
        exit_code_verifier = next(
            (v for v in self.verifiers if isinstance(v, ExitCodeVerifier)),
            ExitCodeVerifier(),
        )
        return exit_code_verifier.verify(
            step=step,
            step_result=step_result,
            repo_path=repo_path,
            executor=executor,
            process_manager=process_manager,
            dry_run=dry_run,
        )
