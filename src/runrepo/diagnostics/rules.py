"""Deterministic failure classification and diagnostic rules with priority ordering."""

import re
from abc import ABC, abstractmethod
from typing import Any
from runrepo.diagnostics.models import (
    Diagnostic,
    DiagnosticCategory,
    DiagnosticSeverity,
    SuggestedAction,
)
from runrepo.executor.models import StepExecutionResult
from runrepo.planner.models import PlanStep
from runrepo.verification.models import VerificationResult


class DiagnosticRule(ABC):
    """Abstract failure rule inspecting error signals and output."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the rule."""
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """Evaluation priority. Higher priority rules match first."""
        ...

    @abstractmethod
    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        """Evaluate if this rule explains the failure and return structured Diagnostic."""
        ...


class PermissionDeniedRule(DiagnosticRule):
    """Matches filesystem or OS access permission errors."""

    @property
    def name(self) -> str:
        return "permission_denied"

    @property
    def priority(self) -> int:
        return 100

    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        lower = combined_error.lower()
        if any(p in lower for p in ("eacces", "permission denied", "access is denied", "operation not permitted")):
            step_id = step.id if step else (step_result.step_id if step_result else "unknown")
            return Diagnostic(
                id=f"diag:permission:{step_id}",
                severity=DiagnosticSeverity.ERROR,
                category=DiagnosticCategory.PERMISSION,
                title="Filesystem or Command Permission Denied",
                explanation=(
                    f"The operation failed because the current user lacks required permissions to access files "
                    f"or execute system processes in this directory."
                ),
                affected_step_id=step_id,
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
                exit_code=step_result.exit_code if step_result else None,
                suggested_actions=[
                    SuggestedAction(
                        title="Check directory permissions",
                        description="Ensure your current user account owns the project directory and has write access.",
                    ),
                    SuggestedAction(
                        title="Reopen terminal with elevated privileges",
                        description="If system-level operations or port bindings require administrator access, reopen PowerShell/Terminal as Administrator.",
                    ),
                ],
            )
        return None


class PortConflictRule(DiagnosticRule):
    """Matches network port collisions."""

    @property
    def name(self) -> str:
        return "port_conflict"

    @property
    def priority(self) -> int:
        return 90

    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        lower = combined_error.lower()
        if any(p in lower for p in ("eaddrinuse", "address already in use", "port is already allocated", "only one usage of each socket address")):
            step_id = step.id if step else (step_result.step_id if step_result else "unknown")
            # Extract port if possible
            port_match = re.search(r":(\d{4,5})", combined_error) or re.search(r"port (\d{4,5})", combined_error, re.IGNORECASE)
            port_str = port_match.group(1) if port_match else "the configured port"

            owner_desc = ""
            if port_match:
                try:
                    from runrepo.diagnostics.network import PortDiagnostics
                    owner_info = PortDiagnostics.get_port_owner(int(port_match.group(1)))
                    if owner_info and owner_info.pid:
                        owner_desc = f" Occupied by PID {owner_info.pid}"
                        if owner_info.process_name:
                            owner_desc += f" ({owner_info.process_name})"
                        owner_desc += "."
                except Exception:
                    pass

            return Diagnostic(
                id=f"diag:port_conflict:{step_id}",
                severity=DiagnosticSeverity.ERROR,
                category=DiagnosticCategory.NETWORK,
                title=f"Network Port Conflict ({port_str})",
                explanation=f"A service failed to bind to {port_str} because another active process or container is already using it.{owner_desc}",
                affected_step_id=step_id,
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
                exit_code=step_result.exit_code if step_result else None,
                suggested_actions=[
                    SuggestedAction(
                        title=f"Identify and stop the conflicting process on {port_str}",
                        command=f"netstat -ano | findstr {port_str}" if port_match else "netstat -ano",
                        description="Locate the PID listening on the conflicting port and terminate it, or reconfigure the application port in .env.",
                    ),
                    SuggestedAction(
                        title="Stop existing background RunRepo processes",
                        command="runrepo stop --all",
                        description="Stop all RunRepo-managed background services and processes that may still be bound to local ports.",
                    ),
                ],
            )
        return None


class DockerUnavailableRule(DiagnosticRule):
    """Matches Docker daemon or Docker CLI missing/stopped errors."""

    @property
    def name(self) -> str:
        return "docker_unavailable"

    @property
    def priority(self) -> int:
        return 85

    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        lower = combined_error.lower()
        if any(p in lower for p in ("error response from daemon", "cannot connect to the docker daemon", "is the docker daemon running", "docker daemon is not running", "docker daemon unavailable")):
            step_id = step.id if step else (step_result.step_id if step_result else "unknown")
            return Diagnostic(
                id=f"diag:docker:{step_id}",
                severity=DiagnosticSeverity.ERROR,
                category=DiagnosticCategory.SERVICE,
                title="Docker Daemon Unreachable",
                explanation="RunRepo attempted to start containerized services (such as PostgreSQL, Redis, or Compose), but the Docker engine/daemon is not running.",
                affected_step_id=step_id,
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
                exit_code=step_result.exit_code if step_result else None,
                suggested_actions=[
                    SuggestedAction(
                        title="Start Docker Desktop",
                        description="Launch Docker Desktop on Windows and ensure the engine status changes to 'Running'.",
                    ),
                    SuggestedAction(
                        title="Verify Docker connectivity",
                        command="docker info",
                        description="Check that Docker responds cleanly in your terminal before running setup again.",
                    ),
                ],
            )
        return None


class MissingCommandRule(DiagnosticRule):
    """Matches missing CLI binaries or executable PATH issues."""

    @property
    def name(self) -> str:
        return "missing_command"

    @property
    def priority(self) -> int:
        return 80

    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        lower = combined_error.lower()
        if any(p in lower for p in ("not recognized as an internal or external command", "command not found", "no such file or directory", "executable file not found")):
            step_id = step.id if step else (step_result.step_id if step_result else "unknown")
            cmd_str = " ".join(step.command) if (step and step.command) else "The required tool"
            return Diagnostic(
                id=f"diag:missing_command:{step_id}",
                severity=DiagnosticSeverity.ERROR,
                category=DiagnosticCategory.DEPENDENCY,
                title="Required Command / Executable Missing",
                explanation=f"Command execution failed because the required executable was not found on your system PATH: '{cmd_str}'.",
                affected_step_id=step_id,
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
                exit_code=step_result.exit_code if step_result else None,
                suggested_actions=[
                    SuggestedAction(
                        title="Run environment health check",
                        command="runrepo doctor",
                        description="Run doctor to inspect which runtimes or package managers need installation.",
                    ),
                    SuggestedAction(
                        title="Verify system PATH",
                        description="Ensure the directory containing the executable is added to your user or system environment PATH variable.",
                    ),
                ],
            )
        return None


class MissingEnvVarRule(DiagnosticRule):
    """Matches missing required environment variable failures."""

    @property
    def name(self) -> str:
        return "missing_env_var"

    @property
    def priority(self) -> int:
        return 75

    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        lower = combined_error.lower()
        if any(p in lower for p in ("missing required environment variable", "keyerror:", "environmentvariableerror", "env var is missing")):
            step_id = step.id if step else (step_result.step_id if step_result else "unknown")
            return Diagnostic(
                id=f"diag:missing_env:{step_id}",
                severity=DiagnosticSeverity.ERROR,
                category=DiagnosticCategory.CONFIGURATION,
                title="Missing Required Environment Configuration",
                explanation="The application failed to start or verify because one or more mandatory environment variables are undefined.",
                affected_step_id=step_id,
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
                exit_code=step_result.exit_code if step_result else None,
                suggested_actions=[
                    SuggestedAction(
                        title="Inspect .env configuration",
                        description="Check .env.example or .env.template and populate all required variables in .env.",
                    ),
                    SuggestedAction(
                        title="Re-run RunRepo environment preparation",
                        command="runrepo setup",
                        description="Run setup to automatically generate safe local database credentials and application secrets.",
                    ),
                ],
            )
        return None


class VersionMismatchRule(DiagnosticRule):
    """Matches runtime version incompatibilities."""

    @property
    def name(self) -> str:
        return "version_mismatch"

    @property
    def priority(self) -> int:
        return 70

    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        lower = combined_error.lower()
        if "version mismatch" in lower or "unsupported engine" in lower or "requires node" in lower:
            step_id = step.id if step else (step_result.step_id if step_result else "unknown")
            return Diagnostic(
                id=f"diag:version_mismatch:{step_id}",
                severity=DiagnosticSeverity.ERROR,
                category=DiagnosticCategory.ENVIRONMENT,
                title="Runtime Version Incompatibility",
                explanation="The installed runtime version on the host machine does not satisfy the repository version constraints.",
                affected_step_id=step_id,
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
                exit_code=step_result.exit_code if step_result else None,
                suggested_actions=[
                    SuggestedAction(
                        title="Switch active runtime version",
                        description="Use a version manager (e.g. nvm, fnm, pyenv) to switch to the compatible version indicated in .nvmrc or pyproject.toml.",
                    ),
                ],
            )
        return None


class DependencyFailureRule(DiagnosticRule):
    """Matches package manager dependency installation failures."""

    @property
    def name(self) -> str:
        return "dependency_failure"

    @property
    def priority(self) -> int:
        return 50

    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        lower = combined_error.lower()
        if any(p in lower for p in ("eresolve", "npm err!", "pip install", "no matching distribution", "could not solve dependencies", "yarn error", "pnpm err", "externally managed", "externally-managed", "break-system-packages")):
            step_id = step.id if step else (step_result.step_id if step_result else "unknown")
            return Diagnostic(
                id=f"diag:dependency:{step_id}",
                severity=DiagnosticSeverity.ERROR,
                category=DiagnosticCategory.DEPENDENCY,
                title="Dependency Installation Failed",
                explanation="The package manager encountered conflicting dependency constraints or network errors during package installation.",
                affected_step_id=step_id,
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
                exit_code=step_result.exit_code if step_result else None,
                suggested_actions=[
                    SuggestedAction(
                        title="Clean package cache and retry",
                        command="npm cache clean --force",
                        description="Purge any corrupt local package caches and re-attempt dependency installation.",
                    ),
                    SuggestedAction(
                        title="Inspect lockfile consistency",
                        description="Ensure your lockfile (package-lock.json, pnpm-lock.yaml, uv.lock) is not corrupted or referencing inaccessible private registries.",
                    ),
                ],
            )
        return None


class NetworkTimeoutRule(DiagnosticRule):
    """Matches network timeouts or connection refused errors."""

    @property
    def name(self) -> str:
        return "network_timeout"

    @property
    def priority(self) -> int:
        return 45

    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        lower = combined_error.lower()
        if any(p in lower for p in ("etimedout", "connection refused", "connection timeout", "fetch failed", "econnrefused", "temporary failure in name resolution")):
            step_id = step.id if step else (step_result.step_id if step_result else "unknown")
            return Diagnostic(
                id=f"diag:network:{step_id}",
                severity=DiagnosticSeverity.ERROR,
                category=DiagnosticCategory.NETWORK,
                title="Network Connection Failed or Timed Out",
                explanation="A network request failed due to an unreachable host, DNS resolution error, or request timeout.",
                affected_step_id=step_id,
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
                exit_code=step_result.exit_code if step_result else None,
                suggested_actions=[
                    SuggestedAction(
                        title="Check internet connectivity and VPN/Proxy settings",
                        description="Verify your internet connection is active and that no corporate proxy is intercepting outbound traffic.",
                    ),
                ],
            )
        return None


class ProcessCrashRule(DiagnosticRule):
    """Matches background process immediate crash or health probe failure."""

    @property
    def name(self) -> str:
        return "process_crash"

    @property
    def priority(self) -> int:
        return 40

    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        from runrepo.planner.models import ActionType

        is_process_step = step and step.action_type in (ActionType.START_APPLICATION, ActionType.START_SERVICE)
        is_process_verification = verification and getattr(verification, "verification_type", None) and str(verification.verification_type) in ("PROCESS_CHECK", "HTTP_CHECK", "PORT_CHECK")
        has_crash_text = any(p in combined_error.lower() for p in ("crashed", "segmentation fault", "sigsegv", "sigabrt", "unhandled exception", "fatal exception"))

        if is_process_step or is_process_verification or has_crash_text:
            step_id = step.id if step else (step_result.step_id if step_result else "unknown")
            return Diagnostic(
                id=f"diag:process_crash:{step_id}",
                severity=DiagnosticSeverity.ERROR,
                category=DiagnosticCategory.PROCESS,
                title="Application Process Terminated Unexpectedly",
                explanation="The application process exited prematurely or failed to become responsive on its configured health check endpoint.",
                affected_step_id=step_id,
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
                exit_code=step_result.exit_code if step_result else None,
                suggested_actions=[
                    SuggestedAction(
                        title="View recent process log output",
                        command="runrepo logs --tail 50",
                        description="Inspect the standard output and error streams captured during startup.",
                    ),
                ],
            )
        return None


class UnknownFailureRule(DiagnosticRule):
    """Fallback rule producing a structured diagnostic for unrecognized failure cases."""

    @property
    def name(self) -> str:
        return "unknown_failure"

    @property
    def priority(self) -> int:
        return 10

    def match(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult | None,
        verification: VerificationResult | None,
        combined_error: str,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
    ) -> Diagnostic | None:
        step_id = step.id if step else (step_result.step_id if step_result else "unknown")
        exit_code = step_result.exit_code if step_result else None
        return Diagnostic(
            id=f"diag:unknown:{step_id}",
            severity=DiagnosticSeverity.ERROR,
            category=DiagnosticCategory.UNKNOWN,
            title="Unrecognized Failure",
            explanation=f"The operation failed with exit code {exit_code or 'unknown'}. No specific root cause pattern was recognized in output logs.",
            affected_step_id=step_id,
            stdout_excerpt=stdout_excerpt,
            stderr_excerpt=stderr_excerpt,
            exit_code=exit_code,
            suggested_actions=[
                SuggestedAction(
                    title="Review full error logs",
                    command="runrepo logs --tail 100",
                    description="Examine the full execution log for stack traces or error messages.",
                ),
            ],
        )


DEFAULT_DIAGNOSTIC_RULES: list[DiagnosticRule] = [
    PermissionDeniedRule(),
    PortConflictRule(),
    DockerUnavailableRule(),
    MissingCommandRule(),
    MissingEnvVarRule(),
    VersionMismatchRule(),
    DependencyFailureRule(),
    NetworkTimeoutRule(),
    ProcessCrashRule(),
    UnknownFailureRule(),
]
