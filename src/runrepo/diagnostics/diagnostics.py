"""DiagnosticsEngine coordinating pre-flight and post-execution failure diagnosis with early secret scrubbing."""

import re
from runrepo.diagnostics.models import (
    Diagnostic,
    DiagnosticCategory,
    DiagnosticSeverity,
    SuggestedAction,
)
from runrepo.diagnostics.rules import DEFAULT_DIAGNOSTIC_RULES, DiagnosticRule
from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.env.redactor import is_sensitive_key, redact_value
from runrepo.executor.models import ExecutionResult, ExecutionStatus, StepExecutionResult
from runrepo.models import ProjectInfo
from runrepo.planner.models import ExecutionPlan, PlanStep
from runrepo.verification.models import VerificationResult


class DiagnosticsEngine:
    """Read-only diagnostics engine synthesizing root-cause explanations and safe suggestions."""

    def __init__(self, rules: list[DiagnosticRule] | None = None) -> None:
        raw_rules = rules or DEFAULT_DIAGNOSTIC_RULES
        # Sort by priority descending
        self.rules = sorted(raw_rules, key=lambda r: r.priority, reverse=True)

    @classmethod
    def sanitize_log_excerpt(cls, text: str | None, max_lines: int = 15) -> str | None:
        """Sanitize, scrub secrets, and extract trailing lines of a log string."""
        if not text or not text.strip():
            return None

        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return None

        trailing = lines[-max_lines:]
        sanitized_lines = []

        for line in trailing:
            # Mask potential key=value secrets
            cleaned = line
            # Match assignments like FOO_KEY=abc or --password=xyz
            cleaned = re.sub(
                r'([A-Za-z_0-9]*(?:SECRET|PASSWORD|PASSWD|KEY|TOKEN|AUTH)[A-Za-z_0-9]*\s*=\s*)([^\s,]+)',
                lambda m: f"{m.group(1)}******",
                cleaned,
                flags=re.IGNORECASE,
            )
            # Match Bearer tokens or sk- tokens
            cleaned = re.sub(
                r'(Bearer\s+|sk-[A-Za-z0-9_-]+)([A-Za-z0-9_.-]+)',
                lambda m: f"{m.group(1)[:4]}******",
                cleaned,
                flags=re.IGNORECASE,
            )
            sanitized_lines.append(cleaned)

        return "\n".join(sanitized_lines)

    def diagnose_execution(
        self,
        execution_result: ExecutionResult,
        plan: ExecutionPlan | None = None,
    ) -> list[Diagnostic]:
        """Diagnose failed steps or verification failures from an ExecutionResult."""
        diagnostics: list[Diagnostic] = []
        step_map: dict[str, PlanStep] = {s.id: s for s in plan.steps} if plan else {}
        step_records = execution_result.steps if hasattr(execution_result, "steps") else getattr(execution_result, "step_results", [])

        for step_res in step_records:
            if step_res.status == ExecutionStatus.FAILED or (step_res.verification and not step_res.verification.passed):
                step = step_map.get(step_res.step_id)

                stdout_clean = self.sanitize_log_excerpt(step_res.stdout)
                stderr_clean = self.sanitize_log_excerpt(step_res.stderr)

                combined_error_parts = []
                if step_res.error:
                    combined_error_parts.append(step_res.error)
                if step_res.stderr:
                    combined_error_parts.append(step_res.stderr)
                if step_res.stdout:
                    combined_error_parts.append(step_res.stdout)
                if step_res.verification and step_res.verification.message:
                    combined_error_parts.append(step_res.verification.message)

                combined_error = " \n ".join(combined_error_parts)

                # Match against priority-ordered rules
                matched_diag: Diagnostic | None = None
                for rule in self.rules:
                    matched_diag = rule.match(
                        step=step,
                        step_result=step_res,
                        verification=step_res.verification,
                        combined_error=combined_error,
                        stdout_excerpt=stdout_clean,
                        stderr_excerpt=stderr_clean,
                    )
                    if matched_diag is not None:
                        break

                if matched_diag:
                    diagnostics.append(matched_diag)

        return diagnostics

    def diagnose_environment(
        self,
        environment_state: EnvironmentState,
        project_info: ProjectInfo | None = None,
    ) -> list[Diagnostic]:
        """Diagnose missing runtimes, package managers, or broken daemon checks from EnvironmentState."""
        diagnostics: list[Diagnostic] = []

        for check in environment_state.checks:
            if check.status == EnvironmentStatus.OK:
                continue

            name_lower = check.name.lower()

            if check.status == EnvironmentStatus.MISSING:
                if name_lower in ("docker", "docker-compose"):
                    diagnostics.append(
                        Diagnostic(
                            id=f"diag:env:missing:{name_lower}",
                            severity=DiagnosticSeverity.ERROR,
                            category=DiagnosticCategory.SERVICE,
                            title="Docker Engine / Daemon Missing or Not Installed",
                            explanation=f"Docker is required by this repository but was not found on your system PATH: {check.details or 'CLI missing'}",
                            suggested_actions=[
                                SuggestedAction(
                                    title="Install Docker Desktop",
                                    description="Download and install Docker Desktop for Windows from https://docker.com/products/docker-desktop.",
                                ),
                            ],
                        )
                    )
                else:
                    diagnostics.append(
                        Diagnostic(
                            id=f"diag:env:missing:{name_lower}",
                            severity=DiagnosticSeverity.ERROR,
                            category=DiagnosticCategory.DEPENDENCY,
                            title=f"Required Runtime or Tool Missing: '{check.name}'",
                            explanation=f"The project requires {check.name} {check.required_version or ''}, but it is not installed or accessible on PATH.",
                            suggested_actions=[
                                SuggestedAction(
                                    title=f"Install {check.name}",
                                    description=f"Install {check.name} on your system and verify with '{check.name} --version'.",
                                ),
                            ],
                        )
                    )

            elif check.status == EnvironmentStatus.WRONG_VERSION:
                diagnostics.append(
                    Diagnostic(
                        id=f"diag:env:version:{name_lower}",
                        severity=DiagnosticSeverity.ERROR,
                        category=DiagnosticCategory.ENVIRONMENT,
                        title=f"Runtime Version Mismatch: '{check.name}'",
                        explanation=(
                            f"Installed {check.name} version ({check.installed_version}) does not satisfy "
                            f"the repository requirement ({check.required_version})."
                        ),
                        suggested_actions=[
                            SuggestedAction(
                                title=f"Switch {check.name} version",
                                description=f"Use a version manager (e.g. nvm, fnm, pyenv) to switch to {check.required_version}.",
                            ),
                        ],
                    )
                )

        return diagnostics
