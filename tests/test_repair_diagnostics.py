"""Tests for autonomous diagnostic repair engine."""

from pathlib import Path
from typing import Any
from runrepo.diagnostics.repair import EnvironmentRepairManager
from runrepo.executor.process import ProcessExecutionResult, ProcessExecutor


class MockExecutor(ProcessExecutor):
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def execute(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout_s: float | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessExecutionResult:
        self.commands.append(command)
        cmd_str = " ".join(command)
        if "uv venv --clear" in cmd_str:
            return ProcessExecutionResult(exit_code=0, stdout="Cleared venv", stderr="")
        if "docker info" in cmd_str:
            return ProcessExecutionResult(exit_code=0, stdout="Server Version: 24.0.0", stderr="")
        return ProcessExecutionResult(exit_code=0, stdout="", stderr="")

    def start_background(self, command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> Any:
        return None


def test_repair_broken_venv(tmp_path: Path) -> None:
    repo_dir = tmp_path / "broken_repo"
    repo_dir.mkdir()
    venv_dir = repo_dir / ".venv"
    venv_dir.mkdir()  # empty broken venv without pyvenv.cfg

    mock_exec = MockExecutor()
    manager = EnvironmentRepairManager(executor=mock_exec)

    result = manager.repair(repo_dir)
    assert result.success is True
    assert any(a.category == "venv" and a.success for a in result.actions)
    assert any("uv venv --clear" in " ".join(cmd) for cmd in mock_exec.commands)


def test_repair_missing_env(tmp_path: Path) -> None:
    repo_dir = tmp_path / "env_repo"
    repo_dir.mkdir()
    (repo_dir / ".env.example").write_text("DATABASE_URL=postgres://localhost:5432/db\nSECRET_KEY=changeme\n", encoding="utf-8")

    mock_exec = MockExecutor()
    manager = EnvironmentRepairManager(executor=mock_exec)

    result = manager.repair(repo_dir)
    assert result.success is True
    assert (repo_dir / ".env").exists()
    env_content = (repo_dir / ".env").read_text(encoding="utf-8")
    assert "DATABASE_URL=" in env_content
    assert "SECRET_KEY=" in env_content
    assert "changeme" not in env_content  # synthesized random secret
