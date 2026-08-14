"""Unit tests for ExecutionPlanner generating infrastructure service steps."""

from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.models import (
    Confidence,
    DatabaseRequirement,
    DatabaseType,
    DetectionEvidence,
    DockerInfo,
    ProjectInfo,
    ProjectType,
    ServiceRequirement,
)
from runrepo.planner.models import ActionType, PlanStatus, RiskLevel
from runrepo.planner.planner import ExecutionPlanner


def test_planner_creates_compose_service_step():
    ev = [DetectionEvidence(source="compose.yaml", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="testapp",
        project_type=ProjectType.WEB_APPLICATION,
        docker=DockerInfo(compose_files=["compose.yaml"]),
    )

    env = EnvironmentState(
        checks=[
            EnvironmentCheck(name="docker", status=EnvironmentStatus.OK, installed_version="27.0.0", required=True),
            EnvironmentCheck(name="docker-compose", status=EnvironmentStatus.OK, installed_version="2.28.0", required=True),
        ],
        platform="Windows 11",
        architecture="x86_64",
        is_satisfied=True,
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    compose_steps = [s for s in plan.steps if s.id == "start-service:docker-compose"]
    assert len(compose_steps) == 1
    assert compose_steps[0].action_type == ActionType.START_SERVICE
    assert compose_steps[0].risk == RiskLevel.REQUIRES_CONFIRMATION


def test_planner_creates_standalone_postgres_step():
    ev = [DetectionEvidence(source="schema.prisma", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="testapp",
        project_type=ProjectType.WEB_APPLICATION,
        databases=[DatabaseRequirement(name=DatabaseType.POSTGRESQL, evidence=ev)],
    )

    env = EnvironmentState(
        checks=[
            EnvironmentCheck(name="docker", status=EnvironmentStatus.OK, installed_version="27.0.0", required=True),
            EnvironmentCheck(name="docker-compose", status=EnvironmentStatus.OK, installed_version="2.28.0", required=True),
        ],
        platform="Windows 11",
        architecture="x86_64",
        is_satisfied=True,
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    pg_steps = [s for s in plan.steps if s.id == "start-service:postgres"]
    assert len(pg_steps) == 1
    assert pg_steps[0].action_type == ActionType.START_SERVICE
    assert "postgres:16-alpine" in pg_steps[0].command[-1]


def test_planner_creates_standalone_redis_step():
    ev = [DetectionEvidence(source="requirements.txt", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="testapp",
        project_type=ProjectType.WEB_APPLICATION,
        services=[ServiceRequirement(name="redis", evidence=ev)],
    )

    env = EnvironmentState(
        checks=[
            EnvironmentCheck(name="docker", status=EnvironmentStatus.OK, installed_version="27.0.0", required=True),
            EnvironmentCheck(name="docker-compose", status=EnvironmentStatus.OK, installed_version="2.28.0", required=True),
        ],
        platform="Windows 11",
        architecture="x86_64",
        is_satisfied=True,
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    rd_steps = [s for s in plan.steps if s.id == "start-service:redis"]
    assert len(rd_steps) == 1
    assert rd_steps[0].action_type == ActionType.START_SERVICE
    assert "redis:7-alpine" in rd_steps[0].command[-1]


def test_planner_blocks_postgres_when_docker_missing():
    ev = [DetectionEvidence(source="schema.prisma", confidence=Confidence.HIGH)]
    project = ProjectInfo(
        path="/repo",
        name="testapp",
        project_type=ProjectType.WEB_APPLICATION,
        databases=[DatabaseRequirement(name=DatabaseType.POSTGRESQL, evidence=ev)],
    )

    env = EnvironmentState(
        checks=[
            EnvironmentCheck(name="docker", status=EnvironmentStatus.MISSING, details="Docker daemon not running", required=True),
        ],
        platform="Windows 11",
        architecture="x86_64",
        is_satisfied=False,
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project, env)

    assert plan.status == PlanStatus.BLOCKED
    pg_steps = [s for s in plan.steps if s.id == "start-service:postgres"]
    assert len(pg_steps) == 1
    assert pg_steps[0].is_blocked is True
