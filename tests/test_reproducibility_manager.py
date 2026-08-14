"""Unit tests for ReproducibilityManager lifecycle (load, generate, drift check)."""

from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.models import PackageManagerInfo, ProjectInfo, ProjectScript, ProjectType
from runrepo.planner.models import ActionType, ExecutionPlan, PlanStatus, PlanStep, RiskLevel
from runrepo.reproducibility.manager import ReproducibilityManager


def test_reproducibility_manager_generate_and_reload(tmp_path):
    mgr = ReproducibilityManager(tmp_path)

    project_info = ProjectInfo(
        path=str(tmp_path),
        name="test-project",
        project_type=ProjectType.WEB_APPLICATION,
        package_managers=[PackageManagerInfo(name="uv")],
        scripts=[ProjectScript(name="dev", command="uvicorn main:app --reload")],
    )

    env_state = EnvironmentState(
        platform="windows",
        architecture="x86_64",
        checks=[
            EnvironmentCheck(
                name="python",
                status=EnvironmentStatus.OK,
                installed_version="3.12.2",
            )
        ],
    )

    plan = ExecutionPlan(
        repository_path=str(tmp_path),
        project_info=project_info,
        environment_state=env_state,
        status=PlanStatus.READY,
        steps=[
            PlanStep(
                id="start-app",
                description="Start application",
                action_type=ActionType.START_APPLICATION,
                command=["uvicorn", "main:app", "--reload"],
                risk=RiskLevel.REQUIRES_CONFIRMATION,
                reason="Launch dev server",
            )
        ],
    )

    lock = mgr.generate_lockfile(project_info, env_state, plan)
    assert lock is not None
    assert (tmp_path / "runrepo.lock").is_file()

    # Reload from disk
    loaded_lock = mgr.load_lockfile()
    assert loaded_lock is not None
    assert loaded_lock.resolved_package_manager == "uv"
    assert loaded_lock.resolved_startup.command == ["uvicorn", "main:app", "--reload"]

    # Check drift is clean
    diff = mgr.check_drift(project_info, env_state, plan)
    assert diff is not None
    assert diff.has_changes is False
