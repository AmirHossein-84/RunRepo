"""Regression tests for defects discovered during real-world benchmarking."""

import os
from pathlib import Path
import pytest
from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
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
from runrepo.planner.models import ActionType, PlanStatus
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


