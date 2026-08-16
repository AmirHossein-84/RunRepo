"""Tests for runrepo export, reproduce, and share commands."""

from pathlib import Path
from typing import Any
import yaml
from runrepo.executor.process import ProcessExecutionResult, ProcessExecutor
from runrepo.reproduce.exporter import EnvironmentExporter
from runrepo.reproduce.reproducer import EnvironmentReproducer
from runrepo.reproduce.share import ShareGenerator


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
        return ProcessExecutionResult(exit_code=0, stdout="", stderr="")

    def start_background(self, command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> Any:
        return None


def test_export_yaml_and_lock(tmp_path: Path) -> None:
    repo_dir = tmp_path / "sample_app"
    repo_dir.mkdir()
    (repo_dir / "package.json").write_text('{"name":"sample-node-app","scripts":{"dev":"node server.js"}}', encoding="utf-8")

    exporter = EnvironmentExporter()
    yaml_content = exporter.export_yaml(repo_dir)
    parsed = yaml.safe_load(yaml_content)
    assert parsed["name"] == "sample-node-app"
    assert "node" in parsed["runtime"]
    assert parsed["commands"]["start"] == "node server.js"

    lock_content = exporter.export_lock(repo_dir)
    assert "sample-node-app" in lock_content
    assert "lock_version" in lock_content
    assert "resolved_runtimes" in lock_content


def test_share_generator(tmp_path: Path) -> None:
    repo_dir = tmp_path / "shared_app"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text('[project]\nname="py-shared"\nversion="0.1.0"', encoding="utf-8")
    (repo_dir / ".env.example").write_text("API_KEY=xxx", encoding="utf-8")

    gen = ShareGenerator()
    spec = gen.generate(repo_dir)
    assert spec.project_name == "py-shared"
    assert "Developer Onboarding Guide for py-shared" in spec.markdown_guide
    assert "set -Eeuo pipefail" in spec.bash_script
    assert "Set-StrictMode -Version Latest" in spec.powershell_script
    assert "$ErrorActionPreference = \"Stop\"" in spec.powershell_script


def test_reproduce_execution(tmp_path: Path) -> None:
    repo_dir = tmp_path / "locked_app"
    repo_dir.mkdir()
    (repo_dir / "package.json").write_text('{"name":"locked-app"}', encoding="utf-8")

    mock_exec = MockExecutor()
    reproducer = EnvironmentReproducer(executor=mock_exec)

    success, result, warnings = reproducer.reproduce(repo_dir, dry_run=True)
    assert success is True
    assert result is not None
    assert result.status.value == "SUCCESS"
