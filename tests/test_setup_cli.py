"""Integration tests for runrepo setup, status, stop, logs CLI commands."""

import json
from typer.testing import CliRunner

from runrepo.cli import app

runner = CliRunner()


def test_cli_setup_dry_run(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "package.json": '{"name": "test-app", "scripts": {"dev": "vite"}}',
        }
    )

    result = runner.invoke(app, ["setup", str(repo), "--dry-run"])
    assert result.exit_code == 0
    assert "RunRepo Execution Result" in result.output
    assert "SUCCESS" in result.output


def test_cli_setup_json_output(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "package.json": '{"name": "json-app", "scripts": {"dev": "vite"}}',
        }
    )

    result = runner.invoke(app, ["setup", str(repo), "--dry-run", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "status" in data
    assert "steps" in data
    assert data["status"] == "SUCCESS"


def test_cli_status_command():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "RunRepo Managed Background Processes" in result.output


def test_cli_stop_nonexistent_process():
    result = runner.invoke(app, ["stop", "--name", "non_existent_12345"])
    assert result.exit_code == 0
    assert "No matching running processes found" in result.output


def test_cli_logs_nonexistent_process():
    result = runner.invoke(app, ["logs", "--name", "non_existent_12345"])
    assert result.exit_code == 0
    assert "No matching processes found" in result.output
