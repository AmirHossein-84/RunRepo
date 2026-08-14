"""Unit tests for planner applying runrepo.yaml configuration overrides."""

from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.models import FrameworkCategory, FrameworkInfo, PackageManagerInfo, ProjectInfo, ProjectScript, ProjectType, RuntimeInfo
from runrepo.planner.models import ActionType, PlanStatus
from runrepo.planner.planner import ExecutionPlanner
from runrepo.reproducibility.models import RunRepoConfig, StartupConfig


def test_planner_applies_startup_override():
    project_info = ProjectInfo(
        path=".",
        name="test",
        project_type=ProjectType.WEB_APPLICATION,
        runtimes=[RuntimeInfo(name="python", version=">=3.11")],
        package_managers=[PackageManagerInfo(name="uv")],
        frameworks=[FrameworkInfo(name="FastAPI", category=FrameworkCategory.WEB_BACKEND)],
        scripts=[ProjectScript(name="dev", command="uvicorn main:app --reload")],
    )

    env_state = EnvironmentState(
        platform="windows",
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
                installed_version="0.1.0",
                detected_version="0.1.0",
            ),
        ],
    )

    config = RunRepoConfig(
        startup=StartupConfig(command="uvicorn custom_app:server --port 9000 --reload")
    )

    planner = ExecutionPlanner()
    plan = planner.plan(project_info, env_state, config=config)

    start_step = next((s for s in plan.steps if s.action_type == ActionType.START_APPLICATION), None)
    assert start_step is not None
    assert start_step.command == ["uvicorn", "custom_app:server", "--port", "9000", "--reload"]
