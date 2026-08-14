"""Unit tests for GitManager using MockProcessExecutor."""

from pathlib import Path
from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.repository.git import GitManager
from runrepo.repository.models import CloneStatus, RepositorySource, RepositoryTarget


def test_verify_git_installed_success():
    mock_executor = MockProcessExecutor(default_result=ProcessExecutionResult(stdout="git version 2.44.0", exit_code=0))
    git_manager = GitManager(executor=mock_executor)

    assert git_manager.verify_git_installed() is True
    assert mock_executor.executed_commands[0][0] == ["git", "--version"]


def test_verify_git_installed_failure():
    mock_executor = MockProcessExecutor(default_result=ProcessExecutionResult(exit_code=1))
    git_manager = GitManager(executor=mock_executor)

    assert git_manager.verify_git_installed() is False


def test_verify_repository_valid_success(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    mock_executor = MockProcessExecutor(default_result=ProcessExecutionResult(stdout="true\n", exit_code=0))
    git_manager = GitManager(executor=mock_executor)

    assert git_manager.verify_repository_valid(tmp_path) is True


def test_git_clone_success(tmp_path):
    dest = tmp_path / "cloned_repo"
    target = RepositoryTarget(
        source=RepositorySource.GITHUB_HTTPS,
        raw_input="https://github.com/test/repo",
        owner="test",
        name="repo",
        clone_url="https://github.com/test/repo.git",
    )

    def side_effect(cmd, cwd=None, env=None, timeout=None):
        if "rev-parse" in cmd:
            return ProcessExecutionResult(stdout="true\n", exit_code=0)
        # Create directory on clone
        dest.mkdir(parents=True, exist_ok=True)
        (dest / ".git").mkdir()
        return ProcessExecutionResult(stdout="Cloning into destination...\n", exit_code=0)

    mock_executor = MockProcessExecutor(side_effect=side_effect)
    git_manager = GitManager(executor=mock_executor)

    res = git_manager.clone(target, dest, depth=1)

    assert res.success is True
    assert res.target.status == CloneStatus.CLONED
    assert res.local_path == dest


def test_git_clone_failure_cleans_up_destination(tmp_path):
    dest = tmp_path / "failed_repo"
    target = RepositoryTarget(
        source=RepositorySource.GITHUB_HTTPS,
        raw_input="https://github.com/test/private_repo",
        owner="test",
        name="private_repo",
        clone_url="https://github.com/test/private_repo.git",
    )

    def side_effect(cmd, cwd=None, env=None, timeout=None):
        # Create partial files
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "partial_file.txt").write_text("corrupted", encoding="utf-8")
        return ProcessExecutionResult(stderr="fatal: Authentication failed for 'https://github.com/test/private_repo.git'", exit_code=128)

    mock_executor = MockProcessExecutor(side_effect=side_effect)
    git_manager = GitManager(executor=mock_executor)

    res = git_manager.clone(target, dest, depth=1)

    assert res.success is False
    assert res.target.status == CloneStatus.FAILED
    assert not dest.exists()  # Cleaned up
    assert "Authentication failed" in (res.error_message or "")
