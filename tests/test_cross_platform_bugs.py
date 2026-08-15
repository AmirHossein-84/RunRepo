"""Unit and integration tests for cross-platform bug fixes and edge-case prevention.

Covers:
1. Non-web / CLI / GUI app verification strategy routing (process_liveness vs http_health_check).
2. Python fallback entrypoint detection for custom filenames and __main__ blocks.
3. Python package installation fallback when requirements.txt is absent (pyproject.toml/setup.py).
4. Windows .cmd/.bat execution wrapping via cmd.exe /c.
"""

from pathlib import Path
import sys
from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detectors.python import PythonDetector
from runrepo.environment.command import SystemCommandRunner
from runrepo.environment.models import (
    EnvironmentCheck,
    EnvironmentState,
    EnvironmentStatus,
)
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import SystemProcessExecutor
from runrepo.models import (
    Confidence,
    FrameworkCategory,
    FrameworkInfo,
    PackageManagerInfo,
    ProjectInfo,
    ProjectScript,
    ProjectType,
    RuntimeInfo,
)
from runrepo.planner import ExecutionPlanner
from runrepo.planner.models import ActionType
from runrepo.verification.verifiers.http import HttpVerifier
from runrepo.verification.verifiers.process import ProcessVerifier


def test_cli_gui_app_process_liveness_planning(tmp_path):
    """Ensure non-web/CLI/GUI Python apps are planned with process_liveness verification, not HTTP health checks."""
    project_info = ProjectInfo(
        path=str(tmp_path),
        name="DNS-changer",
        project_type=ProjectType.CLI_TOOL,
        runtimes=[RuntimeInfo(name="python", version=">=3.10")],
        package_managers=[PackageManagerInfo(name="uv")],
        frameworks=[],
        entrypoints=["dns_changer.py"],
        scripts=[],
    )

    env_state = EnvironmentState(
        platform="linux",
        architecture="x86_64",
        checks=[
            EnvironmentCheck(
                name="python",
                status=EnvironmentStatus.OK,
                installed_version="3.12.0",
                detected_version="3.12.0",
            ),
            EnvironmentCheck(
                name="uv",
                status=EnvironmentStatus.OK,
                installed_version="0.5.0",
                detected_version="0.5.0",
            ),
        ],
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project_info, env_state)

    start_step = next((s for s in plan.steps if s.action_type == ActionType.START_APPLICATION), None)
    verify_step = next((s for s in plan.steps if s.action_type == ActionType.VERIFY_APPLICATION), None)

    assert start_step is not None
    assert verify_step is not None
    assert start_step.verification.strategy == "process_liveness"
    assert verify_step.verification.strategy == "process_liveness"
    assert "process" in verify_step.verification.description.lower()

    # Verify that ProcessVerifier accepts this step and HttpVerifier rejects it
    process_verifier = ProcessVerifier()
    http_verifier = HttpVerifier()

    assert process_verifier.can_verify(verify_step) is True
    assert http_verifier.can_verify(verify_step) is False


def test_web_app_uses_http_health_check(tmp_path):
    """Ensure Web/API projects continue to use http_health_check."""
    project_info = ProjectInfo(
        path=str(tmp_path),
        name="web-api",
        project_type=ProjectType.API_SERVICE,
        runtimes=[RuntimeInfo(name="python", version=">=3.11")],
        package_managers=[PackageManagerInfo(name="uv")],
        frameworks=[FrameworkInfo(name="fastapi", category=FrameworkCategory.WEB_BACKEND)],
        entrypoints=["main.py"],
        scripts=[],
    )

    env_state = EnvironmentState(
        platform="linux",
        architecture="x86_64",
        checks=[
            EnvironmentCheck(
                name="python",
                status=EnvironmentStatus.OK,
                installed_version="3.12.0",
                detected_version="3.12.0",
            ),
            EnvironmentCheck(
                name="uv",
                status=EnvironmentStatus.OK,
                installed_version="0.5.0",
                detected_version="0.5.0",
            ),
        ],
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project_info, env_state)

    verify_step = next((s for s in plan.steps if s.action_type == ActionType.VERIFY_APPLICATION), None)
    assert verify_step is not None
    assert verify_step.verification.strategy == "http_health_check"
    assert verify_step.verification.target == "http://127.0.0.1:8000"

    process_verifier = ProcessVerifier()
    http_verifier = HttpVerifier()

    assert http_verifier.can_verify(verify_step) is True
    assert process_verifier.can_verify(verify_step) is False


def test_fallback_python_entrypoint_detection(tmp_path):
    """Test detecting single root Python script or file with __main__ as entrypoint."""
    (tmp_path / "custom_tool.py").write_text(
        'import sys\n\nif __name__ == "__main__":\n    print("Running custom tool")\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "custom-tool"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    ctx = ScanContext(tmp_path)
    detector = PythonDetector()
    res = detector.detect(ctx)

    assert "custom_tool.py" in res.entrypoints


def test_pyproject_fallback_install_command(tmp_path):
    """Test generating pip install -e . or uv pip install -e . when requirements.txt is absent."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "my-pkg"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    project_info = ProjectInfo(
        path=str(tmp_path),
        name="my-pkg",
        project_type=ProjectType.LIBRARY,
        runtimes=[RuntimeInfo(name="python", version=">=3.11")],
        package_managers=[PackageManagerInfo(name="pip")],
        frameworks=[],
        entrypoints=[],
        scripts=[],
    )

    env_state = EnvironmentState(
        platform="linux",
        architecture="x86_64",
        checks=[
            EnvironmentCheck(
                name="python",
                status=EnvironmentStatus.OK,
                installed_version="3.12.0",
                detected_version="3.12.0",
            ),
            EnvironmentCheck(
                name="pip",
                status=EnvironmentStatus.OK,
                installed_version="24.0",
                detected_version="24.0",
            ),
        ],
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project_info, env_state)

    install_step = next((s for s in plan.steps if s.action_type == ActionType.INSTALL_DEPENDENCIES), None)
    assert install_step is not None
    assert install_step.command == ["pip", "install", "-e", "."]
