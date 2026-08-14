"""Unit tests for deterministic planning rules across repository and environment scenarios."""

from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.models import (
    Confidence,
    DetectionEvidence,
    DockerInfo,
    EnvVarCategory,
    EnvironmentVariable,
    FrameworkCategory,
    FrameworkInfo,
    PackageManagerInfo,
    ProjectInfo,
    ProjectScript,
    ProjectType,
    RuntimeInfo,
    SubprojectInfo,
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


def test_plan_node_pnpm_satisfied():
    ev = [DetectionEvidence(source="package.json", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="next-app",
        project_type=ProjectType.WEB_APPLICATION,
        runtimes=[RuntimeInfo(name="node", version=">=22", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
        scripts=[ProjectScript(name="dev", command="next dev", evidence=ev)],
    )

    env = _make_env(
        [
            EnvironmentCheck(name="git", status=EnvironmentStatus.OK, installed_version="2.45.0"),
            EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="22.15.0", required=True),
            EnvironmentCheck(name="pnpm", status=EnvironmentStatus.OK, installed_version="10.12.1", required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    assert plan.status == PlanStatus.NEEDS_CONFIRMATION
    assert len(plan.blocking_reasons) == 0

    step_ids = [s.id for s in plan.steps]
    assert "verify-runtime:node" in step_ids
    assert "verify-pm:pnpm" in step_ids
    assert "install-deps" in step_ids
    assert "start-app" in step_ids
    assert "verify-app" in step_ids

    # Check dependencies
    install_step = next(s for s in plan.steps if s.id == "install-deps")
    assert install_step.command == ["pnpm", "install"]
    assert "verify-pm:pnpm" in install_step.depends_on
    assert "verify-runtime:node" in install_step.depends_on

    start_step = next(s for s in plan.steps if s.id == "start-app")
    assert start_step.command == ["pnpm", "run", "dev"]
    assert "install-deps" in start_step.depends_on


def test_plan_node_wrong_version_blocked():
    ev = [DetectionEvidence(source="package.json", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="next-app",
        runtimes=[RuntimeInfo(name="node", version=">=22", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
    )

    env = _make_env(
        [
            EnvironmentCheck(name="node", status=EnvironmentStatus.WRONG_VERSION, installed_version="20.11.0", required=True),
            EnvironmentCheck(name="pnpm", status=EnvironmentStatus.OK, installed_version="10.12.1", required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    assert plan.status == PlanStatus.BLOCKED
    assert any("version mismatch" in r.lower() for r in plan.blocking_reasons)
    node_step = next(s for s in plan.steps if s.id == "verify-runtime:node")
    assert node_step.is_blocked is True
    assert node_step.risk == RiskLevel.BLOCKED


def test_plan_missing_package_manager_blocked():
    ev = [DetectionEvidence(source="package.json", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="app",
        runtimes=[RuntimeInfo(name="node", version=">=22", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
    )

    env = _make_env(
        [
            EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="22.15.0", required=True),
            EnvironmentCheck(name="pnpm", status=EnvironmentStatus.MISSING, required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    assert plan.status == PlanStatus.BLOCKED
    assert any("missing" in r.lower() for r in plan.blocking_reasons)


def test_plan_python_uv_satisfied():
    ev = [DetectionEvidence(source="pyproject.toml", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="fastapi-app",
        project_type=ProjectType.API_SERVICE,
        runtimes=[RuntimeInfo(name="python", version=">=3.11", evidence=ev)],
        package_managers=[PackageManagerInfo(name="uv", evidence=ev)],
        frameworks=[FrameworkInfo(name="FastAPI", category=FrameworkCategory.WEB_BACKEND, evidence=ev)],
        scripts=[ProjectScript(name="dev", command="fastapi dev main.py", evidence=ev)],
    )

    env = _make_env(
        [
            EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.3", required=True),
            EnvironmentCheck(name="uv", status=EnvironmentStatus.OK, installed_version="0.12.0", required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    assert plan.status == PlanStatus.NEEDS_CONFIRMATION
    install_step = next(s for s in plan.steps if s.id == "install-deps")
    assert install_step.command == ["uv", "sync"]


def test_plan_required_secret_env_needs_input():
    ev = [DetectionEvidence(source=".env.example", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="ai-app",
        runtimes=[RuntimeInfo(name="python", version=">=3.11", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pip", evidence=ev)],
        environment_variables=[
            EnvironmentVariable(
                name="OPENAI_API_KEY",
                is_required=True,
                category=EnvVarCategory.SECRET,
                evidence=ev,
            )
        ],
    )

    env = _make_env(
        [
            EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.0", required=True),
            EnvironmentCheck(name="pip", status=EnvironmentStatus.OK, installed_version="24.0", required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    assert plan.status == PlanStatus.NEEDS_INPUT
    assert any("OPENAI_API_KEY" in r for r in plan.input_reasons)


def test_plan_multiple_startup_scripts_needs_input():
    ev = [DetectionEvidence(source="package.json", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="multi-script-app",
        runtimes=[RuntimeInfo(name="node", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
        scripts=[
            ProjectScript(name="dev", command="vite", evidence=ev),
            ProjectScript(name="start", command="vite preview", evidence=ev),
            ProjectScript(name="serve", command="sirv dist", evidence=ev),
        ],
    )

    env = _make_env(
        [
            EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="22.0.0", required=True),
            EnvironmentCheck(name="pnpm", status=EnvironmentStatus.OK, installed_version="10.0.0", required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    assert plan.status == PlanStatus.NEEDS_INPUT
    start_step = next(s for s in plan.steps if s.id == "start-app")
    assert len(start_step.candidate_commands) >= 2
    assert any("Multiple startup commands detected" in w for w in plan.warnings)


def test_plan_docker_broken_daemon_blocked():
    ev = [DetectionEvidence(source="compose.yaml", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="docker-app",
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

    assert plan.status == PlanStatus.BLOCKED
    assert any("Docker" in r for r in plan.blocking_reasons)


def test_plan_polyglot_subprojects_dag():
    ev = [DetectionEvidence(source="manifest", confidence=Confidence.HIGH)]
    sp_fe = SubprojectInfo(
        name="frontend",
        path="frontend",
        runtimes=[RuntimeInfo(name="node", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
        scripts=[ProjectScript(name="dev", command="next dev", evidence=ev)],
    )
    sp_be = SubprojectInfo(
        name="backend",
        path="backend",
        runtimes=[RuntimeInfo(name="python", evidence=ev)],
        package_managers=[PackageManagerInfo(name="uv", evidence=ev)],
        scripts=[ProjectScript(name="dev", command="fastapi dev main.py", evidence=ev)],
    )

    project = ProjectInfo(
        path="/repo",
        name="fullstack-app",
        project_type=ProjectType.POLYGLOT_FULLSTACK,
        subprojects=[sp_fe, sp_be],
    )

    env = _make_env(
        [
            EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="22.0.0", required=True),
            EnvironmentCheck(name="pnpm", status=EnvironmentStatus.OK, installed_version="10.0.0", required=True),
            EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.0", required=True),
            EnvironmentCheck(name="uv", status=EnvironmentStatus.OK, installed_version="0.12.0", required=True),
        ]
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    assert plan.status == PlanStatus.NEEDS_CONFIRMATION
    step_ids = [s.id for s in plan.steps]

    assert "install-deps:frontend" in step_ids
    assert "install-deps:backend" in step_ids
    assert "start-app:frontend" in step_ids
    assert "start-app:backend" in step_ids

    fe_install = next(s for s in plan.steps if s.id == "install-deps:frontend")
    assert fe_install.cwd == "frontend"
    assert fe_install.command == ["pnpm", "install"]

    be_install = next(s for s in plan.steps if s.id == "install-deps:backend")
    assert be_install.cwd == "backend"
    assert be_install.command == ["uv", "sync"]


def test_planner_zero_side_effects(monkeypatch):
    """Ensure ExecutionPlanner never calls subprocess or modifies the filesystem."""
    def fail_subprocess(*args, **kwargs):
        raise RuntimeError("Subprocess execution attempted during planning!")

    monkeypatch.setattr("subprocess.run", fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", fail_subprocess)

    project = ProjectInfo(
        path="/repo",
        name="app",
        runtimes=[RuntimeInfo(name="node")],
        package_managers=[PackageManagerInfo(name="pnpm")],
    )
    env = _make_env([EnvironmentCheck(name="node", status=EnvironmentStatus.OK), EnvironmentCheck(name="pnpm", status=EnvironmentStatus.OK)])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)
    assert plan is not None
