"""Environment checker orchestrating local tool probes and evaluating project requirements."""

import platform
from typing import Sequence

from runrepo.environment.checks import (
    check_docker,
    check_docker_compose,
    check_git,
    check_node,
    check_npm,
    check_pip,
    check_pipenv,
    check_pnpm,
    check_poetry,
    check_python,
    check_uv,
    check_yarn,
)
from runrepo.environment.command import CommandRunner, SystemCommandRunner
from runrepo.environment.models import (
    EnvironmentCheck,
    EnvironmentState,
    EnvironmentStatus,
)
from runrepo.models import ProjectInfo


def get_platform_name() -> str:
    """Return clean human-readable OS platform description."""
    sys_name = platform.system()
    if sys_name == "Windows":
        rel = platform.release()
        return f"Windows {rel}"
    elif sys_name == "Darwin":
        return f"macOS {platform.mac_ver()[0]}"
    return f"{sys_name} ({platform.release()})"


def get_architecture_name() -> str:
    """Return CPU architecture name."""
    mach = platform.machine().lower()
    if mach in ("amd64", "x86_64"):
        return "x86_64"
    elif mach in ("arm64", "aarch64"):
        return "arm64"
    return mach or "unknown"


class EnvironmentChecker:
    """Evaluates local host environment capabilities against repository requirements."""

    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner if runner is not None else SystemCommandRunner()

    def check_environment(self, project_info: ProjectInfo | None = None) -> EnvironmentState:
        """Run environment checks and evaluate requirement satisfaction."""
        checks: list[EnvironmentCheck] = []
        seen_tools: set[str] = set()

        # Always check Git as core developer capability
        git_check = check_git(self.runner)
        checks.append(git_check)
        seen_tools.add("git")

        if project_info is not None and (
            project_info.runtimes
            or project_info.package_managers
            or project_info.docker.has_dockerfile
            or project_info.docker.compose_files
            or project_info.databases
            or project_info.subprojects
        ):
            # 1. Project-guided requirements mode
            python_exe: str | None = None

            # Collect requirements from root and subprojects
            all_runtimes = list(project_info.runtimes)
            all_pms = list(project_info.package_managers)
            for sp in project_info.subprojects:
                all_runtimes.extend(sp.runtimes)
                all_pms.extend(sp.package_managers)

            # Node runtime check
            node_rts = [rt for rt in all_runtimes if rt.name == "node"]
            if node_rts:
                primary_rt = node_rts[0]
                node_check = check_node(
                    self.runner,
                    required=True,
                    required_version=primary_rt.version,
                    evidence=primary_rt.evidence,
                )
                checks.append(node_check)
                seen_tools.add("node")

            # Python runtime check
            py_rts = [rt for rt in all_runtimes if rt.name == "python"]
            if py_rts:
                primary_py = py_rts[0]
                py_check, python_exe = check_python(
                    self.runner,
                    required=True,
                    required_version=primary_py.version,
                    evidence=primary_py.evidence,
                )
                checks.append(py_check)
                seen_tools.add("python")
            else:
                # Probe Python in background if needed for other tools
                _, python_exe = check_python(self.runner, required=False)

            # Package Managers check
            for pm in all_pms:
                pm_name = pm.name.lower()
                if pm_name in seen_tools:
                    continue

                if pm_name == "npm":
                    checks.append(
                        check_npm(
                            self.runner,
                            required=True,
                            required_version=pm.version,
                            evidence=pm.evidence,
                        )
                    )
                    seen_tools.add("npm")
                elif pm_name == "pnpm":
                    checks.append(
                        check_pnpm(
                            self.runner,
                            required=True,
                            required_version=pm.version,
                            evidence=pm.evidence,
                        )
                    )
                    seen_tools.add("pnpm")
                elif pm_name == "yarn":
                    checks.append(
                        check_yarn(
                            self.runner,
                            required=True,
                            required_version=pm.version,
                            evidence=pm.evidence,
                        )
                    )
                    seen_tools.add("yarn")
                elif pm_name == "pip":
                    checks.append(
                        check_pip(
                            self.runner,
                            python_executable=python_exe,
                            required=True,
                            required_version=pm.version,
                            evidence=pm.evidence,
                        )
                    )
                    seen_tools.add("pip")
                elif pm_name == "poetry":
                    checks.append(
                        check_poetry(
                            self.runner,
                            required=True,
                            required_version=pm.version,
                            evidence=pm.evidence,
                        )
                    )
                    seen_tools.add("poetry")
                elif pm_name == "pipenv":
                    checks.append(
                        check_pipenv(
                            self.runner,
                            required=True,
                            required_version=pm.version,
                            evidence=pm.evidence,
                        )
                    )
                    seen_tools.add("pipenv")
                elif pm_name == "uv":
                    checks.append(
                        check_uv(
                            self.runner,
                            required=True,
                            required_version=pm.version,
                            evidence=pm.evidence,
                        )
                    )
                    seen_tools.add("uv")

            # Docker and Compose check
            needs_docker = (
                project_info.docker.has_dockerfile
                or bool(project_info.docker.compose_files)
                or bool(project_info.databases)
                or bool(project_info.services)
            )
            needs_compose = bool(project_info.docker.compose_files)

            if needs_docker or needs_compose:
                docker_check = check_docker(
                    self.runner,
                    required=needs_docker,
                    evidence=project_info.docker.evidence,
                )
                checks.append(docker_check)
                seen_tools.add("docker")

                if needs_compose:
                    compose_check = check_docker_compose(
                        self.runner,
                        docker_status=docker_check.status,
                        required=True,
                        evidence=project_info.docker.evidence,
                    )
                    checks.append(compose_check)
                    seen_tools.add("docker-compose")

        else:
            # 2. Host-wide general capability check mode
            # Node
            checks.append(check_node(self.runner, required=False))
            # Python
            py_check, python_exe = check_python(self.runner, required=False)
            checks.append(py_check)
            # Package managers
            checks.append(check_npm(self.runner, required=False))
            checks.append(check_pnpm(self.runner, required=False))
            checks.append(check_yarn(self.runner, required=False))
            checks.append(check_pip(self.runner, python_executable=python_exe, required=False))
            checks.append(check_uv(self.runner, required=False))
            # Docker & Compose
            d_check = check_docker(self.runner, required=False)
            checks.append(d_check)
            checks.append(check_docker_compose(self.runner, docker_status=d_check.status, required=False))

        # Calculate satisfaction metrics
        missing = [c.name for c in checks if c.required and c.status == EnvironmentStatus.MISSING]
        wrong_v = [c.name for c in checks if c.required and c.status == EnvironmentStatus.WRONG_VERSION]
        broken = [c.name for c in checks if c.required and c.status == EnvironmentStatus.BROKEN]
        unknown = [c.name for c in checks if c.required and c.status == EnvironmentStatus.UNKNOWN]

        is_satisfied = len(missing) == 0 and len(wrong_v) == 0 and len(broken) == 0

        return EnvironmentState(
            checks=checks,
            platform=get_platform_name(),
            architecture=get_architecture_name(),
            is_satisfied=is_satisfied,
            missing_checks=missing,
            wrong_version_checks=wrong_v,
            broken_checks=broken,
            unknown_checks=unknown,
        )
