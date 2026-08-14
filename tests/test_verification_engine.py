"""Unit tests for VerificationEngine dispatching and coordination."""

from runrepo.executor.models import StepExecutionResult
from runrepo.planner.models import ActionType, PlanStep, RiskLevel, StepVerification
from runrepo.verification.engine import VerificationEngine
from runrepo.verification.models import VerificationStatus, VerificationType


def test_verification_engine_dispatch_dependency(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "test"}', encoding="utf-8")
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "pkg").mkdir()

    engine = VerificationEngine()
    step = PlanStep(
        id="install-deps",
        description="Install dependencies",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        command=["pnpm", "install"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="pnpm lockfile detected",
    )

    step_result = StepExecutionResult(step_id="install-deps", exit_code=0)
    res = engine.verify_step(step, step_result, repo_path=tmp_path)

    assert res.status == VerificationStatus.PASSED
    assert res.verification_type == VerificationType.DEPENDENCY_CHECK


def test_verification_engine_dispatch_file(tmp_path):
    (tmp_path / ".env").write_text("API_KEY=xyz", encoding="utf-8")

    engine = VerificationEngine()
    step = PlanStep(
        id="configure-env:template",
        description="Configure env from template",
        action_type=ActionType.CONFIGURE_ENV,
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="template detected",
        verification=StepVerification(strategy="file_exists", target=".env", description=".env exists"),
    )

    step_result = StepExecutionResult(step_id="configure-env:template", exit_code=0)
    res = engine.verify_step(step, step_result, repo_path=tmp_path)

    assert res.status == VerificationStatus.PASSED
    assert res.verification_type == VerificationType.FILE_CHECK


def test_verification_engine_dry_run(tmp_path):
    engine = VerificationEngine()
    step = PlanStep(
        id="install-deps",
        description="Install dependencies",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        command=["pnpm", "install"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="pnpm lockfile detected",
    )

    step_result = StepExecutionResult(step_id="install-deps", exit_code=0)
    res = engine.verify_step(step, step_result, repo_path=tmp_path, dry_run=True)

    assert res.status == VerificationStatus.PASSED
