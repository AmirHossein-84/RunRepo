"""Unit tests for individual StepHandlers."""

from pathlib import Path
from runrepo.executor.handlers import (
    ApplicationStepHandler,
    EnvConfigStepHandler,
    InstallDepsStepHandler,
    MigrationStepHandler,
    ServiceStepHandler,
    VerifyStepHandler,
)
from runrepo.executor.models import ExecutionStatus
from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep, RiskLevel


def test_verify_step_handler(tmp_path):
    handler = VerifyStepHandler()
    step = PlanStep(
        id="verify-runtime:node",
        description="Verify Node runtime",
        action_type=ActionType.VERIFY_RUNTIME,
        risk=RiskLevel.SAFE,
        reason="Node satisfied",
        is_satisfied=True,
    )

    res = handler.execute(step, tmp_path, MockProcessExecutor(), ProcessManager(state_dir=tmp_path))
    assert res.status == ExecutionStatus.SUCCESS
    assert res.verification_passed is True


def test_env_config_step_handler(tmp_path):
    handler = EnvConfigStepHandler()
    (tmp_path / ".env.example").write_text("DATABASE_URL=postgres://localhost\n", encoding="utf-8")

    step = PlanStep(
        id="configure-env:template",
        description="Configure env from template",
        action_type=ActionType.CONFIGURE_ENV,
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="template exists",
    )

    res = handler.execute(step, tmp_path, MockProcessExecutor(), ProcessManager(state_dir=tmp_path))
    assert res.status == ExecutionStatus.SUCCESS
    assert (tmp_path / ".env").exists()
    assert "DATABASE_URL" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_install_deps_step_handler(tmp_path):
    handler = InstallDepsStepHandler()
    step = PlanStep(
        id="install-deps",
        description="Install dependencies",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        command=["pnpm", "install"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="pnpm lockfile detected",
    )

    executor = MockProcessExecutor()
    executor.register_response(
        ["pnpm", "install"],
        ProcessExecutionResult(stdout="Installed packages", stderr="", exit_code=0, duration_ms=50.0),
    )

    res = handler.execute(step, tmp_path, executor, ProcessManager(state_dir=tmp_path))
    assert res.status == ExecutionStatus.SUCCESS
    assert res.exit_code == 0


def test_service_step_handler_docker_compose(tmp_path):
    handler = ServiceStepHandler()
    step = PlanStep(
        id="start-service:docker-compose",
        description="Start services with Docker Compose",
        action_type=ActionType.START_SERVICE,
        command=["docker", "compose", "up", "-d"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="compose.yaml present",
    )

    executor = MockProcessExecutor()
    res = handler.execute(step, tmp_path, executor, ProcessManager(state_dir=tmp_path))
    assert res.status == ExecutionStatus.SUCCESS


def test_migration_step_handler(tmp_path):
    handler = MigrationStepHandler()
    step = PlanStep(
        id="generate-client:prisma",
        description="Generate Prisma Client",
        action_type=ActionType.GENERATE_CLIENT,
        command=["npx", "prisma", "generate"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="prisma schema detected",
    )

    executor = MockProcessExecutor()
    res = handler.execute(step, tmp_path, executor, ProcessManager(state_dir=tmp_path))
    assert res.status == ExecutionStatus.SUCCESS


def test_application_step_handler_start(tmp_path):
    handler = ApplicationStepHandler()
    step = PlanStep(
        id="start-app",
        description="Start application",
        action_type=ActionType.START_APPLICATION,
        command=["pnpm", "run", "dev"],
        risk=RiskLevel.SAFE,
        reason="dev script detected",
    )

    executor = MockProcessExecutor()
    pm = ProcessManager(state_dir=tmp_path)
    res = handler.execute(step, tmp_path, executor, pm)

    assert res.status == ExecutionStatus.SUCCESS
    assert "Application started in background" in res.stdout
    procs = pm.list_processes(repo_path=tmp_path)
    assert len(procs) == 1
