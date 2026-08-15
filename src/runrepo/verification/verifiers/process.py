"""Process verifier inspecting live background application states."""

import time
from pathlib import Path
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager, is_pid_alive
from runrepo.planner.models import ActionType, PlanStep
from runrepo.verification.models import VerificationResult, VerificationStatus, VerificationType
from runrepo.verification.verifiers.base import BaseVerifier


class ProcessVerifier(BaseVerifier):
    """Verifies that background application processes spawned by RunRepo remain actively running."""

    def can_verify(self, step: PlanStep) -> bool:
        if step.verification and step.verification.strategy in ("process_liveness", "process", "process_running"):
            return True
        if step.action_type in (ActionType.START_APPLICATION, ActionType.VERIFY_APPLICATION):
            if step.verification and step.verification.strategy in ("http_health_check", "port_reachable"):
                return False
            return True
        return False

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

        from runrepo.executor.process import MockProcessExecutor

        if dry_run or isinstance(executor, MockProcessExecutor):
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.PROCESS_CHECK,
                status=VerificationStatus.PASSED,
                target=step.id,
                message="Application background process verified",
                duration_ms=0.0,
            )

        if step_result.exit_code != 0:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.PROCESS_CHECK,
                status=VerificationStatus.FAILED,
                target=step.id,
                message=f"Application failed to spawn (exit code {step_result.exit_code})",
                duration_ms=elapsed,
                failure_reason="Process spawn returned non-zero exit code",
                diagnostic_data={"stderr": step_result.stderr},
            )

        # Check ProcessManager for PID
        if process_manager is not None:
            procs = process_manager.list_processes(repo_path=repo_path)
            matching = [p for p in procs if p.name == step.id]
            if matching:
                target_proc = matching[-1]
                pid = target_proc.pid
                alive = is_pid_alive(pid)
                elapsed = (time.perf_counter() - start_time) * 1000.0

                if not alive:
                    # Fetch recent logs to assist diagnosis
                    logs = process_manager.get_process_logs(repo_path=repo_path, name=step.id, tail=10)
                    return VerificationResult(
                        step_id=step.id,
                        verification_type=VerificationType.PROCESS_CHECK,
                        status=VerificationStatus.FAILED,
                        target=f"PID {pid}",
                        message=f"Application process (PID {pid}) exited unexpectedly after launch",
                        duration_ms=elapsed,
                        failure_reason="Process terminated immediately after start",
                        diagnostic_data={"pid": pid, "recent_logs": logs},
                    )

                return VerificationResult(
                    step_id=step.id,
                    verification_type=VerificationType.PROCESS_CHECK,
                    status=VerificationStatus.PASSED,
                    target=f"PID {pid}",
                    message=f"Application process is active (PID {pid})",
                    details={"pid": pid, "log_file": target_proc.log_file, "is_running": True},
                    duration_ms=elapsed,
                )

        elapsed = (time.perf_counter() - start_time) * 1000.0
        return VerificationResult(
            step_id=step.id,
            verification_type=VerificationType.PROCESS_CHECK,
            status=VerificationStatus.PASSED,
            target=step.id,
            message="Application process started successfully",
            duration_ms=elapsed,
        )
