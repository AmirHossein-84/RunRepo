"""Integration tests for ExecutionEngine coordinating plan DAGs."""

from pathlib import Path
from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.executor.confirmation import AutoConfirmationHandler, NonInteractiveConfirmationHandler
from runrepo.executor.executor import ExecutionEngine
from runrepo.executor.models import ExecutionStatus
from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.executor.process_manager import ProcessManager
from runrepo.models import Confidence, DetectionEvidence, PackageManagerInfo, ProjectInfo, ProjectScript, ProjectType, RuntimeInfo
from runrepo.planner.models import ExecutionPlan, PlanStatus
from runrepo.planner.planner import ExecutionPlanner


def _make_plan(project_path: Path, plan_status: PlanStatus = PlanStatus.READY) -> ExecutionPlan:
    ev = [DetectionEvidence(source="package.json", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path=str(project_path),
        name="web-app",
        project_type=ProjectType.WEB_APPLICATION,
        runtimes=[RuntimeInfo(name="node", version=">=22", evidence=ev)],
        package_managers=[PackageManagerInfo(name="pnpm", evidence=ev)],
        scripts=[ProjectScript(name="dev", command="vite", evidence=ev)],
    )

    env = EnvironmentState(
        checks=[
            EnvironmentCheck(name="node", status=EnvironmentStatus.OK, installed_version="22.15.0", required=True),
            EnvironmentCheck(name="pnpm", status=EnvironmentStatus.OK, installed_version="10.12.1", required=True),
        ],
        platform="Windows 11",
        architecture="x86_64",
        is_satisfied=True,
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)
    if plan_status != PlanStatus.READY:
        plan.status = plan_status
    return plan


def test_execution_engine_success(tmp_path):
    plan = _make_plan(tmp_path)
    executor = MockProcessExecutor()
    pm = ProcessManager(state_dir=tmp_path / ".runrepo_state")

    engine = ExecutionEngine(
        executor=executor,
        confirmation=AutoConfirmationHandler(),
        process_manager=pm,
    )

    result = engine.execute(plan)

    assert result.status == ExecutionStatus.SUCCESS
    assert "install-deps" in result.successful_steps
    assert "start-app" in result.successful_steps
    assert len(result.failed_steps) == 0
    assert len(result.skipped_steps) == 0


def test_execution_engine_failed_step_halts_downstream(tmp_path):
    plan = _make_plan(tmp_path)
    executor = MockProcessExecutor()
    # Configure pnpm install to fail
    executor.register_response(
        ["pnpm", "install"],
        ProcessExecutionResult(
            stdout="",
            stderr="ERR_PNPM_FETCH_404: Package not found",
            exit_code=1,
            duration_ms=25.0,
        ),
    )

    pm = ProcessManager(state_dir=tmp_path / ".runrepo_state")
    engine = ExecutionEngine(
        executor=executor,
        confirmation=AutoConfirmationHandler(),
        process_manager=pm,
    )

    result = engine.execute(plan)

    assert result.status == ExecutionStatus.FAILED
    assert "install-deps" in result.failed_steps
    assert "start-app" in result.skipped_steps
    assert "verify-app" in result.skipped_steps


def test_execution_engine_cancelled_confirmation(tmp_path):
    plan = _make_plan(tmp_path)
    executor = MockProcessExecutor()
    pm = ProcessManager(state_dir=tmp_path / ".runrepo_state")

    # Non-interactive without --yes will reject REQUIRES_CONFIRMATION
    engine = ExecutionEngine(
        executor=executor,
        confirmation=NonInteractiveConfirmationHandler(),
        process_manager=pm,
    )

    result = engine.execute(plan)

    assert result.status == ExecutionStatus.CANCELLED
    assert "install-deps" in result.skipped_steps or any(s.status == ExecutionStatus.CANCELLED for s in result.steps)


def test_execution_engine_blocked_plan(tmp_path):
    plan = _make_plan(tmp_path, plan_status=PlanStatus.BLOCKED)
    plan.blocking_reasons.append("Missing Node runtime")

    executor = MockProcessExecutor()
    engine = ExecutionEngine(
        executor=executor,
        confirmation=AutoConfirmationHandler(),
        process_manager=ProcessManager(state_dir=tmp_path / ".runrepo_state"),
    )

    result = engine.execute(plan)

    assert result.status == ExecutionStatus.BLOCKED
    assert len(executor.executed_commands) == 0


def test_execution_engine_dry_run(tmp_path):
    plan = _make_plan(tmp_path)
    executor = MockProcessExecutor()
    pm = ProcessManager(state_dir=tmp_path / ".runrepo_state")

    engine = ExecutionEngine(
        executor=executor,
        confirmation=AutoConfirmationHandler(),
        process_manager=pm,
    )

    result = engine.execute(plan, dry_run=True)

    assert result.status == ExecutionStatus.SUCCESS
    assert len(executor.executed_commands) == 0
    assert len(executor.background_commands) == 0
