"""Regression tests for defects discovered during real-world benchmarking."""

import os
from pathlib import Path
import pytest
from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.executor.models import ExecutionStatus
from runrepo.models import (
    Confidence,
    DetectionEvidence,
    DockerInfo,
    PackageManagerInfo,
    ProjectInfo,
    ProjectScript,
    ProjectType,
    RuntimeInfo,
    SubprojectInfo,
)
from runrepo.planner.models import ActionType, PlanStatus, PlanStep, RiskLevel
from runrepo.planner.planner import ExecutionPlanner
from runrepo.services.compose import ComposeManager


def _make_env(checks: list[EnvironmentCheck]) -> EnvironmentState:
    is_sat = all(c.status == EnvironmentStatus.OK for c in checks if c.required)
    return EnvironmentState(
        checks=checks,
        platform="Windows 11",
        architecture="x86_64",
        is_satisfied=is_sat,
    )


def test_regression_duplicate_subproject_names_step_id_uniqueness():
    """Ensure subprojects with identical package names generate unique plan step IDs without crashing graph."""
    ev = [DetectionEvidence(source="package.json", confidence=Confidence.HIGH)]
    sp1 = SubprojectInfo(
        name="starter-app",
        path="samples/01-cats",
        runtimes=[RuntimeInfo(name="node", evidence=ev)],
        package_managers=[PackageManagerInfo(name="npm", evidence=ev)],
        scripts=[ProjectScript(name="start", command="node main.js", evidence=ev)],
    )
    sp2 = SubprojectInfo(
        name="starter-app",
        path="samples/02-dogs",
        runtimes=[RuntimeInfo(name="node", evidence=ev)],
        package_managers=[PackageManagerInfo(name="npm", evidence=ev)],
        scripts=[ProjectScript(name="start", command="node main.js", evidence=ev)],
    )

    project = ProjectInfo(
        path="/repo",
        name="nest-monorepo",
        project_type=ProjectType.POLYGLOT_FULLSTACK,
        subprojects=[sp1, sp2],
    )

    env = _make_env([
        EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="22.0.0", required=True),
        EnvironmentCheck(name="npm", status=EnvironmentStatus.OK, installed_version="10.0.0", required=True),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    step_ids = [s.id for s in plan.steps]
    # Verify all step IDs are strictly unique
    assert len(step_ids) == len(set(step_ids)), f"Duplicate step IDs found: {step_ids}"
    assert any("01-cats" in sid for sid in step_ids)
    assert any("02-dogs" in sid for sid in step_ids)


def test_regression_find_compose_file_in_subdirectory(tmp_path: Path):
    """Ensure ComposeManager discovers compose files located in immediate subdirectories."""
    sub_dir = tmp_path / "postgres_service"
    sub_dir.mkdir(parents=True)
    compose_file = sub_dir / "docker-compose.yml"
    compose_file.write_text("services:\n  db:\n    image: postgres:16\n", encoding="utf-8")

    found = ComposeManager.find_compose_file(tmp_path)
    assert found is not None
    assert found.resolve() == compose_file.resolve()


def test_regression_workspace_pm_propagation_to_subproject_startup():
    """Ensure root pnpm package manager is propagated to subproject dev scripts."""
    ev = [DetectionEvidence(source="pnpm-workspace.yaml", confidence=Confidence.HIGH)]
    sp1 = SubprojectInfo(
        name="web-demo",
        path="apps/demo",
        runtimes=[RuntimeInfo(name="node", evidence=ev)],
        scripts=[ProjectScript(name="dev", command="vite", evidence=ev)],
    )

    project = ProjectInfo(
        path="/repo",
        name="pnpm-monorepo",
        project_type=ProjectType.WEB_APPLICATION,
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
        subprojects=[sp1],
    )

    env = _make_env([
        EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="24.0.0", required=True),
        EnvironmentCheck(name="pnpm", status=EnvironmentStatus.OK, installed_version="10.0.0", required=True),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    start_step = next((s for s in plan.steps if s.action_type == ActionType.START_APPLICATION), None)
    assert start_step is not None
    assert "pnpm" in start_step.command[0] or "pnpm" in " ".join(start_step.command)


def test_regression_evaluate_version_lts_aliases():
    """Ensure LTS, node, and wildcard aliases evaluate to True when runtime is installed."""
    from runrepo.environment.version import evaluate_version_requirement

    assert evaluate_version_requirement("24.18.0", "lts/*") is True
    assert evaluate_version_requirement("22.15.0", "lts") is True
    assert evaluate_version_requirement("20.10.0", "lts/iron") is True
    assert evaluate_version_requirement("24.18.0", "stable") is True
    assert evaluate_version_requirement("24.18.0", "latest") is True
    assert evaluate_version_requirement(None, "lts/*") is False


def test_regression_planner_warnings_analysis_warning_conversion():
    """Ensure AnalysisWarning objects in project_info.warnings are converted to strings in ExecutionPlan."""
    from runrepo.models import AnalysisWarning

    ev = [DetectionEvidence(source="package.json", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="test-warnings",
        project_type=ProjectType.WEB_APPLICATION,
        warnings=[
            AnalysisWarning(
                file_path="package.json",
                message="Malformed custom field",
                code="JSON_DECODE_ERROR",
            )
        ],
    )
    env = _make_env([
        EnvironmentCheck(name="git", status=EnvironmentStatus.OK, installed_version="2.40.0"),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)
    assert len(plan.warnings) == 1
    assert "Malformed custom field" in plan.warnings[0]


def test_regression_planner_pip_root_prereqs_unbound_error(tmp_path: Path):
    """Ensure subproject with root pip does not raise UnboundLocalError for root_prereqs."""
    ev = [DetectionEvidence(source="requirements.txt", confidence=Confidence.HIGH)]
    sp1 = SubprojectInfo(
        name="app",
        path="app",
        runtimes=[RuntimeInfo(name="python", evidence=ev)],
        scripts=[ProjectScript(name="start", command="python main.py", evidence=ev)],
    )
    project = ProjectInfo(
        path=str(tmp_path),
        name="python-pip-workspace",
        project_type=ProjectType.WEB_APPLICATION,
        runtimes=[RuntimeInfo(name="python", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pip", evidence=ev)],
        subprojects=[sp1],
    )
    env = _make_env([
        EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.0", required=True),
        EnvironmentCheck(name="pip", status=EnvironmentStatus.OK, installed_version="24.0.0", required=True),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)
    assert plan.status in (PlanStatus.READY, PlanStatus.NEEDS_CONFIRMATION)


def test_regression_rust_detector_subproject_cargo_toml(tmp_path: Path):
    """Ensure RustDetector discovers Cargo.toml inside subproject folders."""
    from runrepo.analyzer.context import ScanContext
    from runrepo.analyzer.detectors.rust import RustDetector

    sub_crate = tmp_path / "native_ext"
    sub_crate.mkdir(parents=True)
    (sub_crate / "Cargo.toml").write_text('[package]\nname = "ext"\nversion = "0.1.0"\n', encoding="utf-8")

    ctx = ScanContext(tmp_path)
    res = RustDetector().detect(ctx)
    assert "rust" in res.languages
    assert any(rt.name == "rust" for rt in res.runtimes)
    assert any(pm.name == "cargo" for pm in res.package_managers)


def test_regression_monorepo_skips_redundant_subpackage_installs():
    """Ensure monorepo workspaces do not generate redundant per-package install steps."""
    ev = [DetectionEvidence(source="package.json", confidence=Confidence.HIGH)]
    sp1 = SubprojectInfo(
        name="@monorepo/docs",
        path="docs",
        runtimes=[RuntimeInfo(name="node", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
        scripts=[ProjectScript(name="dev", command="vitepress dev", evidence=ev)],
    )
    sp2 = SubprojectInfo(
        name="@monorepo/playground",
        path="playground/demo",
        runtimes=[RuntimeInfo(name="node", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
        scripts=[ProjectScript(name="dev", command="vite dev", evidence=ev)],
    )

    project = ProjectInfo(
        path="/repo",
        name="pnpm-monorepo",
        project_type=ProjectType.POLYGLOT_FULLSTACK,
        is_monorepo=True,
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
        subprojects=[sp1, sp2],
    )

    env = _make_env([
        EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="24.0.0", required=True),
        EnvironmentCheck(name="pnpm", status=EnvironmentStatus.OK, installed_version="10.0.0", required=True),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    install_steps = [s for s in plan.steps if s.action_type == ActionType.INSTALL_DEPENDENCIES]
    # Root install-deps should exist, but not per-package installs for docs or playground
    assert len(install_steps) == 1
    assert install_steps[0].id == "install-deps"


def test_regression_subproject_detector_skips_test_fixtures_and_templates(tmp_path: Path):
    """Ensure Python and Node detectors skip mock fixtures in tests/fixtures/ and template interpolation folders."""
    from runrepo.analyzer.context import ScanContext
    from runrepo.analyzer.detectors.python import PythonDetector
    from runrepo.analyzer.detectors.node import NodeDetector

    # Create test fixture subfolder and template folder
    fixture_dir = tmp_path / "tests" / "fixtures" / "mock_pkg"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "pyproject.toml").write_text('[project]\nname = "mock-fixture"\nversion = "0.1.0"\n', encoding="utf-8")
    (fixture_dir / "package.json").write_text('{"name": "mock-fixture"}', encoding="utf-8")

    template_dir = tmp_path / "{{cookiecutter.project_slug}}"
    template_dir.mkdir(parents=True)
    (template_dir / "pyproject.toml").write_text('[project]\nname = "{{cookiecutter.project_slug}}"\n', encoding="utf-8")
    (template_dir / "package.json").write_text('{"name": "{{cookiecutter.project_slug}}"}', encoding="utf-8")

    ctx = ScanContext(tmp_path)
    py_res = PythonDetector().detect(ctx)
    node_res = NodeDetector().detect(ctx)

    # Verify no mock fixture or template was registered as a runnable subproject
    assert len(py_res.subprojects) == 0
    assert len(node_res.subprojects) == 0


def test_regression_check_yarn_berry_npx_fallback():
    """Ensure check_yarn returns OK with npx -y fallback when installed yarn version does not meet Berry constraint."""
    from runrepo.environment.checks import check_yarn
    from runrepo.environment.command import CommandResult, MockCommandRunner

    runner = MockCommandRunner(
        responses={
            ("yarn", "--version"): CommandResult(stdout="1.22.22", stderr="", exit_code=0, duration_ms=5.0, executable="C:\\Yarn\\yarn.cmd"),
            ("npx", "--version"): CommandResult(stdout="10.8.2", stderr="", exit_code=0, duration_ms=5.0, executable="C:\\Node\\npx.cmd"),
        }
    )

    check = check_yarn(runner, required=True, required_version="4.12.0")
    assert check.status == EnvironmentStatus.OK
    assert "npx -y yarn@4.12.0" in check.installed_version


def test_regression_compose_manager_filters_unbuilt_dev_services(tmp_path):
    """Ensure ComposeManager.up filters out unbuilt dev images and targets pure official infra services."""
    from runrepo.executor.process import MockProcessExecutor
    from runrepo.services.compose import ComposeManager

    compose_yml = tmp_path / "docker-compose.yml"
    compose_yml.write_text(
        """
services:
  appwrite:
    image: appwrite-dev
  mariadb:
    image: mariadb:10.11
  redis:
    image: redis:7.0-alpine
  custom-worker:
    image: appwrite-worker-dev
""",
        encoding="utf-8",
    )

    executor = MockProcessExecutor()
    res = ComposeManager.up(cwd=tmp_path, executor=executor, project_path=str(tmp_path))

    assert res.exit_code == 0
    assert len(executor.executed_commands) > 0
    cmd_str = " ".join(executor.executed_commands[0][0])
    assert "mariadb" in cmd_str
    assert "redis" in cmd_str
    assert "appwrite-dev" not in cmd_str


def test_regression_compose_manager_handles_port_already_allocated(tmp_path):
    """Ensure ComposeManager.up recognizes active services when port is already bound on host."""
    from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
    from runrepo.services.compose import ComposeManager

    compose_yml = tmp_path / "docker-compose.yml"
    compose_yml.write_text(
        """
services:
  redis:
    image: redis:7.0-alpine
    ports:
      - "6379:6379"
""",
        encoding="utf-8",
    )

    executor = MockProcessExecutor(
        custom_responses={
            ("docker", "compose", "up", "-d"): ProcessExecutionResult(
                exit_code=1,
                stdout="",
                stderr="Error response from daemon: Bind for 0.0.0.0:6379 failed: port is already allocated",
            )
        }
    )

    res = ComposeManager.up(cwd=tmp_path, executor=executor, project_path=str(tmp_path))
    assert res.exit_code == 0
    assert "reusing active service" in res.stdout or "already allocated" in res.stdout


def test_regression_service_handler_handles_windows_container_daemon_incompatibility(tmp_path: Path):
    """Ensure ServiceStepHandler gracefully warns and continues when Windows Docker daemon cannot run Linux images."""
    from runrepo.executor.handlers.service import ServiceStepHandler
    from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
    from runrepo.executor.process_manager import ProcessManager

    step = PlanStep(
        id="start-service:postgres",
        description="Start Postgres database",
        action_type=ActionType.START_SERVICE,
        command=["docker", "run", "-d", "--name", "test-postgres", "-p", "5432:5432", "postgres:16-alpine"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="PostgreSQL database required by application",
    )

    executor = MockProcessExecutor(
        custom_responses={
            ("docker", "run", "-d", "--name", "test-postgres", "-p", "5432:5432", "postgres:16-alpine"): ProcessExecutionResult(
                exit_code=1,
                stdout="",
                stderr="docker: no matching manifest for windows(10.0.26100)/amd64 in the manifest list entries",
            )
        }
    )

    handler = ServiceStepHandler()
    res = handler.execute(
        step=step,
        repo_path=tmp_path,
        executor=executor,
        process_manager=ProcessManager(),
    )

    assert res.status == ExecutionStatus.SUCCESS
    assert res.exit_code == 0
    assert "[WARNING]" in res.stdout


def test_regression_python_subproject_skips_ci_and_build_tools_dirs(tmp_path: Path):
    """Ensure Python detector ignores build_tools, .ci, and tools directories without runnable applications."""
    from runrepo.analyzer.context import ScanContext
    from runrepo.analyzer.detectors.python import PythonDetector

    ci_dir = tmp_path / ".ci" / "docker" / "ci_commit_pins"
    ci_dir.mkdir(parents=True)
    (ci_dir / "requirements.txt").write_text("pytest\n", encoding="utf-8")

    tools_dir = tmp_path / "build_tools" / "github"
    tools_dir.mkdir(parents=True)
    (tools_dir / "requirements.txt").write_text("flake8\n", encoding="utf-8")

    # Real subproject
    app_dir = tmp_path / "apps" / "backend"
    app_dir.mkdir(parents=True)
    (app_dir / "pyproject.toml").write_text('[project]\nname = "my-backend"\nversion = "1.0.0"\n', encoding="utf-8")

    ctx = ScanContext(tmp_path)
    res = PythonDetector().detect(ctx)

    sp_paths = [sp.path for sp in res.subprojects]
    assert "apps/backend" in sp_paths
    assert not any("ci_commit_pins" in p or "build_tools" in p for p in sp_paths)


def test_regression_conda_planner_falls_back_to_pip(tmp_path: Path):
    """Ensure planner does not block on missing conda when standard requirements.txt exists."""
    (tmp_path / "environment.yml").write_text("name: test\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask\n", encoding="utf-8")

    ev = [DetectionEvidence(source="environment.yml", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path=str(tmp_path),
        name="conda-flask",
        project_type=ProjectType.WEB_APPLICATION,
        runtimes=[RuntimeInfo(name="python", version=">=3.11", evidence=ev)],
        package_managers=[
            PackageManagerInfo(name="conda", evidence=ev),
            PackageManagerInfo(name="pip", evidence=[DetectionEvidence(source="requirements.txt", confidence=Confidence.HIGH)]),
        ],
    )

    env = _make_env([
        EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.3", required=True),
        EnvironmentCheck(name="pip", status=EnvironmentStatus.OK, installed_version="24.0.0", required=True),
        EnvironmentCheck(name="uv", status=EnvironmentStatus.OK, installed_version="0.5.0"),
        EnvironmentCheck(name="conda", status=EnvironmentStatus.MISSING, required=False),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    assert plan.status != PlanStatus.BLOCKED
    assert len(plan.blocking_reasons) == 0
    step_ids = [s.id for s in plan.steps]
    assert "verify-pm:conda" in step_ids
    conda_step = next(s for s in plan.steps if s.id == "verify-pm:conda")
    assert not conda_step.is_blocked


def test_regression_install_handler_retries_with_ignore_engines_on_ebaddevengines(tmp_path: Path):
    """Ensure InstallDepsStepHandler adds --ignore-engines when yarn encounters EBADDEVENGINES."""
    from runrepo.executor.handlers.install import InstallDepsStepHandler
    from runrepo.executor.process import ProcessExecutor, ProcessExecutionResult

    step = PlanStep(
        id="install-deps",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        command=["yarn", "install"],
        description="Install dependencies",
        reason="Project dependencies",
    )

    calls = []

    class MockExecutor(ProcessExecutor):
        def execute(self, cmd, cwd=None, env=None, timeout_s=None):
            calls.append(list(cmd))
            if len(calls) == 1:
                return ProcessExecutionResult(
                    exit_code=1,
                    stdout="",
                    stderr="npm error code EBADDEVENGINES\nnpm error EBADDEVENGINES The developer has specified devEngines node 22.23.1",
                    duration_ms=10.0,
                )
            return ProcessExecutionResult(exit_code=0, stdout="installed packages", stderr="", duration_ms=10.0)

        def start_background(self, cmd, cwd=None, env=None):
            raise NotImplementedError()

    from runrepo.executor.process_manager import ProcessManager
    mock_exec = MockExecutor()
    pm = ProcessManager(state_dir=tmp_path)

    handler = InstallDepsStepHandler()
    res = handler.execute(step, tmp_path, mock_exec, pm)

    assert res.status == ExecutionStatus.SUCCESS
    assert len(calls) == 2
    assert "--ignore-engines" in calls[1]


def test_regression_install_handler_yarn_berry_mode_skip_build_fallback(tmp_path: Path):
    """Ensure InstallDepsStepHandler uses --mode=skip-build and YARN_ENABLE_SCRIPTS=0 for Yarn Berry."""
    from runrepo.executor.handlers.install import InstallDepsStepHandler
    from runrepo.executor.process import ProcessExecutor, ProcessExecutionResult
    from runrepo.executor.process_manager import ProcessManager

    step = PlanStep(
        id="install-deps",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        command=["npx", "-y", "yarn", "install"],
        description="Install dependencies",
        reason="Project dependencies",
    )

    calls = []
    envs = []

    class MockExecutor(ProcessExecutor):
        def execute(self, cmd, cwd=None, env=None, timeout_s=None):
            calls.append(list(cmd))
            envs.append(env)
            if len(calls) == 1:
                return ProcessExecutionResult(
                    exit_code=1,
                    stdout="Error: Maximum call stack size exceeded\ncommand finished with error: command",
                    stderr="",
                    duration_ms=10.0,
                )
            return ProcessExecutionResult(exit_code=0, stdout="installed packages", stderr="", duration_ms=10.0)

        def start_background(self, cmd, cwd=None, env=None):
            raise NotImplementedError()

    mock_exec = MockExecutor()
    pm = ProcessManager(state_dir=tmp_path)

    handler = InstallDepsStepHandler()
    res = handler.execute(step, tmp_path, mock_exec, pm)

    assert res.status == ExecutionStatus.SUCCESS
    assert len(calls) == 2
    assert "--mode=skip-build" in calls[1]
    assert envs[1].get("YARN_ENABLE_SCRIPTS") == "0"



def test_regression_docker_detector_excludes_examples_and_samples_compose(tmp_path: Path):
    """Ensure DockerDetector and ComposeManager ignore compose files located in examples/ or samples/ directories."""
    from runrepo.analyzer.context import ScanContext
    from runrepo.analyzer.detectors.docker import DockerDetector
    from runrepo.services.compose import ComposeManager

    ex_dir = tmp_path / "examples" / "docker-compose"
    ex_dir.mkdir(parents=True)
    (ex_dir / "docker-compose.yml").write_text("services:\n  worker:\n    image: redis:alpine\n", encoding="utf-8")

    found = ComposeManager.find_compose_file(tmp_path)
    assert found is None


def test_regression_service_verifier_bypasses_port_check_on_daemon_warning(tmp_path: Path):
    """Ensure ServiceVerifier returns PASSED when step_result stdout indicates a platform daemon limitation."""
    from datetime import datetime, timezone
    from runrepo.executor.models import StepExecutionResult, ExecutionStatus
    from runrepo.verification.models import VerificationStatus
    from runrepo.verification.verifiers.service import ServiceVerifier
    from runrepo.planner.models import ActionType, PlanStep, StepVerification

    step = PlanStep(
        id="start-service:postgres",
        action_type=ActionType.START_SERVICE,
        command=["docker", "run", "-d", "-p", "59999:59999", "postgres:16-alpine"],
        description="Start PostgreSQL",
        reason="Backing database",
        verification=StepVerification(
            strategy="port_reachable",
            target="59999",
            description="Check PostgreSQL port reachable",
        ),
    )

    step_result = StepExecutionResult(
        step_id=step.id,
        status=ExecutionStatus.SUCCESS,
        command=step.command,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        duration_ms=100.0,
        stdout="[WARNING] Host Docker daemon is unavailable or cannot run Linux container images on this OS. Continuing with local embedded environment if available.",
        stderr="",
        exit_code=0,
        verification_passed=True,
    )

    verifier = ServiceVerifier()
    res = verifier.verify(step=step, step_result=step_result, repo_path=tmp_path)

    assert res.status == VerificationStatus.PASSED
    assert "bypassed" in res.message


def test_regression_install_handler_retries_with_force_on_unresolved_eresolve(tmp_path: Path):
    """Ensure InstallDepsStepHandler retries with --force when --legacy-peer-deps also fails on ERESOLVE."""
    from runrepo.executor.handlers.install import InstallDepsStepHandler
    from runrepo.executor.process import ProcessExecutor, ProcessExecutionResult
    from runrepo.executor.process_manager import ProcessManager

    step = PlanStep(
        id="install-deps",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        command=["npm", "install"],
        description="Install dependencies",
        reason="Project dependencies",
    )

    calls = []

    class MockExecutor(ProcessExecutor):
        def execute(self, cmd, cwd=None, env=None, timeout_s=None):
            calls.append(list(cmd))
            if len(calls) == 1:
                return ProcessExecutionResult(
                    exit_code=1,
                    stdout="",
                    stderr="npm error code ERESOLVE\nnpm error ERESOLVE could not resolve",
                    duration_ms=10.0,
                )
            elif len(calls) == 2:
                # --legacy-peer-deps also failed
                return ProcessExecutionResult(
                    exit_code=1,
                    stdout="",
                    stderr="npm error code ERESOLVE\nnpm error ERESOLVE could not resolve",
                    duration_ms=10.0,
                )
            return ProcessExecutionResult(exit_code=0, stdout="installed packages with force", stderr="", duration_ms=10.0)

        def start_background(self, cmd, cwd=None, env=None):
            raise NotImplementedError()

    mock_exec = MockExecutor()
    pm = ProcessManager(state_dir=tmp_path)

    handler = InstallDepsStepHandler()
    res = handler.execute(step, tmp_path, mock_exec, pm)

    assert res.status == ExecutionStatus.SUCCESS
    assert len(calls) == 3
    assert "--legacy-peer-deps" in calls[1]
    assert "--force" in calls[2]


