"""Unit tests for ProcessExecutor implementations."""

import sys
from pathlib import Path
from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult, SystemProcessExecutor


def test_mock_process_executor_custom_responses():
    executor = MockProcessExecutor()
    executor.register_response(
        ["pnpm", "install"],
        ProcessExecutionResult(
            stdout="Installed 42 packages",
            stderr="",
            exit_code=0,
            duration_ms=45.0,
            pid=111,
        ),
    )

    res = executor.execute(["pnpm", "install"], cwd=Path("/tmp"))
    assert res.exit_code == 0
    assert res.stdout == "Installed 42 packages"
    assert len(executor.executed_commands) == 1
    assert executor.executed_commands[0] == (["pnpm", "install"], Path("/tmp"))


def test_mock_process_executor_background():
    executor = MockProcessExecutor()
    log_path = Path("/tmp/mock_log.log")
    pid = executor.start_background(["python", "main.py"], cwd=Path("/app"), log_file=log_path)
    assert pid > 0
    assert len(executor.background_commands) == 1


def test_system_process_executor_echo():
    executor = SystemProcessExecutor()
    # Cross platform command
    cmd = [sys.executable, "-c", "import sys; print('hello stdout'); sys.stderr.write('hello stderr\\n')"]
    res = executor.execute(cmd)

    assert res.exit_code == 0
    assert "hello stdout" in res.stdout
    assert "hello stderr" in res.stderr
    assert res.duration_ms > 0


def test_system_process_executor_missing_binary():
    executor = SystemProcessExecutor()
    res = executor.execute(["non_existent_binary_12345_runrepo"])
    assert res.exit_code == 127
    assert "not found" in res.stderr.lower()
