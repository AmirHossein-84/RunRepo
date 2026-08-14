"""Unit tests for RepositoryManager cache reuse and deterministic storage."""

from pathlib import Path
from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.repository.manager import RepositoryManager
from runrepo.repository.models import CloneStatus, RepositorySource


def test_repository_manager_resolves_local_path(tmp_path):
    manager = RepositoryManager(cache_dir=tmp_path / "cache")
    result = manager.resolve(tmp_path)

    assert result.success is True
    assert result.target.source == RepositorySource.LOCAL
    assert result.local_path == tmp_path.resolve()


def test_repository_manager_reuses_valid_cached_clone(tmp_path):
    cache_dir = tmp_path / "cache"
    cached_repo = cache_dir / "fastapi_fastapi"
    cached_repo.mkdir(parents=True, exist_ok=True)
    (cached_repo / ".git").mkdir()

    def side_effect(cmd, cwd=None, env=None, timeout=None):
        if "rev-parse" in cmd:
            return ProcessExecutionResult(stdout="true\n", exit_code=0)
        return ProcessExecutionResult(exit_code=0)

    mock_executor = MockProcessExecutor(side_effect=side_effect)
    manager = RepositoryManager(cache_dir=cache_dir, executor=mock_executor)

    result = manager.resolve("fastapi/fastapi")

    assert result.success is True
    assert result.target.status == CloneStatus.CACHED
    assert result.local_path == cached_repo.resolve()
    # No clone command executed since cache was valid
    assert not any("clone" in cmd[0] for cmd in mock_executor.executed_commands)


def test_repository_manager_refresh_forces_reclone(tmp_path):
    cache_dir = tmp_path / "cache"
    cached_repo = cache_dir / "fastapi_fastapi"
    cached_repo.mkdir(parents=True, exist_ok=True)
    (cached_repo / ".git").mkdir()

    def side_effect(cmd, cwd=None, env=None, timeout=None):
        if "clone" in cmd:
            cached_repo.mkdir(parents=True, exist_ok=True)
            (cached_repo / ".git").mkdir()
            return ProcessExecutionResult(stdout="Cloned\n", exit_code=0)
        if "rev-parse" in cmd:
            return ProcessExecutionResult(stdout="true\n", exit_code=0)
        return ProcessExecutionResult(exit_code=0)

    mock_executor = MockProcessExecutor(side_effect=side_effect)
    manager = RepositoryManager(cache_dir=cache_dir, executor=mock_executor)

    result = manager.resolve("fastapi/fastapi", refresh=True)

    assert result.success is True
    assert any("clone" in cmd[0] for cmd in mock_executor.executed_commands)
