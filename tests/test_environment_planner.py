"""Unit tests for ExecutionPlanner consuming analyzed environment facts."""

from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.models import (
    Confidence,
    DetectionEvidence,
    EnvVarCategory,
    EnvironmentVariable,
    ProjectInfo,
    ProjectType,
)
from runrepo.planner.models import ActionType, PlanStatus, RiskLevel
from runrepo.planner.planner import ExecutionPlanner


def test_planner_creates_configure_env_for_local_defaults():
    project = ProjectInfo(
        path="/repo",
        name="testapp",
        project_type=ProjectType.WEB_APPLICATION,
        environment_variables=[
            EnvironmentVariable(
                name="PORT",
                default_value="3000",
                is_required=True,
                category=EnvVarCategory.LOCAL_DEFAULT,
                evidence=[DetectionEvidence(source=".env.example", confidence=Confidence.HIGH)],
            )
        ],
    )

    env = EnvironmentState(
        checks=[],
        platform="Windows 11",
        architecture="x86_64",
        is_satisfied=True,
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    env_steps = [s for s in plan.steps if s.action_type == ActionType.CONFIGURE_ENV]
    assert len(env_steps) == 1
    assert env_steps[0].id == "configure-env:template"
    assert env_steps[0].risk == RiskLevel.REQUIRES_CONFIRMATION


def test_planner_sets_needs_input_for_missing_external_secrets():
    project = ProjectInfo(
        path="/repo",
        name="testapp",
        project_type=ProjectType.WEB_APPLICATION,
        environment_variables=[
            EnvironmentVariable(
                name="OPENAI_API_KEY",
                default_value=None,
                is_required=True,
                category=EnvVarCategory.EXTERNAL_SERVICE,
                evidence=[DetectionEvidence(source=".env.example", confidence=Confidence.HIGH)],
            )
        ],
    )

    env = EnvironmentState(
        checks=[],
        platform="Windows 11",
        architecture="x86_64",
        is_satisfied=True,
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    assert plan.status == PlanStatus.NEEDS_INPUT
    assert any("OPENAI_API_KEY" in r for r in plan.input_reasons)
    env_steps = [s for s in plan.steps if s.action_type == ActionType.CONFIGURE_ENV]
    assert len(env_steps) == 1
    assert env_steps[0].id == "configure-env:secrets"
