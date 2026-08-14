"""Individual tool probe functions for Git, Node, Python, Package Managers, and Docker."""

from runrepo.environment.command import CommandRunner
from runrepo.environment.models import EnvironmentCheck, EnvironmentStatus
from runrepo.environment.version import clean_version_string, evaluate_version_requirement
from runrepo.models.evidence import DetectionEvidence


def check_git(runner: CommandRunner) -> EnvironmentCheck:
    """Inspect Git CLI presence and version."""
    res = runner.run(["git", "--version"])
    if not res.success or not res.stdout:
        return EnvironmentCheck(
            name="git",
            status=EnvironmentStatus.MISSING,
            details="Git executable not found on system PATH",
        )

    v = clean_version_string(res.stdout)
    return EnvironmentCheck(
        name="git",
        status=EnvironmentStatus.OK,
        installed_version=v,
        executable_path=res.executable,
        details=f"Git version {v}",
    )


def check_node(
    runner: CommandRunner,
    required: bool = False,
    required_version: str | None = None,
    evidence: list[DetectionEvidence] | None = None,
) -> EnvironmentCheck:
    """Inspect Node.js runtime presence and evaluate version requirement."""
    res = runner.run(["node", "--version"])
    ev_list = evidence or []

    if not res.success or not res.stdout:
        return EnvironmentCheck(
            name="node",
            status=EnvironmentStatus.MISSING,
            required=required,
            required_version=required_version,
            details="Node.js executable not found on system PATH",
            evidence=ev_list,
        )

    v = clean_version_string(res.stdout)
    sat = evaluate_version_requirement(v, required_version)

    if sat is True:
        status = EnvironmentStatus.OK
        details = f"Node.js {v} satisfies requirement {required_version}" if required_version else f"Node.js {v}"
    elif sat is False:
        status = EnvironmentStatus.WRONG_VERSION
        details = f"Installed Node.js ({v}) does not satisfy required {required_version}"
    else:
        status = EnvironmentStatus.UNKNOWN
        details = f"Could not reliably evaluate Node version requirement: {required_version}"

    return EnvironmentCheck(
        name="node",
        status=status,
        required=required,
        required_version=required_version,
        installed_version=v,
        executable_path=res.executable,
        details=details,
        evidence=ev_list,
    )


def check_python(
    runner: CommandRunner,
    required: bool = False,
    required_version: str | None = None,
    evidence: list[DetectionEvidence] | None = None,
) -> tuple[EnvironmentCheck, str | None]:
    """Inspect Python interpreter presence and evaluate version requirement.

    Returns the EnvironmentCheck and the resolved python executable path for pip to use.
    """
    ev_list = evidence or []
    res = runner.run(["python", "--version"])

    # If 'python' fails, try 'python3' on Linux/macOS or 'py' on Windows
    if not res.success or not res.stdout:
        res_py3 = runner.run(["python3", "--version"])
        if res_py3.success and res_py3.stdout:
            res = res_py3
        else:
            res_py = runner.run(["py", "-0"])
            if res_py.success:
                res = runner.run(["py", "--version"])

    if not res.success or not res.stdout:
        return (
            EnvironmentCheck(
                name="python",
                status=EnvironmentStatus.MISSING,
                required=required,
                required_version=required_version,
                details="Python interpreter not found on system PATH",
                evidence=ev_list,
            ),
            None,
        )

    v = clean_version_string(res.stdout)
    sat = evaluate_version_requirement(v, required_version)

    if sat is True:
        status = EnvironmentStatus.OK
        details = f"Python {v} satisfies requirement {required_version}" if required_version else f"Python {v}"
    elif sat is False:
        status = EnvironmentStatus.WRONG_VERSION
        details = f"Installed Python ({v}) does not satisfy required {required_version}"
    else:
        status = EnvironmentStatus.UNKNOWN
        details = f"Could not reliably evaluate Python version requirement: {required_version}"

    check = EnvironmentCheck(
        name="python",
        status=status,
        required=required,
        required_version=required_version,
        installed_version=v,
        executable_path=res.executable,
        details=details,
        evidence=ev_list,
    )
    return check, res.executable


def check_npm(
    runner: CommandRunner,
    required: bool = False,
    required_version: str | None = None,
    evidence: list[DetectionEvidence] | None = None,
) -> EnvironmentCheck:
    """Inspect npm package manager."""
    res = runner.run(["npm", "--version"])
    ev_list = evidence or []

    if not res.success or not res.stdout:
        return EnvironmentCheck(
            name="npm",
            status=EnvironmentStatus.MISSING,
            required=required,
            required_version=required_version,
            details="npm not found on system PATH",
            evidence=ev_list,
        )

    v = clean_version_string(res.stdout)
    sat = evaluate_version_requirement(v, required_version)
    status = EnvironmentStatus.OK if sat is True else (EnvironmentStatus.WRONG_VERSION if sat is False else EnvironmentStatus.UNKNOWN)

    return EnvironmentCheck(
        name="npm",
        status=status,
        required=required,
        required_version=required_version,
        installed_version=v,
        executable_path=res.executable,
        details=f"npm {v}",
        evidence=ev_list,
    )


def check_pnpm(
    runner: CommandRunner,
    required: bool = False,
    required_version: str | None = None,
    evidence: list[DetectionEvidence] | None = None,
) -> EnvironmentCheck:
    """Inspect pnpm package manager."""
    res = runner.run(["pnpm", "--version"])
    ev_list = evidence or []

    if not res.success or not res.stdout:
        return EnvironmentCheck(
            name="pnpm",
            status=EnvironmentStatus.MISSING,
            required=required,
            required_version=required_version,
            details="pnpm not found on system PATH",
            evidence=ev_list,
        )

    v = clean_version_string(res.stdout)
    sat = evaluate_version_requirement(v, required_version)
    status = EnvironmentStatus.OK if sat is True else (EnvironmentStatus.WRONG_VERSION if sat is False else EnvironmentStatus.UNKNOWN)

    return EnvironmentCheck(
        name="pnpm",
        status=status,
        required=required,
        required_version=required_version,
        installed_version=v,
        executable_path=res.executable,
        details=f"pnpm {v}",
        evidence=ev_list,
    )


def check_yarn(
    runner: CommandRunner,
    required: bool = False,
    required_version: str | None = None,
    evidence: list[DetectionEvidence] | None = None,
) -> EnvironmentCheck:
    """Inspect yarn package manager."""
    res = runner.run(["yarn", "--version"])
    ev_list = evidence or []

    if not res.success or not res.stdout:
        return EnvironmentCheck(
            name="yarn",
            status=EnvironmentStatus.MISSING,
            required=required,
            required_version=required_version,
            details="yarn not found on system PATH",
            evidence=ev_list,
        )

    v = clean_version_string(res.stdout)
    sat = evaluate_version_requirement(v, required_version)
    status = EnvironmentStatus.OK if sat is True else (EnvironmentStatus.WRONG_VERSION if sat is False else EnvironmentStatus.UNKNOWN)

    return EnvironmentCheck(
        name="yarn",
        status=status,
        required=required,
        required_version=required_version,
        installed_version=v,
        executable_path=res.executable,
        details=f"yarn {v}",
        evidence=ev_list,
    )


def check_pip(
    runner: CommandRunner,
    python_executable: str | None = None,
    required: bool = False,
    required_version: str | None = None,
    evidence: list[DetectionEvidence] | None = None,
) -> EnvironmentCheck:
    """Inspect pip tied directly to the discovered Python interpreter."""
    ev_list = evidence or []
    if python_executable:
        res = runner.run([python_executable, "-m", "pip", "--version"])
    else:
        res = runner.run(["pip", "--version"])

    if not res.success or not res.stdout:
        return EnvironmentCheck(
            name="pip",
            status=EnvironmentStatus.MISSING,
            required=required,
            required_version=required_version,
            details="pip module not available for Python",
            evidence=ev_list,
        )

    v = clean_version_string(res.stdout)
    sat = evaluate_version_requirement(v, required_version)
    status = EnvironmentStatus.OK if sat is True else (EnvironmentStatus.WRONG_VERSION if sat is False else EnvironmentStatus.UNKNOWN)

    return EnvironmentCheck(
        name="pip",
        status=status,
        required=required,
        required_version=required_version,
        installed_version=v,
        executable_path=res.executable,
        details=f"pip {v}",
        evidence=ev_list,
    )


def check_uv(
    runner: CommandRunner,
    required: bool = False,
    required_version: str | None = None,
    evidence: list[DetectionEvidence] | None = None,
) -> EnvironmentCheck:
    """Inspect uv package manager."""
    res = runner.run(["uv", "--version"])
    ev_list = evidence or []

    if not res.success or not res.stdout:
        return EnvironmentCheck(
            name="uv",
            status=EnvironmentStatus.MISSING,
            required=required,
            required_version=required_version,
            details="uv not found on system PATH",
            evidence=ev_list,
        )

    v = clean_version_string(res.stdout)
    sat = evaluate_version_requirement(v, required_version)
    status = EnvironmentStatus.OK if sat is True else (EnvironmentStatus.WRONG_VERSION if sat is False else EnvironmentStatus.UNKNOWN)

    return EnvironmentCheck(
        name="uv",
        status=status,
        required=required,
        required_version=required_version,
        installed_version=v,
        executable_path=res.executable,
        details=f"uv {v}",
        evidence=ev_list,
    )


def check_docker(
    runner: CommandRunner,
    required: bool = False,
    evidence: list[DetectionEvidence] | None = None,
) -> EnvironmentCheck:
    """Inspect Docker CLI presence and daemon operational reachability."""
    ev_list = evidence or []
    cli_res = runner.run(["docker", "--version"])

    if not cli_res.success or not cli_res.stdout:
        return EnvironmentCheck(
            name="docker",
            status=EnvironmentStatus.MISSING,
            required=required,
            details="Docker CLI not found on system PATH",
            evidence=ev_list,
        )

    v = clean_version_string(cli_res.stdout)

    # Test daemon reachability
    info_res = runner.run(["docker", "info"], timeout_s=5.0)
    if not info_res.success:
        return EnvironmentCheck(
            name="docker",
            status=EnvironmentStatus.BROKEN,
            required=required,
            installed_version=v,
            executable_path=cli_res.executable,
            details="Docker CLI is installed, but the Docker daemon is not running or unreachable",
            evidence=ev_list,
        )

    return EnvironmentCheck(
        name="docker",
        status=EnvironmentStatus.OK,
        required=required,
        installed_version=v,
        executable_path=cli_res.executable,
        details=f"Docker {v} (daemon running and operational)",
        evidence=ev_list,
    )


def check_docker_compose(
    runner: CommandRunner,
    docker_status: EnvironmentStatus,
    required: bool = False,
    evidence: list[DetectionEvidence] | None = None,
) -> EnvironmentCheck:
    """Inspect Docker Compose presence via modern plugin or legacy standalone."""
    ev_list = evidence or []

    # First check modern 'docker compose version'
    plugin_res = runner.run(["docker", "compose", "version"])
    if plugin_res.success and plugin_res.stdout:
        v = clean_version_string(plugin_res.stdout)
        if docker_status == EnvironmentStatus.BROKEN:
            status = EnvironmentStatus.BROKEN
            details = "Docker Compose plugin is available, but the Docker daemon is unreachable"
        else:
            status = EnvironmentStatus.OK
            details = f"Docker Compose plugin {v}"

        return EnvironmentCheck(
            name="docker-compose",
            status=status,
            required=required,
            installed_version=v,
            executable_path=plugin_res.executable,
            details=details,
            evidence=ev_list,
        )

    # Fallback to standalone 'docker-compose version'
    standalone_res = runner.run(["docker-compose", "version"])
    if standalone_res.success and standalone_res.stdout:
        v = clean_version_string(standalone_res.stdout)
        if docker_status == EnvironmentStatus.BROKEN:
            status = EnvironmentStatus.BROKEN
            details = "Docker Compose standalone is available, but the Docker daemon is unreachable"
        else:
            status = EnvironmentStatus.OK
            details = f"Docker Compose standalone {v}"

        return EnvironmentCheck(
            name="docker-compose",
            status=status,
            required=required,
            installed_version=v,
            executable_path=standalone_res.executable,
            details=details,
            evidence=ev_list,
        )

    return EnvironmentCheck(
        name="docker-compose",
        status=EnvironmentStatus.MISSING,
        required=required,
        details="Docker Compose (plugin or standalone) not found",
        evidence=ev_list,
    )
