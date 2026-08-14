"""Unit tests for individual tool checks using MockCommandRunner."""

from runrepo.environment.checks import (
    check_docker,
    check_docker_compose,
    check_git,
    check_node,
    check_npm,
    check_pip,
    check_pnpm,
    check_python,
    check_uv,
    check_yarn,
)
from runrepo.environment.command import CommandResult, MockCommandRunner
from runrepo.environment.models import EnvironmentStatus


def test_check_git():
    runner = MockCommandRunner(
        responses={
            ("git", "--version"): CommandResult(stdout="git version 2.51.0.windows.1", stderr="", exit_code=0, duration_ms=5.0, executable="C:\\Git\\git.exe")
        }
    )
    chk = check_git(runner)
    assert chk.status == EnvironmentStatus.OK
    assert chk.installed_version == "2.51.0"
    assert chk.executable_path == "C:\\Git\\git.exe"

    runner_missing = MockCommandRunner()
    chk_missing = check_git(runner_missing)
    assert chk_missing.status == EnvironmentStatus.MISSING


def test_check_node():
    runner = MockCommandRunner(
        responses={
            ("node", "--version"): CommandResult(stdout="v22.15.0", stderr="", exit_code=0, duration_ms=5.0, executable="/bin/node")
        }
    )

    # Valid requirement
    chk_ok = check_node(runner, required=True, required_version=">=22")
    assert chk_ok.status == EnvironmentStatus.OK
    assert chk_ok.installed_version == "22.15.0"

    # Incompatible requirement
    chk_wrong = check_node(runner, required=True, required_version=">=24")
    assert chk_wrong.status == EnvironmentStatus.WRONG_VERSION

    # Missing Node
    runner_missing = MockCommandRunner()
    chk_missing = check_node(runner_missing, required=True)
    assert chk_missing.status == EnvironmentStatus.MISSING


def test_check_python():
    runner = MockCommandRunner(
        responses={
            ("python", "--version"): CommandResult(stdout="Python 3.12.3", stderr="", exit_code=0, duration_ms=5.0, executable="/usr/bin/python3")
        }
    )

    chk_ok, py_exe = check_python(runner, required=True, required_version=">=3.11")
    assert chk_ok.status == EnvironmentStatus.OK
    assert chk_ok.installed_version == "3.12.3"
    assert py_exe == "/usr/bin/python3"

    chk_wrong, _ = check_python(runner, required=True, required_version=">=3.14")
    assert chk_wrong.status == EnvironmentStatus.WRONG_VERSION

    runner_missing = MockCommandRunner()
    chk_missing, _ = check_python(runner_missing, required=True)
    assert chk_missing.status == EnvironmentStatus.MISSING


def test_check_pip_tied_to_python():
    runner = MockCommandRunner(
        responses={
            ("/usr/bin/python3", "-m", "pip", "--version"): CommandResult(
                stdout="pip 24.0 from /usr/lib/python3.12/site-packages/pip",
                stderr="",
                exit_code=0,
                duration_ms=10.0,
                executable="/usr/bin/python3",
            )
        }
    )

    chk = check_pip(runner, python_executable="/usr/bin/python3", required=True)
    assert chk.status == EnvironmentStatus.OK
    assert chk.installed_version == "24.0"


def test_check_package_managers():
    runner = MockCommandRunner(
        responses={
            ("npm", "--version"): CommandResult(stdout="10.8.2", stderr="", exit_code=0, duration_ms=5.0),
            ("pnpm", "--version"): CommandResult(stdout="9.5.0", stderr="", exit_code=0, duration_ms=5.0),
            ("yarn", "--version"): CommandResult(stdout="1.22.19", stderr="", exit_code=0, duration_ms=5.0),
            ("uv", "--version"): CommandResult(stdout="uv 0.12.0", stderr="", exit_code=0, duration_ms=5.0),
        }
    )

    assert check_npm(runner, required=True).status == EnvironmentStatus.OK
    assert check_pnpm(runner, required=True).status == EnvironmentStatus.OK
    assert check_yarn(runner, required=True).status == EnvironmentStatus.OK
    assert check_uv(runner, required=True).status == EnvironmentStatus.OK


def test_check_docker_operational_states():
    # Case 1: Docker CLI missing
    runner_missing = MockCommandRunner()
    chk_missing = check_docker(runner_missing, required=True)
    assert chk_missing.status == EnvironmentStatus.MISSING

    # Case 2: Docker CLI installed, but daemon is down / unreachable
    runner_daemon_down = MockCommandRunner(
        responses={
            ("docker", "--version"): CommandResult(stdout="Docker version 28.3.0, build 332d431", stderr="", exit_code=0, duration_ms=5.0, executable="C:\\Docker\\docker.exe"),
            ("docker", "info"): CommandResult(stdout="", stderr="Cannot connect to the Docker daemon", exit_code=1, duration_ms=10.0),
        }
    )
    chk_broken = check_docker(runner_daemon_down, required=True)
    assert chk_broken.status == EnvironmentStatus.BROKEN
    assert chk_broken.installed_version == "28.3.0"
    assert "daemon is not running" in (chk_broken.details or "")

    # Case 3: Docker fully operational
    runner_ok = MockCommandRunner(
        responses={
            ("docker", "--version"): CommandResult(stdout="Docker version 28.3.0, build 332d431", stderr="", exit_code=0, duration_ms=5.0, executable="C:\\Docker\\docker.exe"),
            ("docker", "info"): CommandResult(stdout="Server Version: 28.3.0", stderr="", exit_code=0, duration_ms=15.0),
        }
    )
    chk_ok = check_docker(runner_ok, required=True)
    assert chk_ok.status == EnvironmentStatus.OK
    assert chk_ok.installed_version == "28.3.0"


def test_check_docker_compose():
    runner_plugin = MockCommandRunner(
        responses={
            ("docker", "compose", "version"): CommandResult(stdout="Docker Compose version v2.27.0", stderr="", exit_code=0, duration_ms=5.0, executable="docker"),
        }
    )
    chk_plugin = check_docker_compose(runner_plugin, docker_status=EnvironmentStatus.OK, required=True)
    assert chk_plugin.status == EnvironmentStatus.OK
    assert chk_plugin.installed_version == "2.27.0"

    # Daemon down makes compose broken
    chk_broken_compose = check_docker_compose(runner_plugin, docker_status=EnvironmentStatus.BROKEN, required=True)
    assert chk_broken_compose.status == EnvironmentStatus.BROKEN
