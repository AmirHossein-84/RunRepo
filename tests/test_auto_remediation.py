"""Tests for autonomous zero-install tool shims, Python version provisioning, smart secret synthesis, and Docker auto-remediation."""

from pathlib import Path
from runrepo.environment.checker import EnvironmentChecker
from runrepo.environment.checks import check_pipenv, check_pnpm, check_poetry, check_python, check_yarn
from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.env.classifier import EnvClassifier
from runrepo.env.manager import EnvManager
from runrepo.env.models import EnvClassification
from runrepo.executor.handlers.service import ServiceStepHandler
from runrepo.executor.process import MockProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.models import (
    Confidence,
    DatabaseRequirement,
    DetectionEvidence,
    DockerInfo,
    EnvVarCategory,
    EnvironmentVariable,
    PackageManagerInfo,
    ProjectInfo,
    ProjectType,
    RuntimeInfo,
)
from runrepo.planner.models import ActionType, PlanStatus, RiskLevel
from runrepo.planner.planner import ExecutionPlanner


def _make_env(checks: list[EnvironmentCheck]) -> EnvironmentState:
    is_sat = all(c.status == EnvironmentStatus.OK for c in checks if c.required)
    return EnvironmentState(
        checks=checks,
        platform="Windows 11",
        architecture="x86_64",
        is_satisfied=is_sat,
    )


def test_poetry_zero_install_shim_planner():
    """Verify that if poetry is missing on PATH but uvx is available, planner shims with uvx poetry."""
    ev = [DetectionEvidence(source="pyproject.toml", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="poetry-app",
        project_type=ProjectType.CLI_TOOL,
        runtimes=[RuntimeInfo(name="python", version=">=3.11", evidence=ev)],
        package_managers=[PackageManagerInfo(name="poetry", evidence=ev)],
        entrypoints=["main.py"],
    )

    env = _make_env(
        [
            EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.0", required=True),
            EnvironmentCheck(name="poetry", status=EnvironmentStatus.OK, installed_version="uvx poetry (ephemeral)", required=True),
            EnvironmentCheck(name="uv", status=EnvironmentStatus.OK, installed_version="0.12.0", required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    install_step = next(s for s in plan.steps if s.id == "install-deps")
    assert install_step.command == ["uvx", "poetry", "install", "--no-root"]

    start_step = next(s for s in plan.steps if s.id == "start-app")
    assert start_step.command == ["uvx", "--from", "poetry", "poetry", "run", "python", "main.py"]


def test_pnpm_zero_install_shim_planner():
    """Verify that if pnpm is missing on PATH but npx is available, planner shims with npx -y pnpm."""
    ev = [DetectionEvidence(source="package.json", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="pnpm-app",
        project_type=ProjectType.WEB_APPLICATION,
        runtimes=[RuntimeInfo(name="node", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
    )

    env = _make_env(
        [
            EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="22.0.0", required=True),
            EnvironmentCheck(name="pnpm", status=EnvironmentStatus.OK, installed_version="npx -y pnpm (ephemeral)", required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    install_step = next(s for s in plan.steps if s.id == "install-deps")
    assert install_step.command == ["npx", "-y", "pnpm", "install"]


def test_yarn_zero_install_shim_planner():
    """Verify that if yarn is missing on PATH but npx is available, planner shims with npx -y yarn."""
    ev = [DetectionEvidence(source="package.json", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="yarn-app",
        project_type=ProjectType.WEB_APPLICATION,
        runtimes=[RuntimeInfo(name="node", evidence=ev)],
        package_managers=[PackageManagerInfo(name="yarn", evidence=ev)],
    )

    env = _make_env(
        [
            EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="22.0.0", required=True),
            EnvironmentCheck(name="yarn", status=EnvironmentStatus.OK, installed_version="npx -y yarn (ephemeral)", required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    install_step = next(s for s in plan.steps if s.id == "install-deps")
    assert install_step.command == ["npx", "-y", "yarn", "install"]


def test_python_version_auto_provisioning_planner():
    """Verify that when the host Python version requires uv provisioning, a download step is added."""
    ev = [DetectionEvidence(source="pyproject.toml", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="python-versioned-app",
        project_type=ProjectType.CLI_TOOL,
        runtimes=[RuntimeInfo(name="python", version="3.11", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pip", evidence=ev)],
        entrypoints=["app.py"],
    )

    env = _make_env(
        [
            EnvironmentCheck(
                name="python",
                status=EnvironmentStatus.OK,
                installed_version="uv-managed 3.11",
                details="Python 3.11 will be automatically provisioned by uv",
                required=True,
            ),
            EnvironmentCheck(name="pip", status=EnvironmentStatus.OK, installed_version="uv pip", required=True),
            EnvironmentCheck(name="uv", status=EnvironmentStatus.OK, installed_version="0.12.0", required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    py_install_step = next((s for s in plan.steps if s.id == "install-python:3.11"), None)
    assert py_install_step is not None
    assert py_install_step.command == ["uv", "python", "install", "3.11"]

    venv_step = next((s for s in plan.steps if s.id == "create-venv"), None)
    assert venv_step is not None
    assert venv_step.command == ["uv", "venv", "--python", "3.11"]
    assert "install-python:3.11" in venv_step.depends_on


def test_smart_secret_and_env_placeholder_synthesis(tmp_path: Path):
    """Verify that placeholder secret values (changeme, replace_me, xxx) are synthesized with cryptographic randoms."""
    env_example = tmp_path / ".env.example"
    env_example.write_text(
        "SECRET_KEY=your_secret_key_here\n"
        "JWT_SECRET=changeme\n"
        "DATABASE_URL=postgres://user:pass@localhost:5432/test\n"
        "PORT=8000\n"
    )

    from runrepo.env.detector import EnvDetector

    reqs = EnvDetector.detect_project_requirements(tmp_path)
    created, content, keys = EnvManager.apply_env_updates(tmp_path, requirements=reqs)
    assert created is True

    env_content = (tmp_path / ".env").read_text()
    assert "your_secret_key_here" not in env_content
    assert "changeme" not in env_content
    assert "PORT=8000" in env_content

    # Check classified items
    secret_key_var = next(v for v in reqs if v.name == "SECRET_KEY")
    assert secret_key_var.classification == EnvClassification.AUTO_GENERATABLE
    jwt_var = next(v for v in reqs if v.name == "JWT_SECRET")
    assert jwt_var.classification == EnvClassification.AUTO_GENERATABLE


def test_docker_daemon_auto_remediation_step(tmp_path: Path):
    """Verify that start-docker-daemon step executes safely via ServiceStepHandler."""
    ev = [DetectionEvidence(source="compose.yaml", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path=str(tmp_path),
        name="docker-auto-app",
        project_type=ProjectType.WEB_APPLICATION,
        runtimes=[RuntimeInfo(name="node", evidence=ev)],
        package_managers=[PackageManagerInfo(name="npm", evidence=ev)],
        docker=DockerInfo(has_dockerfile=True, compose_files=["compose.yaml"]),
    )

    env = _make_env(
        [
            EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="22.0.0", required=True),
            EnvironmentCheck(name="npm", status=EnvironmentStatus.OK, installed_version="10.0.0", required=True),
            EnvironmentCheck(
                name="docker",
                status=EnvironmentStatus.BROKEN,
                details="Docker daemon is not running",
                required=True,
            ),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    daemon_step = next(s for s in plan.steps if s.id == "start-docker-daemon")
    assert daemon_step is not None

    handler = ServiceStepHandler()
    assert handler.can_handle(daemon_step) is True

    executor = MockProcessExecutor()
    pm = ProcessManager(state_dir=tmp_path / ".runrepo_state")
    res = handler.execute(daemon_step, tmp_path, executor, pm)

    assert res.exit_code == 0
    assert res.status.value == "SUCCESS"
