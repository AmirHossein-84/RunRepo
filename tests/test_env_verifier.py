"""Unit tests for EnvVerifier confirming environment variables across supported sources."""

from runrepo.executor.models import StepExecutionResult
from runrepo.planner.models import ActionType, PlanStep, RiskLevel, StepVerification
from runrepo.verification.models import VerificationStatus
from runrepo.verification.verifiers.env import EnvVerifier


def test_env_verifier_success(tmp_path, monkeypatch):
    (tmp_path / ".env.example").write_text("PORT=3000\n", encoding="utf-8")
    (tmp_path / ".env").write_text("PORT=3000\n", encoding="utf-8")

    verifier = EnvVerifier()
    step = PlanStep(
        id="configure-env",
        description="Config env",
        action_type=ActionType.CONFIGURE_ENV,
        risk=RiskLevel.SAFE,
        reason="Setup",
    )
    step_result = StepExecutionResult(step_id=step.id, exit_code=0)

    res = verifier.verify(step, step_result, repo_path=tmp_path)
    assert res.passed is True
    assert res.status == VerificationStatus.PASSED


def test_env_verifier_missing_variable(tmp_path):
    (tmp_path / ".env.example").write_text("CUSTOM_SECRET=\n", encoding="utf-8")
    # Empty .env without the required variable
    (tmp_path / ".env").write_text("# empty\n", encoding="utf-8")

    verifier = EnvVerifier()
    step = PlanStep(
        id="configure-env",
        description="Config env",
        action_type=ActionType.CONFIGURE_ENV,
        risk=RiskLevel.SAFE,
        reason="Setup",
        verification=StepVerification(
            strategy="env_available",
            description="Verify required env available",
        ),
    )
    step_result = StepExecutionResult(step_id=step.id, exit_code=0)

    res = verifier.verify(step, step_result, repo_path=tmp_path)
    assert res.passed is False
    assert res.status == VerificationStatus.FAILED
    assert "CUSTOM_SECRET" in res.message
