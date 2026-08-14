"""Unit tests for repository security, token redaction, and CLI integration."""

from typer.testing import CliRunner
from runrepo.cli import app
from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.repository.git import GitManager
from runrepo.repository.manager import RepositoryManager
from runrepo.repository.models import RepositorySource, RepositoryTarget

runner = CliRunner()


def test_sanitize_git_output_masks_embedded_credentials():
    raw = "fatal: repository 'https://ghp_1234567890abcdef1234567890abcdef1234@github.com/secret/repo.git' not found"
    sanitized = GitManager.sanitize_git_output(raw)
    assert sanitized is not None
    assert "ghp_1234567890abcdef" not in sanitized
    assert "******@github.com" in sanitized


def test_sanitize_git_output_masks_user_password():
    raw = "fatal: Authentication failed for 'https://myuser:mypassword123@github.com/owner/repo.git'"
    sanitized = GitManager.sanitize_git_output(raw)
    assert sanitized is not None
    assert "mypassword123" not in sanitized
    assert "https://******@github.com" in sanitized


def test_cli_clone_command_json_output(tmp_path, monkeypatch):
    # Mock RepositoryManager resolve
    def mock_resolve(self, target, refresh=False):
        t = RepositoryTarget(
            source=RepositorySource.GITHUB_SHORTHAND,
            raw_input=target,
            owner="fastapi",
            name="fastapi",
            local_path=tmp_path / "fastapi_fastapi",
        )
        from runrepo.repository.models import RepositoryResult
        return RepositoryResult(
            success=True,
            target=t,
            local_path=tmp_path / "fastapi_fastapi",
        )

    monkeypatch.setattr(RepositoryManager, "resolve", mock_resolve)

    result = runner.invoke(app, ["clone", "fastapi/fastapi", "--json"])
    assert result.exit_code == 0
    assert '"success": true' in result.output
    assert '"owner": "fastapi"' in result.output
