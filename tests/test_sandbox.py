"""Unit tests for SandboxedProcessExecutor and SandboxPolicy."""

from pathlib import Path
from runrepo.executor.process import MockProcessExecutor
from runrepo.executor.sandbox import SandboxedProcessExecutor, SandboxPolicy


def test_sandbox_working_directory_boundary_violation(tmp_path):
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    policy = SandboxPolicy(allowed_working_dir=sandbox_root)
    mock = MockProcessExecutor()
    executor = SandboxedProcessExecutor(policy=policy, underlying_executor=mock)

    # Attempting to run outside allowed working directory fails
    res = executor.execute(["echo", "hello"], cwd=outside_dir)
    assert res.exit_code == 1
    assert "Sandbox Violation" in res.stderr
    assert len(mock.executed_commands) == 0


def test_sandbox_working_directory_permitted(tmp_path):
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()
    child_dir = sandbox_root / "subdir"
    child_dir.mkdir()

    policy = SandboxPolicy(allowed_working_dir=sandbox_root)
    mock = MockProcessExecutor()
    executor = SandboxedProcessExecutor(policy=policy, underlying_executor=mock)

    res = executor.execute(["echo", "hello"], cwd=child_dir)
    assert res.exit_code == 0
    assert len(mock.executed_commands) == 1


def test_sandbox_environment_isolation():
    policy = SandboxPolicy(
        isolate_environment=True,
        allowed_env_vars=["PATH"],
        custom_env={"SAFE_VAR": "123"},
    )
    mock = MockProcessExecutor()
    executor = SandboxedProcessExecutor(policy=policy, underlying_executor=mock)

    res = executor.execute(["echo", "test"], env={"CALLER_VAR": "abc"})
    assert res.exit_code == 0
    assert len(mock.executed_commands) == 1
