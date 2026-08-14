"""Unit tests for ReproducibilityComparator detecting environment, package manager, and service drift."""

from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.models import PackageManagerInfo, ProjectInfo, ProjectScript, ProjectType
from runrepo.reproducibility.comparator import ReproducibilityComparator
from runrepo.reproducibility.models import (
    PlatformLockInfo,
    RepositoryLockInfo,
    ResolvedStartupLock,
    RunRepoLock,
)


def test_comparator_detects_no_changes():
    lock = RunRepoLock(
        repository=RepositoryLockInfo(name="test"),
        platform=PlatformLockInfo(os="windows", arch="x86_64"),
        resolved_package_manager="pnpm",
        resolved_startup=ResolvedStartupLock(command=["pnpm", "dev"]),
    )

    project_info = ProjectInfo(
        path=".",
        name="test",
        project_type=ProjectType.WEB_APPLICATION,
        package_managers=[PackageManagerInfo(name="pnpm")],
        scripts=[ProjectScript(name="dev", command="pnpm dev")],
    )

    diff = ReproducibilityComparator.compare(
        project_info=project_info,
        environment_state=None,
        execution_plan=None,
        lock=lock,
    )

    assert diff.has_changes is False
    assert len(diff.warnings) == 0


def test_comparator_detects_package_manager_drift():
    lock = RunRepoLock(
        repository=RepositoryLockInfo(name="test"),
        platform=PlatformLockInfo(os="windows", arch="x86_64"),
        resolved_package_manager="pnpm",
    )

    # Current repo has npm instead of pnpm
    project_info = ProjectInfo(
        path=".",
        name="test",
        package_managers=[PackageManagerInfo(name="npm")],
    )

    diff = ReproducibilityComparator.compare(
        project_info=project_info,
        environment_state=None,
        execution_plan=None,
        lock=lock,
    )

    assert diff.has_changes is True
    assert diff.package_manager_diff == ("pnpm", "npm")
    assert any("Package manager drifted" in w for w in diff.warnings)


def test_comparator_detects_runtime_version_drift():
    lock = RunRepoLock(
        repository=RepositoryLockInfo(name="test"),
        platform=PlatformLockInfo(os="windows", arch="x86_64"),
        resolved_runtimes={"node": "20.10.0"},
    )

    project_info = ProjectInfo(path=".", name="test")
    env_state = EnvironmentState(
        platform="windows",
        architecture="x86_64",
        checks=[
            EnvironmentCheck(
                name="node",
                status=EnvironmentStatus.OK,
                installed_version="22.1.0",
            )
        ],
    )

    diff = ReproducibilityComparator.compare(
        project_info=project_info,
        environment_state=env_state,
        execution_plan=None,
        lock=lock,
    )

    assert diff.has_changes is True
    assert "node" in diff.runtime_diffs
    assert diff.runtime_diffs["node"] == ("20.10.0", "22.1.0")
