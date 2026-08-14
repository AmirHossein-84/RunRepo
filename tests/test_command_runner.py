"""Unit tests for CommandRunner, SystemCommandRunner, and MockCommandRunner."""

from runrepo.environment.command import CommandResult, MockCommandRunner, SystemCommandRunner


def test_mock_command_runner():
    mock = MockCommandRunner(
        responses={
            ("node", "--version"): CommandResult(
                stdout="v22.15.0",
                stderr="",
                exit_code=0,
                duration_ms=10.0,
                executable="/usr/bin/node",
            )
        },
        which_map={"node": "/usr/bin/node"},
    )

    assert mock.which("node") == "/usr/bin/node"
    assert mock.which("python") is None

    res = mock.run(["node", "--version"])
    assert res.success is True
    assert res.stdout == "v22.15.0"
    assert len(mock.recorded_calls) == 1

    # Test caching: second call returns cached result without re-executing
    res2 = mock.run(["node", "--version"])
    assert res2.stdout == "v22.15.0"
    assert len(mock.recorded_calls) == 1

    # Test unknown binary
    res_missing = mock.run(["unknown_tool", "--version"])
    assert res_missing.success is False
    assert res_missing.exit_code == 127


def test_system_command_runner_missing_binary():
    runner = SystemCommandRunner()
    res = runner.run(["non_existent_binary_xyz_12345", "--version"])
    assert res.success is False
    assert res.exit_code == 127
    assert "not found" in res.stderr
