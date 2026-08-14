"""AI diagnostics assistant providing fallback root-cause analysis for unknown failures."""

from runrepo.ai.gemini import GeminiClient
from runrepo.ai.prompts import (
    FAILURE_DIAGNOSTICS_SYSTEM_PROMPT,
    build_failure_diagnosis_prompt,
)
from runrepo.ai.validator import AIResponseValidator
from runrepo.diagnostics.models import (
    Diagnostic,
    DiagnosticCategory,
    DiagnosticSeverity,
    SuggestedAction,
)
from runrepo.environment.models import EnvironmentState
from runrepo.executor.models import StepExecutionResult
from runrepo.planner.models import PlanStep


class AIDiagnosticsAssistant:
    """Invoked when deterministic failure rules return UNKNOWN to provide AI-assisted insights."""

    def __init__(self, client: GeminiClient | None = None) -> None:
        self.client = client or GeminiClient()

    def diagnose_failure(
        self,
        step: PlanStep | None,
        step_result: StepExecutionResult,
        environment_state: EnvironmentState | None = None,
    ) -> Diagnostic | None:
        """Consult Gemini AI to diagnose an unrecognized execution failure."""
        if not self.client.is_available():
            return None

        env_summary = {}
        if environment_state:
            env_summary = {
                "platform": environment_state.platform,
                "architecture": environment_state.architecture,
                "checks": [{"name": c.name, "status": c.status.value} for c in environment_state.checks],
            }

        prompt = build_failure_diagnosis_prompt(
            step_id=step_result.step_id,
            command=step.command if step else None,
            exit_code=step_result.exit_code,
            error_message=step_result.error,
            stderr_excerpt=step_result.stderr,
            stdout_excerpt=step_result.stdout,
            environment_info=env_summary,
        )

        try:
            raw_text = self.client.generate(
                prompt,
                system_instruction=FAILURE_DIAGNOSTICS_SYSTEM_PROMPT,
            )
            ai_diag = AIResponseValidator.parse_diagnostic_result(raw_text)
        except Exception:
            return None

        # Convert to standard Diagnostic model
        suggested_actions = [
            SuggestedAction(
                title=fix.description,
                command=" ".join(fix.command) if fix.command else None,
                description=fix.justification,
                is_safe_to_copy=fix.is_safe,
            )
            for fix in ai_diag.suggested_fixes
        ]

        title = f"AI Diagnosis: {ai_diag.likely_root_cause}" if ai_diag.likely_root_cause else "AI Diagnostic Analysis"

        return Diagnostic(
            id=f"diag:ai:{step_result.step_id}",
            severity=DiagnosticSeverity.ERROR,
            category=DiagnosticCategory.UNKNOWN,
            title=title,
            explanation=f"{ai_diag.explanation}\n\n[Prevention Advice]: {ai_diag.prevention_advice}".strip(),
            affected_step_id=step_result.step_id,
            stdout_excerpt=step_result.stdout,
            stderr_excerpt=step_result.stderr,
            exit_code=step_result.exit_code,
            suggested_actions=suggested_actions,
        )
