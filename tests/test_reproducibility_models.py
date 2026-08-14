"""Unit tests for RunRepoConfig and RunRepoLock domain models."""

import json
from runrepo.reproducibility.models import (
    PlatformLockInfo,
    RepositoryLockInfo,
    ResolvedEnvLock,
    ResolvedServiceLock,
    ResolvedStartupLock,
    RunRepoConfig,
    RunRepoLock,
    ServiceConfigOverride,
)


def test_runrepo_config_serialization():
    config = RunRepoConfig(
        name="my-app",
        runtimes={"node": ">=20"},
        package_manager="pnpm",
        docker=True,
        services={
            "postgres": ServiceConfigOverride(
                image="postgres:16-alpine",
                port=5432,
                database_name="app_db",
            )
        },
    )

    data = json.loads(config.model_dump_json())
    assert data["name"] == "my-app"
    assert data["package_manager"] == "pnpm"
    assert data["services"]["postgres"]["image"] == "postgres:16-alpine"
    assert data["services"]["postgres"]["port"] == 5432


def test_runrepo_lock_serialization():
    lock = RunRepoLock(
        repository=RepositoryLockInfo(
            name="test-repo",
            commit_hash="abc1234",
            ref="main",
        ),
        platform=PlatformLockInfo(os="windows", arch="x86_64"),
        resolved_runtimes={"node": "20.11.0", "python": "3.12.2"},
        resolved_package_manager="pnpm",
        resolved_services=[
            ResolvedServiceLock(
                name="postgres",
                image="postgres:16",
                port=5432,
            )
        ],
        resolved_environment=[
            ResolvedEnvLock(
                name="PORT",
                category="local_default",
                source="local_default",
                is_secret=False,
            )
        ],
        resolved_startup=ResolvedStartupLock(command=["pnpm", "run", "dev"]),
        plan_steps=["install-deps", "service-postgres", "start-app"],
    )

    data = json.loads(lock.model_dump_json())
    assert data["lock_version"] == 1
    assert data["repository"]["name"] == "test-repo"
    assert data["resolved_runtimes"]["node"] == "20.11.0"
    assert len(data["plan_steps"]) == 3
