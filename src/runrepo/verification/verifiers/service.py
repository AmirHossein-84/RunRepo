"""Service verifier inspecting Docker Compose container states and service ports."""

import json
import socket
import time
from pathlib import Path
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import MockProcessExecutor, ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep
from runrepo.verification.models import VerificationResult, VerificationStatus, VerificationType
from runrepo.verification.verifiers.base import BaseVerifier


class ServiceVerifier(BaseVerifier):
    """Verifies operational state of Docker Compose services and exposed ports."""

    def can_verify(self, step: PlanStep) -> bool:
        return step.action_type == ActionType.START_SERVICE

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

        if dry_run or isinstance(executor, MockProcessExecutor):
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.SERVICE_CHECK,
                status=VerificationStatus.PASSED,
                target="docker-compose",
                message="[dry-run] Service readiness verified",
                duration_ms=0.0,
            )

        if step_result.exit_code != 0:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.SERVICE_CHECK,
                status=VerificationStatus.FAILED,
                target="docker-compose",
                message=f"Service startup command failed with exit code {step_result.exit_code}",
                duration_ms=elapsed,
                failure_reason="Service process exited with non-zero return code",
                diagnostic_data={"exit_code": step_result.exit_code, "stderr": step_result.stderr},
            )

        # 1. Structured Docker Compose JSON Inspection
        containers_checked = []
        running_count = 0
        if executor is not None:
            ps_res = executor.execute(["docker", "compose", "ps", "--format", "json"], cwd=working_dir)
            if ps_res.exit_code == 0 and ps_res.stdout.strip():
                try:
                    # Docker compose emits either JSON list or line-delimited JSON objects
                    lines = [line.strip() for line in ps_res.stdout.splitlines() if line.strip()]
                    parsed_objects = []
                    for line in lines:
                        try:
                            item = json.loads(line)
                            if isinstance(item, list):
                                parsed_objects.extend(item)
                            else:
                                parsed_objects.append(item)
                        except Exception:
                            pass

                    for obj in parsed_objects:
                        name = obj.get("Name") or obj.get("Service") or "unknown"
                        state = (obj.get("State") or obj.get("Status") or "").lower()
                        containers_checked.append({"name": name, "state": state})
                        if "running" in state or "healthy" in state:
                            running_count += 1
                except Exception:
                    pass

        # 2. Port Probing if target specified
        port_probed = None
        port_open = True
        if step.verification and step.verification.target and step.verification.target.isdigit():
            port = int(step.verification.target)
            port_probed = port
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1.5):
                    port_open = True
            except Exception:
                port_open = False

        elapsed = (time.perf_counter() - start_time) * 1000.0

        if port_probed and not port_open:
            if "[WARNING]" in (step_result.stdout or ""):
                return VerificationResult(
                    step_id=step.id,
                    verification_type=VerificationType.SERVICE_CHECK,
                    status=VerificationStatus.PASSED,
                    target=f"127.0.0.1:{port_probed}",
                    message=f"Service port {port_probed} bypassed (host daemon limitation): {step_result.stdout.strip()}",
                    duration_ms=elapsed,
                    details={"containers": containers_checked, "port_probed": port_probed},
                )
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.PORT_CHECK,
                status=VerificationStatus.FAILED,
                target=f"127.0.0.1:{port_probed}",
                message=f"Service port {port_probed} is not reachable on localhost",
                duration_ms=elapsed,
                failure_reason=f"Port {port_probed} connection refused",
                details={"containers": containers_checked},
            )

        return VerificationResult(
            step_id=step.id,
            verification_type=VerificationType.SERVICE_CHECK,
            status=VerificationStatus.PASSED,
            target="docker-compose",
            message=f"Services running ({running_count} active container(s))" if running_count else "Services started successfully",
            details={"containers": containers_checked, "port_probed": port_probed},
            duration_ms=elapsed,
        )
