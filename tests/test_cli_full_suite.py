"""CLI end-to-end integration tests for root dispatch and new subcommands."""

from pathlib import Path
from typer.testing import CliRunner
from runrepo.cli import app

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "RunRepo main CLI entrypoint" in result.output or "Usage" in result.output
    assert "pr" in result.output
    assert "repair" in result.output
    assert "export" in result.output
    assert "reproduce" in result.output
    assert "share" in result.output


def test_cli_export(tmp_path: Path) -> None:
    repo_dir = tmp_path / "cli_node"
    repo_dir.mkdir()
    (repo_dir / "package.json").write_text('{"name":"cli-export-app"}', encoding="utf-8")

    result = runner.invoke(app, ["export", str(repo_dir)])
    assert result.exit_code == 0
    assert "name: cli-export-app" in result.output


def test_cli_share(tmp_path: Path) -> None:
    repo_dir = tmp_path / "cli_share"
    repo_dir.mkdir()
    (repo_dir / "package.json").write_text('{"name":"cli-share-app"}', encoding="utf-8")

    result = runner.invoke(app, ["share", str(repo_dir)])
    assert result.exit_code == 0
    assert "Developer Onboarding Guide for cli-share-app" in result.output


def test_cli_repair(tmp_path: Path) -> None:
    repo_dir = tmp_path / "cli_repair"
    repo_dir.mkdir()

    result = runner.invoke(app, ["repair", str(repo_dir)])
    assert result.exit_code == 0
    assert "RunRepo Repair Summary" in result.output


def test_cli_start_dry_run(tmp_path: Path) -> None:
    repo_dir = tmp_path / "cli_start"
    repo_dir.mkdir()
    (repo_dir / "package.json").write_text('{"name":"cli-start-app"}', encoding="utf-8")

    result = runner.invoke(app, ["start", str(repo_dir), "--dry-run"])
    assert result.exit_code == 0
