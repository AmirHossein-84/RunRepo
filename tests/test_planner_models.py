"""Unit tests for Planner domain models and serialization."""

import json
from runrepo.environment.models import EnvironmentState, EnvironmentStatus
from runrepo.models import ProjectInfo, ProjectType
from runrepo.planner.models import (
    ActionType,
    ExecutionPlan,
    PlanStatus,
    PlanStep,
    RiskLevel,
    StepRollback,
    StepVerification,
)


def test_plan_step_model():
    step = PlanStep(
        id="install-deps:root",
        description="Install project dependencies",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        command=["pnpm", "install"],
        cwd=".",
        depends_on=["verify-runtime:node", "verify-pm:pnpm"],
        risk=RiskLevel.REQUIRES_CONFIRMATION,
        reason="pnpm-lock.yaml detected",
        verification=StepVerification(strategy="exit_code", description="pnpm install returns 0"),
        rollback=StepRollback(strategy="remove_directory", description="Remove node_modules"),
    )

    assert step.id == "install-deps:root"
    assert step.action_type == ActionType.INSTALL_DEPENDENCIES
    assert step.risk == RiskLevel.REQUIRES_CONFIRMATION
    assert step.command == ["pnpm", "install"]


def test_execution_plan_serialization():
    project = ProjectInfo(path="/repo", name="test-app", project_type=ProjectType.WEB_APPLICATION)
    env = EnvironmentState(platform="Windows 11", architecture="x86_64", is_satisfied=True)
    step = PlanStep(
        id="verify-runtime:node",
        description="Verify Node runtime",
        action_type=ActionType.VERIFY_RUNTIME,
        risk=RiskLevel.SAFE,
        reason="Node >=22 required",
        is_satisfied=True,
    )

    plan = ExecutionPlan(
        repository_path="/repo",
        project_info=project,
        environment_state=env,
        status=PlanStatus.READY,
        steps=[step],
        warnings=[],
        blocking_reasons=[],
    )

    json_data = json.loads(plan.model_dump_json())
    assert json_data["status"] == "READY"
    assert len(json_data["steps"]) == 1
    assert json_data["steps"][0]["id"] == "verify-runtime:node"
