"""CLI tests for runrepo analyze."""

import json
from typer.testing import CliRunner

from runrepo.cli import app

runner = CliRunner()


def test_cli_analyze_rich(create_fixture_repo):
    repo = create_fixture_repo(
        {
            ".nvmrc": "22.0.0\n",
            "package.json": '{"name": "test-repo", "dependencies": {"next": "14.2.0"}}',
        }
    )

    result = runner.invoke(app, ["analyze", str(repo)])
    assert result.exit_code == 0
    assert "RunRepo Analysis" in result.stdout
    assert "test-repo" in result.stdout
    assert "node" in result.stdout or "Node" in result.stdout


def test_cli_analyze_json(create_fixture_repo):
    repo = create_fixture_repo(
        {
            ".python-version": "3.12.0\n",
            "requirements.txt": "fastapi>=0.100.0\n",
        }
    )

    result = runner.invoke(app, ["analyze", str(repo), "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert "runtimes" in data
    assert any(r["name"] == "python" and r["version"] == "3.12.0" for r in data["runtimes"])
    assert any(f["name"] == "FastAPI" for f in data["frameworks"])


def test_cli_analyze_evidence(create_fixture_repo):
    repo = create_fixture_repo(
        {
            ".nvmrc": "20.0.0\n",
            "package.json": '{"name": "ev-repo"}',
        }
    )

    result = runner.invoke(app, ["analyze", str(repo), "--evidence"])
    assert result.exit_code == 0
    assert "Detection Evidence Breakdown" in result.stdout
    assert ".nvmrc" in result.stdout


def test_cli_analyze_nonexistent_dir(tmp_path):
    nonexistent = tmp_path / "does_not_exist"
    result = runner.invoke(app, ["analyze", str(nonexistent)])
    assert result.exit_code == 1
    assert "does not exist" in result.stdout
