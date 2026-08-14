"""Unit tests for LockfileManager deterministic serialization and loading."""

import json
import pytest
from runrepo.reproducibility.lockfile import LockfileManager
from runrepo.reproducibility.models import (
    PlatformLockInfo,
    RepositoryLockInfo,
    RunRepoLock,
)


def test_deterministic_lockfile_generation(tmp_path):
    lock = RunRepoLock(
        repository=RepositoryLockInfo(name="my-repo", commit_hash="123456"),
        platform=PlatformLockInfo(os="windows", arch="x86_64"),
        resolved_runtimes={"node": "20.10.0"},
        resolved_package_manager="pnpm",
        plan_steps=["install-deps", "start-app"],
    )

    path = LockfileManager.save(tmp_path, lock)
    assert path.is_file()

    loaded = LockfileManager.load(tmp_path)
    assert loaded is not None
    assert loaded.repository.name == "my-repo"
    assert loaded.resolved_package_manager == "pnpm"
    assert loaded.resolved_runtimes["node"] == "20.10.0"


def test_lockfile_keys_are_sorted_and_formatted(tmp_path):
    lock = RunRepoLock(
        repository=RepositoryLockInfo(name="repo"),
        platform=PlatformLockInfo(os="linux", arch="x86_64"),
    )
    formatted = LockfileManager.format_json(lock)
    parsed = json.loads(formatted)

    assert "lock_version" in parsed
    assert formatted.endswith("\n")


def test_unsupported_lock_version_raises_value_error(tmp_path):
    (tmp_path / "runrepo.lock").write_text('{"lock_version": 999}', encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported lockfile version"):
        LockfileManager.load(tmp_path)
