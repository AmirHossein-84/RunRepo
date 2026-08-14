"""Unit tests for HttpVerifier endpoint probing and fail-fast PID monitoring."""

import urllib.error
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import MockProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep, RiskLevel, StepVerification
from runrepo.verification.models import VerificationStatus
from runrepo.verification.verifiers.http import HttpVerifier


def test_http_verifier_success(monkeypatch):
    class MockResponse:
        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: MockResponse())

    verifier = HttpVerifier(poll_interval_s=0.01, max_timeout_s=0.1)
    step = PlanStep(
        id="verify-app",
        description="Verify application HTTP",
        action_type=ActionType.VERIFY_APPLICATION,
        risk=RiskLevel.SAFE,
        reason="check HTTP",
        verification=StepVerification(strategy="http_health_check", target="http://127.0.0.1:3000", description="HTTP health check"),
    )

    step_result = StepExecutionResult(step_id="verify-app", exit_code=0)
    res = verifier.verify(step, step_result)

    assert res.status == VerificationStatus.PASSED
    assert "status 200" in res.message


def test_http_verifier_accepted_status_codes(monkeypatch):
    # 401 Unauthorized should still pass because application is alive and responding
    class MockHttpError(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("http://127.0.0.1:3000", 401, "Unauthorized", {}, None)

    def mock_urlopen(req, timeout):
        raise MockHttpError()

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    verifier = HttpVerifier(accepted_status_codes={200, 401, 403}, poll_interval_s=0.01, max_timeout_s=0.1)
    step = PlanStep(
        id="verify-app",
        description="Verify application HTTP",
        action_type=ActionType.VERIFY_APPLICATION,
        risk=RiskLevel.SAFE,
        reason="check HTTP",
        verification=StepVerification(strategy="http_health_check", target="http://127.0.0.1:3000", description="HTTP health check"),
    )

    step_result = StepExecutionResult(step_id="verify-app", exit_code=0)
    res = verifier.verify(step, step_result)

    assert res.status == VerificationStatus.PASSED
    assert "status 401" in res.message


def test_http_verifier_server_error_500(monkeypatch):
    class MockHttpError(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("http://127.0.0.1:3000", 500, "Internal Server Error", {}, None)

    def mock_urlopen(req, timeout):
        raise MockHttpError()

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    verifier = HttpVerifier(accepted_status_codes={200, 201}, poll_interval_s=0.01, max_timeout_s=0.05)
    step = PlanStep(
        id="verify-app",
        description="Verify application HTTP",
        action_type=ActionType.VERIFY_APPLICATION,
        risk=RiskLevel.SAFE,
        reason="check HTTP",
        verification=StepVerification(strategy="http_health_check", target="http://127.0.0.1:3000", description="HTTP health check"),
    )

    step_result = StepExecutionResult(step_id="verify-app", exit_code=0)
    res = verifier.verify(step, step_result)

    assert res.status == VerificationStatus.FAILED
    assert "failed readiness check" in res.message


def test_http_verifier_fail_fast_pid_crashed(tmp_path, monkeypatch):
    pm = ProcessManager(state_dir=tmp_path)
    executor = MockProcessExecutor()
    pm.start_process(name="start-app", repo_path=tmp_path, command=["python", "main.py"], executor=executor)

    # Mock is_pid_alive to return False (crashed immediately)
    monkeypatch.setattr("runrepo.verification.verifiers.http.is_pid_alive", lambda pid: False)

    verifier = HttpVerifier(poll_interval_s=0.01, max_timeout_s=1.0)
    step = PlanStep(
        id="verify-app",
        description="Verify application HTTP",
        action_type=ActionType.VERIFY_APPLICATION,
        risk=RiskLevel.SAFE,
        reason="check HTTP",
        verification=StepVerification(strategy="http_health_check", target="http://127.0.0.1:3000", description="HTTP health check"),
    )

    step_result = StepExecutionResult(step_id="verify-app", exit_code=0)
    res = verifier.verify(step, step_result, repo_path=tmp_path, process_manager=pm)

    assert res.status == VerificationStatus.FAILED
    assert "Application crashed before responding" in res.message
