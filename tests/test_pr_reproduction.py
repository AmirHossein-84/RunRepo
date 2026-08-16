"""Tests for GitHub Pull Request URL parsing, cloning, and reproduction."""

from pathlib import Path
import pytest
from runrepo.executor.process import ProcessExecutionResult, ProcessExecutor
from runrepo.repository.github import GitHubUrlParser
from runrepo.repository.models import PullRequestTarget, RepositorySource
from runrepo.reproduce.pr import PullRequestRunner


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
        if "git clone" in cmd_str or "git init" in cmd_str or "git remote" in cmd_str or "git fetch" in cmd_str or "git checkout" in cmd_str:
            return ProcessExecutionResult(exit_code=0, stdout="git ok", stderr="")
        if "pytest" in cmd_str or "test" in cmd_str:
            return ProcessExecutionResult(exit_code=0, stdout="1 passed in 0.05s", stderr="")
        return ProcessExecutionResult(exit_code=0, stdout="", stderr="")

    def start_background(self, command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> Any:
        return None


def test_parse_pr_url_variations() -> None:
    pr1 = GitHubUrlParser.parse_pull_request("https://github.com/fastapi/fastapi/pull/1234")
    assert pr1.owner == "fastapi"
    assert pr1.repo == "fastapi"
    assert pr1.pr_number == 1234
    assert pr1.ref == "pull/1234/head"

    pr2 = GitHubUrlParser.parse_pull_request("github.com/pallets/flask/pull/567")
    assert pr2.owner == "pallets"
    assert pr2.repo == "flask"
    assert pr2.pr_number == 567

    pr3 = GitHubUrlParser.parse_pull_request("facebook/react#999")
    assert pr3.owner == "facebook"
    assert pr3.repo == "react"
    assert pr3.pr_number == 999


def test_parse_invalid_pr_url() -> None:
    with pytest.raises(ValueError, match="Invalid GitHub Pull Request URL"):
        GitHubUrlParser.parse_pull_request("https://github.com/fastapi/fastapi/issues/123")


def test_pr_runner_execution(tmp_path: Path) -> None:
    pr_dir = tmp_path / "pr_test_repo"
    pr_dir.mkdir()
    (pr_dir / "pyproject.toml").write_text('[project]\nname="test-pr"\nversion="0.1.0"', encoding="utf-8")
    (pr_dir / "tests").mkdir()
    (pr_dir / "tests" / "test_sample.py").write_text("def test_ok(): pass", encoding="utf-8")

    from runrepo.repository.manager import RepositoryManager
    from runrepo.repository.models import RepositoryResult, RepositoryTarget

    mock_exec = MockExecutor()
    runner = PullRequestRunner(executor=mock_exec)

    # Monkeypatch resolve_pull_request to point to local test directory
    target = RepositoryTarget(
        source=RepositorySource.GITHUB_PR,
        raw_input="https://github.com/test/repo/pull/10",
        owner="test",
        name="repo",
        branch="pr-10",
        local_path=pr_dir,
    )
    runner.repo_manager.resolve_pull_request = lambda url, refresh=False: RepositoryResult(
        success=True,
        target=target,
        local_path=pr_dir,
    )

    report = runner.reproduce("https://github.com/test/repo/pull/10", run_tests=True, start_app=False)
    assert report.setup_successful is True
    assert report.owner == "test"
    assert report.repo == "repo"
    assert report.pr_number == 10
    assert report.all_tests_passed is True
    assert len(report.test_results) == 1
    assert "pytest" in report.test_results[0].command[0] or "pytest" in report.test_results[0].command[-1]
