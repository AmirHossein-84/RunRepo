"""Integration tests for runrepo doctor CLI command."""

import json
from typer.testing import CliRunner

from runrepo.cli import app

runner = CliRunner()


def test_cli_doctor_host_mode():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "RunRepo Environment Check (Doctor)" in result.output
    assert "Host System Overview" in result.output


def test_cli_doctor_host_mode_json():
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "checks" in data
    assert "platform" in data
    assert "architecture" in data
    assert "is_satisfied" in data
    assert isinstance(data["checks"], list)


def test_cli_doctor_with_project_fixture(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "package.json": '{"name": "test-pkg", "scripts": {"dev": "vite"}}',
        }
    )

    result = runner.invoke(app, ["doctor", str(repo)])
    assert result.exit_code == 0
    assert "RunRepo Environment Check (Doctor)" in result.output
    assert "node" in result.output.lower() or "npm" in result.output.lower()


def test_cli_doctor_with_project_fixture_json(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "requirements.txt": "fastapi>=0.100.0\nuvicorn\n",
        }
    )

    result = runner.invoke(app, ["doctor", str(repo), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "checks" in data
    req_names = [c["name"] for c in data["checks"] if c["required"]]
    assert "python" in req_names


def test_cli_doctor_nonexistent_directory(tmp_path):
    nonexistent = tmp_path / "does_not_exist"
    result = runner.invoke(app, ["doctor", str(nonexistent)])
    assert result.exit_code == 1
    assert "Error: Directory" in result.output

