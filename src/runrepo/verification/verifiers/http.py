"""HTTP and port readiness verifier with polling and fail-fast PID monitoring."""

import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import MockProcessExecutor, ProcessExecutor
from runrepo.executor.process_manager import ProcessManager, is_pid_alive
from runrepo.planner.models import ActionType, PlanStep
from runrepo.verification.models import VerificationResult, VerificationStatus, VerificationType
from runrepo.verification.verifiers.base import BaseVerifier

DEFAULT_ACCEPTED_HTTP_CODES = {200, 201, 204, 301, 302, 307, 308, 401, 403, 404}


class HttpVerifier(BaseVerifier):
    """Verifies TCP port availability and HTTP endpoint responsiveness with polling retry."""

    def __init__(
        self,
        accepted_status_codes: set[int] | None = None,
        poll_interval_s: float = 0.5,
        max_timeout_s: float = 20.0,
    ) -> None:
        self.accepted_status_codes = accepted_status_codes or DEFAULT_ACCEPTED_HTTP_CODES
        self.poll_interval_s = poll_interval_s
        self.max_timeout_s = max_timeout_s

    def can_verify(self, step: PlanStep) -> bool:
        if step.verification and step.verification.strategy in ("http_health_check", "port_reachable"):
            return True
        if step.action_type == ActionType.VERIFY_APPLICATION:
            if step.verification and step.verification.strategy in (
                "process_liveness",
                "process",
                "process_running",
                "file_exists",
                "exit_code",
            ):
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

        if dry_run or isinstance(executor, MockProcessExecutor):
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.HTTP_CHECK,
                status=VerificationStatus.PASSED,
                target=step.verification.target if step.verification else "http://localhost",
                message="[dry-run] Application endpoint readiness verified",
                duration_ms=0.0,
            )

        strategy = step.verification.strategy if step.verification else "http_health_check"
        target = (step.verification.target if step.verification else None) or "http://127.0.0.1:3000"

        # Find associated process PID for fail-fast crash monitoring
        associated_pid: int | None = None
        if process_manager is not None:
            procs = process_manager.list_processes(repo_path=repo_path)
            # Find the most recently started process for this repo
            if procs:
                associated_pid = procs[-1].pid

        # 1. Port Reachable Strategy
        if strategy == "port_reachable":
            port = int(target) if target and target.isdigit() else 3000
            deadline = time.perf_counter() + self.max_timeout_s
            port_open = False
            last_err = None

            while time.perf_counter() < deadline:
                # Fail-fast check on PID
                if associated_pid is not None and not is_pid_alive(associated_pid):
                    elapsed = (time.perf_counter() - start_time) * 1000.0
                    logs = process_manager.get_process_logs(repo_path=repo_path, tail=10) if process_manager else ""
                    return VerificationResult(
                        step_id=step.id,
                        verification_type=VerificationType.PORT_CHECK,
                        status=VerificationStatus.FAILED,
                        target=f"127.0.0.1:{port}",
                        message=f"Application crashed before binding port {port}",
                        duration_ms=elapsed,
                        failure_reason="Process exited during startup polling",
                        diagnostic_data={"pid": associated_pid, "recent_logs": logs},
                    )

                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                        port_open = True
                        break
                except Exception as exc:
                    last_err = exc
                    time.sleep(self.poll_interval_s)

            elapsed = (time.perf_counter() - start_time) * 1000.0
            if port_open:
                return VerificationResult(
                    step_id=step.id,
                    verification_type=VerificationType.PORT_CHECK,
                    status=VerificationStatus.PASSED,
                    target=f"127.0.0.1:{port}",
                    message=f"Port {port} is listening and reachable",
                    details={"port": port, "polling_duration_ms": elapsed},
                    duration_ms=elapsed,
                )
            else:
                return VerificationResult(
                    step_id=step.id,
                    verification_type=VerificationType.PORT_CHECK,
                    status=VerificationStatus.FAILED,
                    target=f"127.0.0.1:{port}",
                    message=f"Timed out waiting for port {port} to open ({last_err})",
                    duration_ms=elapsed,
                    failure_reason="Port connection timeout",
                )

        # 2. HTTP Health Check Strategy
        url = target if target.startswith("http") else f"http://127.0.0.1:{target}"
        deadline = time.perf_counter() + self.max_timeout_s
        http_success = False
        last_status_code = None
        last_err_msg = None

        while time.perf_counter() < deadline:
            # Fail-fast check on PID
            if associated_pid is not None and not is_pid_alive(associated_pid):
                elapsed = (time.perf_counter() - start_time) * 1000.0
                logs = process_manager.get_process_logs(repo_path=repo_path, tail=10) if process_manager else ""
                return VerificationResult(
                    step_id=step.id,
                    verification_type=VerificationType.HTTP_CHECK,
                    status=VerificationStatus.FAILED,
                    target=url,
                    message=f"Application crashed before responding to HTTP requests at {url}",
                    duration_ms=elapsed,
                    failure_reason="Process exited during HTTP readiness check",
                    diagnostic_data={"pid": associated_pid, "recent_logs": logs},
                )

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "RunRepo/0.1"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    last_status_code = resp.getcode()
                    if last_status_code in self.accepted_status_codes:
                        http_success = True
                        break
            except urllib.error.HTTPError as exc:
                last_status_code = exc.code
                if exc.code in self.accepted_status_codes:
                    http_success = True
                    break
                last_err_msg = f"HTTP status {exc.code}"
                time.sleep(self.poll_interval_s)
            except Exception as exc:
                last_err_msg = str(exc)
                time.sleep(self.poll_interval_s)

        elapsed = (time.perf_counter() - start_time) * 1000.0
        if http_success:
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.HTTP_CHECK,
                status=VerificationStatus.PASSED,
                target=url,
                message=f"Application HTTP endpoint is responding (status {last_status_code})",
                details={"url": url, "status_code": last_status_code, "polling_duration_ms": elapsed},
                duration_ms=elapsed,
            )
        else:
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.HTTP_CHECK,
                status=VerificationStatus.FAILED,
                target=url,
                message=f"HTTP endpoint {url} failed readiness check: {last_err_msg or f'status {last_status_code}'}",
                duration_ms=elapsed,
                failure_reason="HTTP probe failed or returned unexpected status code",
                diagnostic_data={"url": url, "last_status_code": last_status_code, "error": last_err_msg},
            )
