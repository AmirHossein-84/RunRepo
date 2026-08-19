"""Unit tests for DependencyVerifier on Node and Python repositories."""

from runrepo.executor.models import StepExecutionResult
from runrepo.planner.models import ActionType, PlanStep, RiskLevel
from runrepo.verification.models import VerificationStatus
from runrepo.verification.verifiers.dependency import DependencyVerifier


def _make_install_step() -> PlanStep:
    return PlanStep(
        id="install-deps",
        description="Install dependencies",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        command=["pnpm", "install"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="pnpm lockfile detected",
    )


def test_dependency_verifier_node_success(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "test"}', encoding="utf-8")
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "vite").mkdir()

    verifier = DependencyVerifier()
    step = _make_install_step()
    step_result = StepExecutionResult(step_id="install-deps", exit_code=0)

    res = verifier.verify(step, step_result, repo_path=tmp_path)
    assert res.status == VerificationStatus.PASSED
    assert "node_modules present and populated" in res.message


def test_dependency_verifier_node_missing_node_modules(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "test", "dependencies": {"express": "1.0.0"}}', encoding="utf-8")

    verifier = DependencyVerifier()
    step = _make_install_step()
    step_result = StepExecutionResult(step_id="install-deps", exit_code=0)

    res = verifier.verify(step, step_result, repo_path=tmp_path)
    assert res.status == VerificationStatus.FAILED
    assert "node_modules directory is missing" in res.message


def test_dependency_verifier_node_empty_node_modules(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "test", "dependencies": {"express": "1.0.0"}}', encoding="utf-8")
    nm = tmp_path / "node_modules"
    nm.mkdir()

    verifier = DependencyVerifier()
    step = _make_install_step()
    step_result = StepExecutionResult(step_id="install-deps", exit_code=0)

    res = verifier.verify(step, step_result, repo_path=tmp_path)
    assert res.status == VerificationStatus.FAILED
    assert "node_modules directory is empty" in res.message


def test_dependency_verifier_python_venv(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")

    verifier = DependencyVerifier()
    step = _make_install_step()
    step_result = StepExecutionResult(step_id="install-deps", exit_code=0)

    res = verifier.verify(step, step_result, repo_path=tmp_path)
    assert res.status == VerificationStatus.PASSED
    assert ".venv" in res.message


def test_dependency_verifier_failed_exit_code(tmp_path):
    verifier = DependencyVerifier()
    step = _make_install_step()
    step_result = StepExecutionResult(
        step_id="install-deps",
        exit_code=1,
        stderr="ERR_PNPM_FETCH_404",
    )

    res = verifier.verify(step, step_result, repo_path=tmp_path)
    assert res.status == VerificationStatus.FAILED
    assert "failed with exit code 1" in res.message
