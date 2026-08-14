"""Unit tests for DiagnosticsEngine pre-flight, post-execution, and unknown failure handling."""

from rich.console import Console
from runrepo.diagnostics.diagnostics import DiagnosticsEngine
from runrepo.diagnostics.formatters import render_diagnostics_report
from runrepo.diagnostics.models import DiagnosticCategory, DiagnosticSeverity
from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.executor.models import ExecutionResult, ExecutionStatus, StepExecutionResult
from runrepo.models import ProjectInfo, ProjectType
from runrepo.planner.models import ActionType, ExecutionPlan, PlanStatus, PlanStep, RiskLevel


def test_diagnose_environment_missing_docker_and_runtime():
    env = EnvironmentState(
        checks=[
            EnvironmentCheck(name="docker", status=EnvironmentStatus.MISSING, details="daemon stopped", required=True),
            EnvironmentCheck(name="python", status=EnvironmentStatus.WRONG_VERSION, installed_version="3.9.0", required_version=">=3.11", required=True),
        ],
        platform="Windows 11",
        architecture="x86_64",
        is_satisfied=False,
    )

    engine = DiagnosticsEngine()
    diags = engine.diagnose_environment(env)
    assert len(diags) == 2

    categories = {d.category for d in diags}
    assert DiagnosticCategory.SERVICE in categories
    assert DiagnosticCategory.ENVIRONMENT in categories


def test_diagnose_execution_port_conflict():
    step = PlanStep(
        id="start-service:postgres",
        description="Start Postgres",
        action_type=ActionType.START_SERVICE,
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="db required",
    )
    project = ProjectInfo(path="/repo", name="testapp", project_type=ProjectType.WEB_APPLICATION)
    env = EnvironmentState(checks=[], platform="Windows 11", architecture="x86_64", is_satisfied=True)
    plan = ExecutionPlan(
        repository_path="/repo",
        project_info=project,
        environment_state=env,
        status=PlanStatus.READY,
        steps=[step],
    )

    exec_result = ExecutionResult(
        plan_id="test-plan",
        repository_path="/repo",
        status=ExecutionStatus.FAILED,
        total_duration_ms=100.0,
        steps=[
            StepExecutionResult(
                step_id="start-service:postgres",
                status=ExecutionStatus.FAILED,
                exit_code=1,
                stderr="Error response from daemon: driver failed programming external connectivity: Bind for 0.0.0.0:5432 failed: port is already allocated",
            )
        ],
    )

    engine = DiagnosticsEngine()
    diags = engine.diagnose_execution(exec_result, plan=plan)

    assert len(diags) == 1
    assert diags[0].category == DiagnosticCategory.NETWORK
    assert "Port Conflict" in diags[0].title
    assert len(diags[0].suggested_actions) >= 1


def test_diagnose_unknown_failure_fallback():
    exec_result = ExecutionResult(
        plan_id="test-plan",
        repository_path="/repo",
        status=ExecutionStatus.FAILED,
        total_duration_ms=50.0,
        steps=[
            StepExecutionResult(
                step_id="custom-step",
                status=ExecutionStatus.FAILED,
                exit_code=137,
                stderr="Killed by SIGKILL with unusual internal error code 99",
            )
        ],
    )

    engine = DiagnosticsEngine()
    diags = engine.diagnose_execution(exec_result)

    assert len(diags) == 1
    assert diags[0].category == DiagnosticCategory.UNKNOWN
    assert diags[0].exit_code == 137
    assert "Unrecognized Failure" in diags[0].title


def test_render_diagnostics_report_rich_output():
    console = Console(record=True, width=100)
    engine = DiagnosticsEngine()
    exec_result = ExecutionResult(
        plan_id="test-plan",
        repository_path="/repo",
        status=ExecutionStatus.FAILED,
        total_duration_ms=50.0,
        steps=[
            StepExecutionResult(
                step_id="install-deps",
                status=ExecutionStatus.FAILED,
                exit_code=1,
                stderr="npm ERR! code EACCES: permission denied",
            )
        ],
    )

    diags = engine.diagnose_execution(exec_result)
    render_diagnostics_report(diags, console)
    out = console.export_text()

    assert "RunRepo Diagnostic Failure Report" in out
    assert "PERMISSION" in out
    assert "Permission Denied" in out
