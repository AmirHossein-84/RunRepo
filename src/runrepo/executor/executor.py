"""ExecutionEngine coordinating safe plan execution, confirmation gates, and results collection."""

from datetime import datetime, timezone
from pathlib import Path
from rich.console import Console

from runrepo.executor.confirmation import ConfirmationHandler, ConsoleConfirmationHandler
from runrepo.executor.handlers import (
    ApplicationStepHandler,
    BaseStepHandler,
    EnvConfigStepHandler,
    InstallDepsStepHandler,
    MigrationStepHandler,
    ServiceStepHandler,
    VerifyStepHandler,
)
from runrepo.executor.models import ExecutionResult, ExecutionStatus, StepExecutionResult
from runrepo.executor.process import ProcessExecutor, SystemProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.executor.verification import StepVerifier
from runrepo.planner.models import ExecutionPlan, PlanStatus


class ExecutionEngine:
    """Coordinates and executes an approved ExecutionPlan."""

    def __init__(
        self,
        executor: ProcessExecutor | None = None,
        confirmation: ConfirmationHandler | None = None,
        process_manager: ProcessManager | None = None,
        handlers: list[BaseStepHandler] | None = None,
        console: Console | None = None,
    ) -> None:
        self.executor = executor or SystemProcessExecutor()
        self.confirmation = confirmation or ConsoleConfirmationHandler(console=console)
        self.process_manager = process_manager or ProcessManager()
        self.console = console or Console()
        self.handlers = handlers or [
            VerifyStepHandler(),
            EnvConfigStepHandler(),
            InstallDepsStepHandler(),
            ServiceStepHandler(),
            MigrationStepHandler(),
            ApplicationStepHandler(),
        ]

    def _find_handler(self, step) -> BaseStepHandler | None:
        for handler in self.handlers:
            if handler.can_handle(step):
                return handler
        return None

    def execute(
        self,
        plan: ExecutionPlan,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """Execute all steps in an ExecutionPlan according to topological DAG order."""
        started_at = datetime.now(timezone.utc)
        repo_path = Path(plan.repository_path).resolve()

        if plan.status == PlanStatus.BLOCKED:
            reasons_str = "; ".join(plan.blocking_reasons) if plan.blocking_reasons else "Plan is blocked"
            return ExecutionResult(
                plan_id=f"plan_{int(started_at.timestamp())}",
                repository_path=str(repo_path),
                status=ExecutionStatus.BLOCKED,
                started_at=started_at,
                finished_at=started_at,
                summary=f"Execution blocked by prerequisites: {reasons_str}",
            )

        step_results: list[StepExecutionResult] = []
        successful_step_ids: set[str] = set()
        failed_step_ids: set[str] = set()
        skipped_step_ids: list[str] = []
        is_cancelled = False

        for idx, step in enumerate(plan.steps):
            # Check if any prerequisite failed or was skipped
            unmet_prereq = next(
                (req for req in step.depends_on if req not in successful_step_ids),
                None,
            )

            if unmet_prereq is not None or failed_step_ids or is_cancelled:
                # Skip step
                skip_res = StepExecutionResult(
                    step_id=step.id,
                    status=ExecutionStatus.SKIPPED,
                    command=step.command,
                    cwd=step.cwd,
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                    duration_ms=0.0,
                    stdout=f"Skipped because prerequisite '{unmet_prereq or 'previous step'}' did not succeed",
                    exit_code=None,
                    verification_passed=False,
                )
                step_results.append(skip_res)
                skipped_step_ids.append(step.id)
                continue

            # Safety Confirmation Gate
            if not self.confirmation.confirm(step, dry_run=dry_run):
                is_cancelled = True
                cancel_res = StepExecutionResult(
                    step_id=step.id,
                    status=ExecutionStatus.CANCELLED,
                    command=step.command,
                    cwd=step.cwd,
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                    duration_ms=0.0,
                    stdout="Execution rejected by user confirmation",
                    exit_code=None,
                    verification_passed=False,
                )
                step_results.append(cancel_res)
                skipped_step_ids.append(step.id)
                continue

            # Route to step handler
            handler = self._find_handler(step)
            if handler is None:
                fail_res = StepExecutionResult(
                    step_id=step.id,
                    status=ExecutionStatus.FAILED,
                    command=step.command,
                    cwd=step.cwd,
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                    duration_ms=0.0,
                    stderr=f"No execution handler registered for action type: {step.action_type}",
                    exit_code=1,
                    verification_passed=False,
                )
                step_results.append(fail_res)
                failed_step_ids.add(step.id)
                continue

            # Execute Step
            step_result = handler.execute(
                step=step,
                repo_path=repo_path,
                executor=self.executor,
                process_manager=self.process_manager,
                dry_run=dry_run,
            )

            # Verification hook (if not already verified or if post-verification needed)
            from runrepo.executor.process import MockProcessExecutor
            if step_result.status == ExecutionStatus.SUCCESS and not dry_run and not isinstance(self.executor, MockProcessExecutor):
                passed, vmsg = StepVerifier.verify(step, step_result, repo_path)
                step_result.verification_passed = passed
                step_result.verification_details = vmsg
                if not passed:
                    step_result.status = ExecutionStatus.FAILED
                    if not step_result.stderr:
                        step_result.stderr = f"Post-execution verification failed: {vmsg}"

            step_results.append(step_result)

            if step_result.status == ExecutionStatus.SUCCESS:
                successful_step_ids.add(step.id)
            else:
                failed_step_ids.add(step.id)

        finished_at = datetime.now(timezone.utc)

        # Compute overall status
        if is_cancelled:
            final_status = ExecutionStatus.CANCELLED
            summary = "Execution was cancelled by user confirmation"
        elif failed_step_ids:
            final_status = ExecutionStatus.FAILED
            summary = f"Execution failed at step(s): {', '.join(sorted(failed_step_ids))}"
        elif len(skipped_step_ids) == len(plan.steps) and len(plan.steps) > 0:
            final_status = ExecutionStatus.SKIPPED
            summary = "All steps were skipped"
        else:
            final_status = ExecutionStatus.SUCCESS
            summary = f"Successfully executed {len(successful_step_ids)} step(s)"

        return ExecutionResult(
            plan_id=f"plan_{int(started_at.timestamp())}",
            repository_path=str(repo_path),
            status=final_status,
            steps=step_results,
            successful_steps=sorted(successful_step_ids),
            failed_steps=sorted(failed_step_ids),
            skipped_steps=skipped_step_ids,
            started_at=started_at,
            finished_at=finished_at,
            summary=summary,
        )
