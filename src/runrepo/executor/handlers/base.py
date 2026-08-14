"""Base StepHandler interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import PlanStep


class BaseStepHandler(ABC):
    """Abstract interface for dedicated plan step handlers."""

    @abstractmethod
    def can_handle(self, step: PlanStep) -> bool:
        """Check if this handler can process the given step."""
        ...

    @abstractmethod
    def execute(
        self,
        step: PlanStep,
        repo_path: Path,
        executor: ProcessExecutor,
        process_manager: ProcessManager,
        dry_run: bool = False,
    ) -> StepExecutionResult:
        """Execute the plan step and return structured telemetry and results."""
        ...
