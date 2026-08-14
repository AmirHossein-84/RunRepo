"""Unit tests for ProcessVerifier on background processes."""

from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import MockProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep, RiskLevel
from runrepo.verification.models import VerificationStatus
from runrepo.verification.verifiers.process import ProcessVerifier


def test_process_verifier_live_process(tmp_path, monkeypatch):
    pm = ProcessManager(state_dir=tmp_path)
    executor = MockProcessExecutor()
    proc = pm.start_process(
        name="start-app",
        repo_path=tmp_path,
        command=["python", "main.py"],
        executor=executor,
    )

    # Mock is_pid_alive to return True
    monkeypatch.setattr("runrepo.verification.verifiers.process.is_pid_alive", lambda pid: True)

    verifier = ProcessVerifier()
    step = PlanStep(
        id="start-app",
        description="Start application",
        action_type=ActionType.START_APPLICATION,
        command=["python", "main.py"],
        risk=RiskLevel.SAFE,
        reason="entrypoint detected",
    )

    step_result = StepExecutionResult(step_id="start-app", exit_code=0)
    res = verifier.verify(step, step_result, repo_path=tmp_path, process_manager=pm)

    assert res.status == VerificationStatus.PASSED
    assert f"PID {proc.pid}" in res.message


def test_process_verifier_crashed_process(tmp_path, monkeypatch):
    pm = ProcessManager(state_dir=tmp_path)
    executor = MockProcessExecutor()
    proc = pm.start_process(
        name="start-app",
        repo_path=tmp_path,
        command=["python", "main.py"],
        executor=executor,
    )

    # Mock is_pid_alive to return False (crashed)
    monkeypatch.setattr("runrepo.verification.verifiers.process.is_pid_alive", lambda pid: False)

    verifier = ProcessVerifier()
    step = PlanStep(
        id="start-app",
        description="Start application",
        action_type=ActionType.START_APPLICATION,
        command=["python", "main.py"],
        risk=RiskLevel.SAFE,
        reason="entrypoint detected",
    )

    step_result = StepExecutionResult(step_id="start-app", exit_code=0)
    res = verifier.verify(step, step_result, repo_path=tmp_path, process_manager=pm)

    assert res.status == VerificationStatus.FAILED
    assert "exited unexpectedly" in res.message
