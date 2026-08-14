"""Unit tests for StepVerifier strategies."""

from runrepo.executor.models import StepExecutionResult
from runrepo.executor.verification import StepVerifier
from runrepo.planner.models import ActionType, PlanStep, RiskLevel, StepVerification


def test_step_verifier_exit_code():
    step = PlanStep(
        id="test-1",
        description="test",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        risk=RiskLevel.SAFE,
        reason="test",
        verification=StepVerification(strategy="exit_code", description="Exit code 0"),
    )

    res_ok = StepExecutionResult(step_id="test-1", exit_code=0)
    passed, msg = StepVerifier.verify(step, res_ok, repo_path=None)
    assert passed is True

    res_fail = StepExecutionResult(step_id="test-1", exit_code=1)
    passed, msg = StepVerifier.verify(step, res_fail, repo_path=None)
    assert passed is False


def test_step_verifier_file_exists(tmp_path):
    step = PlanStep(
        id="test-env",
        description="test",
        action_type=ActionType.CONFIGURE_ENV,
        risk=RiskLevel.SAFE,
        reason="test",
        verification=StepVerification(strategy="file_exists", target=".env", description=".env exists"),
    )

    res = StepExecutionResult(step_id="test-env", exit_code=0)

    # Before creating .env
    passed, msg = StepVerifier.verify(step, res, repo_path=tmp_path)
    assert passed is False

    # After creating .env
    (tmp_path / ".env").write_text("FOO=bar", encoding="utf-8")
    passed, msg = StepVerifier.verify(step, res, repo_path=tmp_path)
    assert passed is True
