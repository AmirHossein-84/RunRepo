"""Post-execution verification layer confirming step outcomes and operational readiness."""

import socket
import urllib.error
import urllib.request
from pathlib import Path
from runrepo.executor.models import StepExecutionResult
from runrepo.planner.models import PlanStep


class StepVerifier:
    """Verifies that executed plan steps achieved their expected outcome."""

    @classmethod
    def verify(
        cls,
        step: PlanStep,
        step_result: StepExecutionResult,
        repo_path: Path | None = None,
    ) -> tuple[bool, str]:
        """Perform deterministic verification for an executed step."""
        if not step.verification:
            # If no explicit verification strategy, rely on exit code
            passed = step_result.exit_code == 0
            msg = "Execution exited with code 0" if passed else f"Execution failed with exit code {step_result.exit_code}"
            return passed, msg

        strategy = step.verification.strategy
        target = step.verification.target
        base_path = repo_path.resolve() if repo_path is not None else Path.cwd()
        working_dir = (base_path / step.cwd).resolve() if step.cwd else base_path

        if strategy == "exit_code":
            passed = step_result.exit_code == 0
            msg = (
                f"Exit code 0 confirmed ({step.verification.description or 'success'})"
                if passed
                else f"Command failed with exit code {step_result.exit_code}"
            )
            return passed, msg

        elif strategy == "file_exists":
            if not target:
                passed = step_result.exit_code == 0
                return passed, f"Exit code {step_result.exit_code}"

            file_path = (working_dir / target).resolve()
            passed = file_path.exists()
            msg = (
                f"Required target exists: {file_path.name}"
                if passed
                else f"Expected target does not exist after execution: {file_path}"
            )
            return passed, msg

        elif strategy == "port_reachable":
            port = int(target) if target and target.isdigit() else 3000
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1.5):
                    return True, f"Port {port} is reachable on localhost"
            except (OSError, ConnectionRefusedError) as exc:
                return False, f"Port {port} connection failed: {exc}"

        elif strategy == "http_health_check":
            url = target or "http://127.0.0.1:3000"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "RunRepo/0.1"})
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    code = resp.getcode()
                    passed = code < 500
                    return passed, f"HTTP health check returned status {code}"
            except urllib.error.HTTPError as exc:
                # 404 or 401 still proves the server is alive and responding
                return exc.code < 500, f"HTTP health check server responded with status {exc.code}"
            except Exception as exc:
                return False, f"HTTP health check failed: {exc}"

        # Default fallback
        passed = step_result.exit_code == 0
        return passed, f"Exit code {step_result.exit_code}"
