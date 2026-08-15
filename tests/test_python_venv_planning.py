"""Comprehensive tests for Python virtual environment detection, reuse, and safe replacement planning."""

from pathlib import Path
import pytest

from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.environment.venv import (
    VirtualEnvInspection,
    VirtualEnvStatus,
    inspect_virtual_env,
)
from runrepo.models import (
    Confidence,
    DetectionEvidence,
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


# ---------------------------------------------------------------------------
# 1. Inspection Unit Tests
# ---------------------------------------------------------------------------

def test_inspect_virtual_env_not_found(tmp_path: Path):
    """When .venv does not exist, status is NOT_FOUND."""
    inspection = inspect_virtual_env(tmp_path)
    assert inspection.status == VirtualEnvStatus.NOT_FOUND
    assert "No virtual environment found" in inspection.details


def test_inspect_virtual_env_valid_windows(tmp_path: Path):
    """Windows virtualenv with Scripts/python.exe and pyvenv.cfg is VALID."""
    venv_dir = tmp_path / ".venv"
    scripts_dir = venv_dir / "Scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "python.exe").write_bytes(b"dummy-binary")
    (venv_dir / "pyvenv.cfg").write_text("version = 3.12.3\nhome = C:\\Python312\n", encoding="utf-8")

    inspection = inspect_virtual_env(tmp_path, required_version=">=3.11")
    assert inspection.status == VirtualEnvStatus.VALID
    assert inspection.python_version == "3.12.3"
    assert inspection.python_executable == scripts_dir / "python.exe"
    assert "Usable virtual environment" in inspection.details


def test_inspect_virtual_env_valid_linux(tmp_path: Path):
    """Linux virtualenv with bin/python and pyvenv.cfg is VALID."""
    venv_dir = tmp_path / ".venv"
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").write_bytes(b"dummy-binary")
    (venv_dir / "pyvenv.cfg").write_text("version = 3.11.8\nhome = /usr/bin\n", encoding="utf-8")

    inspection = inspect_virtual_env(tmp_path, required_version=">=3.10")
    assert inspection.status == VirtualEnvStatus.VALID
    assert inspection.python_version == "3.11.8"
    assert inspection.python_executable == bin_dir / "python"
    assert "Usable virtual environment" in inspection.details


def test_inspect_virtual_env_broken_missing_python(tmp_path: Path):
    """Empty or half-created .venv directory without python binary is BROKEN."""
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir(parents=True)
    (venv_dir / "pyvenv.cfg").write_text("version = 3.12.0\n", encoding="utf-8")

    inspection = inspect_virtual_env(tmp_path)
    assert inspection.status == VirtualEnvStatus.BROKEN
    assert "contains no valid python executable" in inspection.details


def test_inspect_virtual_env_broken_is_file(tmp_path: Path):
    """.venv created as a regular file is classified as BROKEN."""
    file_path = tmp_path / ".venv"
    file_path.write_text("corrupted-file-not-dir", encoding="utf-8")

    inspection = inspect_virtual_env(tmp_path)
    assert inspection.status == VirtualEnvStatus.BROKEN
    assert "is a file, not a directory" in inspection.details


def test_inspect_virtual_env_wrong_version(tmp_path: Path):
    """.venv with Python 3.9 when repository requires >=3.11 is WRONG_VERSION."""
    venv_dir = tmp_path / ".venv"
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").write_bytes(b"dummy-binary")
    (venv_dir / "pyvenv.cfg").write_text("version = 3.9.5\nhome = /usr/bin\n", encoding="utf-8")

    inspection = inspect_virtual_env(tmp_path, required_version=">=3.11")
    assert inspection.status == VirtualEnvStatus.WRONG_VERSION
    assert inspection.python_version == "3.9.5"
    assert "does not satisfy required constraint" in inspection.details


# ---------------------------------------------------------------------------
# 2. Planner Execution Scenarios
# ---------------------------------------------------------------------------

def test_planner_no_venv_creates_venv(tmp_path: Path):
    """When no .venv exists, planner plans a SAFE 'create-venv' step."""
    ev = [DetectionEvidence(source="requirements.txt", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path=str(tmp_path),
        name="my-app",
        project_type=ProjectType.CLI_TOOL,
        runtimes=[RuntimeInfo(name="python", version=">=3.11", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pip", evidence=ev)],
        scripts=[ProjectScript(name="run", command="python main.py", evidence=ev)],
    )

    env = _make_env([
        EnvironmentCheck(name="git", status=EnvironmentStatus.OK, installed_version="2.45.0"),
        EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.3", required=True),
        EnvironmentCheck(name="pip", status=EnvironmentStatus.OK, installed_version="uv (0.12.5)", required=True),
        EnvironmentCheck(name="uv", status=EnvironmentStatus.OK, installed_version="0.12.5"),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    step_ids = [s.id for s in plan.steps]
    assert "create-venv" in step_ids
    assert "replace-venv" not in step_ids

    create_step = next(s for s in plan.steps if s.id == "create-venv")
    assert create_step.command == ["uv", "venv"]
    assert create_step.risk == RiskLevel.SAFE

    install_step = next(s for s in plan.steps if s.id == "install-deps")
    assert "create-venv" in install_step.depends_on
    assert install_step.command == ["uv", "pip", "install", "-r", "requirements.txt"]

    start_step = next(s for s in plan.steps if s.id == "start-app")
    assert start_step.command == ["uv", "run", "python", "main.py"]


def test_planner_valid_venv_reuses_it(tmp_path: Path):
    """When a valid .venv exists, planner reuses it without planning creation or replacement."""
    venv_dir = tmp_path / ".venv"
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").write_bytes(b"dummy")
    (venv_dir / "pyvenv.cfg").write_text("version = 3.12.3\n", encoding="utf-8")

    ev = [DetectionEvidence(source="requirements.txt", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path=str(tmp_path),
        name="my-app",
        project_type=ProjectType.CLI_TOOL,
        runtimes=[RuntimeInfo(name="python", version=">=3.11", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pip", evidence=ev)],
        scripts=[ProjectScript(name="run", command="python main.py", evidence=ev)],
    )

    env = _make_env([
        EnvironmentCheck(name="git", status=EnvironmentStatus.OK, installed_version="2.45.0"),
        EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.3", required=True),
        EnvironmentCheck(name="pip", status=EnvironmentStatus.OK, installed_version="uv (0.12.5)", required=True),
        EnvironmentCheck(name="uv", status=EnvironmentStatus.OK, installed_version="0.12.5"),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    step_ids = [s.id for s in plan.steps]
    # No creation or replacement steps
    assert "create-venv" not in step_ids
    assert "replace-venv" not in step_ids

    install_step = next(s for s in plan.steps if s.id == "install-deps")
    assert "reusing valid environment" in install_step.reason
    assert install_step.command == ["uv", "pip", "install", "-r", "requirements.txt"]


def test_planner_broken_venv_replaces_safely(tmp_path: Path):
    """When .venv is broken, planner plans 'replace-venv' with 'uv venv --clear' and REQUIRES_CONFIRMATION."""
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir(parents=True)  # empty directory (no python executable)

    ev = [DetectionEvidence(source="requirements.txt", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path=str(tmp_path),
        name="my-app",
        project_type=ProjectType.CLI_TOOL,
        runtimes=[RuntimeInfo(name="python", version=">=3.11", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pip", evidence=ev)],
    )

    env = _make_env([
        EnvironmentCheck(name="git", status=EnvironmentStatus.OK, installed_version="2.45.0"),
        EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.3", required=True),
        EnvironmentCheck(name="pip", status=EnvironmentStatus.OK, installed_version="uv (0.12.5)", required=True),
        EnvironmentCheck(name="uv", status=EnvironmentStatus.OK, installed_version="0.12.5"),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    step_ids = [s.id for s in plan.steps]
    assert "replace-venv" in step_ids
    assert "create-venv" not in step_ids

    replace_step = next(s for s in plan.steps if s.id == "replace-venv")
    assert replace_step.command == ["uv", "venv", "--clear"]
    assert replace_step.risk == RiskLevel.REQUIRES_CONFIRMATION
    assert "Replace broken virtual environment" in replace_step.reason

    install_step = next(s for s in plan.steps if s.id == "install-deps")
    assert "replace-venv" in install_step.depends_on


def test_planner_wrong_version_venv_replaces_safely(tmp_path: Path):
    """When .venv has incompatible Python version, planner plans replacement with clear explanation."""
    venv_dir = tmp_path / ".venv"
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").write_bytes(b"dummy")
    (venv_dir / "pyvenv.cfg").write_text("version = 3.9.2\n", encoding="utf-8")

    ev = [DetectionEvidence(source="requirements.txt", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path=str(tmp_path),
        name="my-app",
        project_type=ProjectType.CLI_TOOL,
        runtimes=[RuntimeInfo(name="python", version=">=3.11", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pip", evidence=ev)],
    )

    env = _make_env([
        EnvironmentCheck(name="git", status=EnvironmentStatus.OK, installed_version="2.45.0"),
        EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.3", required=True),
        EnvironmentCheck(name="pip", status=EnvironmentStatus.OK, installed_version="uv (0.12.5)", required=True),
        EnvironmentCheck(name="uv", status=EnvironmentStatus.OK, installed_version="0.12.5"),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    replace_step = next(s for s in plan.steps if s.id == "replace-venv")
    assert replace_step.command == ["uv", "venv", "--clear"]
    assert replace_step.risk == RiskLevel.REQUIRES_CONFIRMATION
    assert "Replace incompatible virtual environment" in replace_step.reason
    assert "3.9.2" in replace_step.reason


def test_monorepo_subproject_venv_scoping(tmp_path: Path):
    """Subproject Python workspaces create/reuse .venv inside their specific subdirectory."""
    sub_dir = tmp_path / "services" / "api"
    sub_dir.mkdir(parents=True)

    ev = [DetectionEvidence(source="requirements.txt", confidence=Confidence.HIGH)]
    sub = SubprojectInfo(
        name="api",
        path="services/api",
        runtimes=[RuntimeInfo(name="python", version=">=3.11", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pip", evidence=ev)],
    )
    project = ProjectInfo(
        path=str(tmp_path),
        name="monorepo",
        is_monorepo=True,
        subprojects=[sub],
    )

    env = _make_env([
        EnvironmentCheck(name="git", status=EnvironmentStatus.OK, installed_version="2.45.0"),
        EnvironmentCheck(name="python", status=EnvironmentStatus.OK, installed_version="3.12.3", required=True),
        EnvironmentCheck(name="pip", status=EnvironmentStatus.OK, installed_version="uv (0.12.5)", required=True),
        EnvironmentCheck(name="uv", status=EnvironmentStatus.OK, installed_version="0.12.5"),
    ])

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    step_ids = [s.id for s in plan.steps]
    assert "create-venv:api" in step_ids

    create_step = next(s for s in plan.steps if s.id == "create-venv:api")
    assert create_step.cwd == "services/api"
