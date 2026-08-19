"""CLI tests for runrepo cache and runrepo tree commands."""

import json
from typer.testing import CliRunner
from runrepo.cli import app

runner = CliRunner()


def test_cli_cache_list_empty():
    result = runner.invoke(app, ["cache", "list"])
    assert result.exit_code == 0
    assert "No cached repositories found" in result.output or "Total:" in result.output


def test_cli_cache_clean_confirmation_no(monkeypatch):
    # Simulated runrepo cache clean answering 'n' (abort)
    monkeypatch.setattr("typer.confirm", lambda *args, **kwargs: False)
    monkeypatch.setattr("runrepo.cli.typer.confirm", lambda *args, **kwargs: False)
    result = runner.invoke(app, ["cache", "clean"], input="n\n")
    assert result.exit_code == 0 or "aborted" in result.output.lower()


def test_cli_tree_command(tmp_path):
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'apps/*'", encoding="utf-8")
    app_dir = tmp_path / "apps" / "web"
    app_dir.mkdir(parents=True)
    (app_dir / "package.json").write_text(json.dumps({"name": "web-app", "scripts": {"dev": "next dev"}}), encoding="utf-8")

    result = runner.invoke(app, ["tree", str(tmp_path)])
    assert result.exit_code == 0
    assert "web-app" in result.output
    assert "pnpm" in result.output


def test_cli_tree_json_output(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "my-app"}), encoding="utf-8")

    result = runner.invoke(app, ["tree", str(tmp_path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "workspace_type" in data
    assert "is_monorepo" in data
