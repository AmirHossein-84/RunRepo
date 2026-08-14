"""BaseVerifier interface for specialized verification strategies."""

from abc import ABC, abstractmethod
from pathlib import Path
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import PlanStep
from runrepo.verification.models import VerificationResult


class BaseVerifier(ABC):
    """Abstract interface for dedicated outcome verifiers."""

    @abstractmethod
    def can_verify(self, step: PlanStep) -> bool:
        """Check if this verifier is responsible for the given plan step."""
        ...

    @abstractmethod
    def verify(
        self,
        step: PlanStep,
        step_result: StepExecutionResult,
        repo_path: Path | None = None,
        executor: ProcessExecutor | None = None,
        process_manager: ProcessManager | None = None,
        dry_run: bool = False,
    ) -> VerificationResult:
        """Perform non-destructive, read-only verification of step outcome."""
        ...
