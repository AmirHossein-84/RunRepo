"""Post-execution verification layer adapter for backward compatibility."""

from pathlib import Path
from runrepo.executor.models import StepExecutionResult
from runrepo.planner.models import PlanStep
from runrepo.verification.engine import VerificationEngine
from runrepo.verification.models import VerificationStatus


class StepVerifier:
    """Verifies that executed plan steps achieved their expected outcome (delegating to VerificationEngine)."""

    _engine = VerificationEngine()

    @classmethod
    def verify(
        cls,
        step: PlanStep,
        step_result: StepExecutionResult,
        repo_path: Path | None = None,
    ) -> tuple[bool, str]:
        """Perform deterministic verification for an executed step."""
        res = cls._engine.verify_step(step, step_result, repo_path=repo_path)
        return (res.status == VerificationStatus.PASSED, res.message)
