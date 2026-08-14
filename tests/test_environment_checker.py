"""Integration tests for EnvironmentChecker with ProjectInfo scenarios."""

from runrepo.environment.checker import EnvironmentChecker
from runrepo.environment.command import CommandResult, MockCommandRunner
from runrepo.environment.models import EnvironmentStatus
from runrepo.models import (
    Confidence,
    DetectionEvidence,
    DockerInfo,
    PackageManagerInfo,
    ProjectInfo,
    RuntimeInfo,
    SubprojectInfo,
)


def test_environment_checker_node_pnpm_satisfied():
    mock_runner = MockCommandRunner(
        responses={
            ("git", "--version"): CommandResult(stdout="git version 2.45.0", stderr="", exit_code=0, duration_ms=5.0),
            ("node", "--version"): CommandResult(stdout="v22.15.0", stderr="", exit_code=0, duration_ms=5.0),
            ("pnpm", "--version"): CommandResult(stdout="9.5.0", stderr="", exit_code=0, duration_ms=5.0),
        }
    )

    ev = [DetectionEvidence(source="package.json", detail="engines.node: >=22", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="my-app",
        runtimes=[RuntimeInfo(name="node", version=">=22", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", version="9.5.0", evidence=ev)],
    )

    checker = EnvironmentChecker(runner=mock_runner)
    state = checker.check_environment(project)

    assert state.is_satisfied is True
    assert len(state.missing_checks) == 0
    assert len(state.wrong_version_checks) == 0
    assert len(state.broken_checks) == 0

    node_chk = next(c for c in state.checks if c.name == "node")
    assert node_chk.required is True
    assert node_chk.status == EnvironmentStatus.OK
    assert node_chk.installed_version == "22.15.0"

    pnpm_chk = next(c for c in state.checks if c.name == "pnpm")
    assert pnpm_chk.required is True
    assert pnpm_chk.status == EnvironmentStatus.OK


def test_environment_checker_node_wrong_version():
    mock_runner = MockCommandRunner(
        responses={
            ("git", "--version"): CommandResult(stdout="git version 2.45.0", stderr="", exit_code=0, duration_ms=5.0),
            ("node", "--version"): CommandResult(stdout="v18.19.0", stderr="", exit_code=0, duration_ms=5.0),
            ("pnpm", "--version"): CommandResult(stdout="9.5.0", stderr="", exit_code=0, duration_ms=5.0),
        }
    )

    ev = [DetectionEvidence(source="package.json", detail="engines.node: >=22", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="my-app",
        runtimes=[RuntimeInfo(name="node", version=">=22", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
    )

    checker = EnvironmentChecker(runner=mock_runner)
    state = checker.check_environment(project)

    assert state.is_satisfied is False
    assert "node" in state.wrong_version_checks


def test_environment_checker_python_uv_missing():
    mock_runner = MockCommandRunner(
        responses={
            ("git", "--version"): CommandResult(stdout="git version 2.45.0", stderr="", exit_code=0, duration_ms=5.0),
            ("python", "--version"): CommandResult(stdout="Python 3.12.3", stderr="", exit_code=0, duration_ms=5.0),
            # uv is not in responses, returns 127
        }
    )

    project = ProjectInfo(
        path="/repo",
        name="py-app",
        runtimes=[RuntimeInfo(name="python", version=">=3.11")],
        package_managers=[PackageManagerInfo(name="uv")],
    )

    checker = EnvironmentChecker(runner=mock_runner)
    state = checker.check_environment(project)

    assert state.is_satisfied is False
    assert "uv" in state.missing_checks


def test_environment_checker_docker_broken_daemon():
    mock_runner = MockCommandRunner(
        responses={
            ("git", "--version"): CommandResult(stdout="git version 2.45.0", stderr="", exit_code=0, duration_ms=5.0),
            ("node", "--version"): CommandResult(stdout="v22.0.0", stderr="", exit_code=0, duration_ms=5.0),
            ("npm", "--version"): CommandResult(stdout="10.8.0", stderr="", exit_code=0, duration_ms=5.0),
            ("docker", "--version"): CommandResult(stdout="Docker version 28.0.0", stderr="", exit_code=0, duration_ms=5.0),
            ("docker", "info"): CommandResult(stdout="", stderr="Cannot connect to docker daemon", exit_code=1, duration_ms=5.0),
            ("docker", "compose", "version"): CommandResult(stdout="Docker Compose version v2.27.0", stderr="", exit_code=0, duration_ms=5.0),
        }
    )

    project = ProjectInfo(
        path="/repo",
        name="docker-app",
        runtimes=[RuntimeInfo(name="node", version="22")],
        package_managers=[PackageManagerInfo(name="npm")],
        docker=DockerInfo(has_dockerfile=True, compose_files=["compose.yaml"]),
    )

    checker = EnvironmentChecker(runner=mock_runner)
    state = checker.check_environment(project)

    assert state.is_satisfied is False
    assert "docker" in state.broken_checks
    assert "docker-compose" in state.broken_checks


def test_environment_checker_polyglot_subprojects():
    mock_runner = MockCommandRunner(
        responses={
            ("git", "--version"): CommandResult(stdout="git version 2.45.0", stderr="", exit_code=0, duration_ms=5.0),
            ("node", "--version"): CommandResult(stdout="v22.15.0", stderr="", exit_code=0, duration_ms=5.0),
            ("pnpm", "--version"): CommandResult(stdout="9.5.0", stderr="", exit_code=0, duration_ms=5.0),
            ("python", "--version"): CommandResult(stdout="Python 3.12.3", stderr="", exit_code=0, duration_ms=5.0, executable="/bin/python3"),
            ("/bin/python3", "-m", "pip", "--version"): CommandResult(stdout="pip 24.0", stderr="", exit_code=0, duration_ms=5.0),
        }
    )

    sp_frontend = SubprojectInfo(
        name="frontend",
        path="frontend",
        runtimes=[RuntimeInfo(name="node", version=">=22")],
        package_managers=[PackageManagerInfo(name="pnpm")],
    )
    sp_backend = SubprojectInfo(
        name="backend",
        path="backend",
        runtimes=[RuntimeInfo(name="python", version=">=3.11")],
        package_managers=[PackageManagerInfo(name="pip")],
    )

    project = ProjectInfo(
        path="/repo",
        name="fullstack",
        subprojects=[sp_frontend, sp_backend],
    )

    checker = EnvironmentChecker(runner=mock_runner)
    state = checker.check_environment(project)

    assert state.is_satisfied is True
    check_names = {c.name for c in state.checks if c.required}
    assert "node" in check_names
    assert "python" in check_names
    assert "pnpm" in check_names
    assert "pip" in check_names


def test_environment_checker_host_mode():
    mock_runner = MockCommandRunner(
        responses={
            ("git", "--version"): CommandResult(stdout="git version 2.45.0", stderr="", exit_code=0, duration_ms=5.0),
            ("node", "--version"): CommandResult(stdout="v22.0.0", stderr="", exit_code=0, duration_ms=5.0),
            ("python", "--version"): CommandResult(stdout="Python 3.12.0", stderr="", exit_code=0, duration_ms=5.0),
            ("npm", "--version"): CommandResult(stdout="10.8.0", stderr="", exit_code=0, duration_ms=5.0),
            ("pnpm", "--version"): CommandResult(stdout="9.5.0", stderr="", exit_code=0, duration_ms=5.0),
            ("yarn", "--version"): CommandResult(stdout="1.22.0", stderr="", exit_code=0, duration_ms=5.0),
            ("pip", "--version"): CommandResult(stdout="pip 24.0", stderr="", exit_code=0, duration_ms=5.0),
            ("uv", "--version"): CommandResult(stdout="uv 0.12.0", stderr="", exit_code=0, duration_ms=5.0),
            ("docker", "--version"): CommandResult(stdout="Docker version 28.0.0", stderr="", exit_code=0, duration_ms=5.0),
            ("docker", "info"): CommandResult(stdout="Server Version: 28.0.0", stderr="", exit_code=0, duration_ms=5.0),
            ("docker", "compose", "version"): CommandResult(stdout="Docker Compose version v2.27.0", stderr="", exit_code=0, duration_ms=5.0),
        }
    )

    checker = EnvironmentChecker(runner=mock_runner)
    state = checker.check_environment(None)

    assert len(state.checks) >= 10
    assert all(c.required is False for c in state.checks)
    assert bool(state.platform)
    assert bool(state.architecture)
