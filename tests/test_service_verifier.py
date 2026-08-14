"""Unit tests for ServiceVerifier with Docker Compose and port probing."""

from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.planner.models import ActionType, PlanStep, RiskLevel, StepVerification
from runrepo.verification.models import VerificationStatus
from runrepo.verification.verifiers.service import ServiceVerifier


def test_service_verifier_mock_mode(tmp_path):
    verifier = ServiceVerifier()
    step = PlanStep(
        id="start-service:docker-compose",
        description="Start docker compose",
        action_type=ActionType.START_SERVICE,
        command=["docker", "compose", "up", "-d"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="compose.yaml detected",
    )

    step_result = StepExecutionResult(step_id="start-service:docker-compose", exit_code=0)
    executor = MockProcessExecutor()

    res = verifier.verify(step, step_result, repo_path=tmp_path, executor=executor)
    assert res.status == VerificationStatus.PASSED


def test_service_verifier_failed_exit_code(tmp_path):
    verifier = ServiceVerifier()
    step = PlanStep(
        id="start-service:docker-compose",
        description="Start docker compose",
        action_type=ActionType.START_SERVICE,
        command=["docker", "compose", "up", "-d"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="compose.yaml detected",
    )

    step_result = StepExecutionResult(
        step_id="start-service:docker-compose",
        exit_code=1,
        stderr="Docker daemon not running",
    )

    res = verifier.verify(step, step_result, repo_path=tmp_path)
    assert res.status == VerificationStatus.FAILED
    assert "exit code 1" in res.message


def test_service_verifier_port_probe_failed(tmp_path, monkeypatch):
    verifier = ServiceVerifier()
    step = PlanStep(
        id="start-service:docker-compose",
        description="Start docker compose",
        action_type=ActionType.START_SERVICE,
        command=["docker", "compose", "up", "-d"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="compose.yaml detected",
        verification=StepVerification(strategy="port_reachable", target="59999", description="Port 59999 reachable"),
    )

    step_result = StepExecutionResult(step_id="start-service:docker-compose", exit_code=0)

    # Use a port that is definitely closed (e.g. 59999)
    res = verifier.verify(step, step_result, repo_path=tmp_path)
    assert res.status == VerificationStatus.FAILED
    assert "59999" in res.message
