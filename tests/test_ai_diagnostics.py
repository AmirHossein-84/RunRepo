"""Unit tests for AIDiagnosticsAssistant providing fallback failure diagnosis."""

from runrepo.ai.diagnostics import AIDiagnosticsAssistant
from runrepo.ai.gemini import GeminiClient
from runrepo.diagnostics.models import DiagnosticCategory
from runrepo.executor.models import StepExecutionResult
from runrepo.planner.models import ActionType, PlanStep, RiskLevel


def test_ai_diagnostics_assistant_fallback():
    mock_diag_json = """{
      "confidence": 0.9,
      "likely_root_cause": "Missing native build tools (gcc/clang)",
      "explanation": "Compilation of native wheels failed due to missing C++ build tools on host.",
      "suggested_fixes": [
        {
          "description": "Install Visual C++ Build Tools or pre-built binary",
          "command": ["pip", "install", "--only-binary=:all:", "mypackage"],
          "justification": "Avoids local source compilation"
        }
      ],
      "prevention_advice": "Ensure pre-compiled binary packages are referenced in pyproject.toml."
    }"""

    client = GeminiClient(api_key="mock_key", transport=lambda payload: mock_diag_json)
    assistant = AIDiagnosticsAssistant(client=client)

    step = PlanStep(
        id="install-deps",
        description="Install dependencies",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="Setup",
    )
    step_res = StepExecutionResult(
        step_id="install-deps",
        exit_code=1,
        stderr="error: command 'cl.exe' failed: No such file or directory",
    )

    diag = assistant.diagnose_failure(step, step_res)

    assert diag is not None
    assert diag.category == DiagnosticCategory.UNKNOWN
    assert "Missing native build tools" in diag.title
    assert "Compilation of native wheels failed" in diag.explanation
    assert len(diag.suggested_actions) == 1
    assert "pip install" in (diag.suggested_actions[0].command or "")
