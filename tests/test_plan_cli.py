"""Integration tests for runrepo plan CLI command."""

import json
from typer.testing import CliRunner

from runrepo.cli import app

runner = CliRunner()


def test_cli_plan_current_dir(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "package.json": '{"name": "test-pkg", "scripts": {"dev": "vite"}}',
        }
    )

    result = runner.invoke(app, ["plan", str(repo)])
    assert result.exit_code == 0
    assert "RunRepo Execution Plan" in result.output
    assert "test-pkg" in result.output
    assert "verify-runtime:node" in result.output.lower() or "verify-pm:npm" in result.output.lower()


def test_cli_plan_json_output(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "requirements.txt": "fastapi>=0.100.0\nuvicorn\n",
        }
    )

    result = runner.invoke(app, ["plan", str(repo), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "status" in data
    assert "steps" in data
    assert "project_info" in data
    assert "environment_state" in data
    assert isinstance(data["steps"], list)


def test_cli_plan_dry_run_flag(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "package.json": '{"name": "dry-pkg", "scripts": {"dev": "vite"}}',
        }
    )

    result = runner.invoke(app, ["plan", str(repo), "--dry-run"])
    assert result.exit_code == 0
    assert "RunRepo Execution Plan" in result.output


def test_cli_plan_nonexistent_directory(tmp_path):
    nonexistent = tmp_path / "does_not_exist"
    result = runner.invoke(app, ["plan", str(nonexistent)])
    assert result.exit_code == 1
    assert "Error: Directory" in result.output
