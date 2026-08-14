"""Security tests ensuring zero plaintext secrets or tokens are stored in runrepo.lock."""

from runrepo.environment.models import EnvironmentState
from runrepo.models import DetectionEvidence, EnvironmentVariable, EnvVarCategory, ProjectInfo
from runrepo.planner.models import ExecutionPlan, PlanStatus
from runrepo.reproducibility.manager import ReproducibilityManager


def test_lockfile_never_contains_secret_values(tmp_path):
    mgr = ReproducibilityManager(tmp_path)

    project_info = ProjectInfo(
        path=str(tmp_path),
        name="secure-app",
        environment_variables=[
            EnvironmentVariable(
                name="DATABASE_PASSWORD",
                default_value="super_secret_db_pass_12345",
                is_required=True,
                category=EnvVarCategory.SECRET,
            ),
            EnvironmentVariable(
                name="JWT_SECRET",
                default_value="my_jwt_secret_token_abcdef",
                is_required=True,
                category=EnvVarCategory.SECRET,
            ),
            EnvironmentVariable(
                name="PORT",
                default_value="3000",
                is_required=False,
                category=EnvVarCategory.LOCAL_DEFAULT,
            ),
        ],
    )

    env_state = EnvironmentState(platform="windows", architecture="x86_64")
    plan = ExecutionPlan(
        repository_path=str(tmp_path),
        project_info=project_info,
        environment_state=env_state,
        status=PlanStatus.READY,
    )

    lock = mgr.generate_lockfile(project_info, env_state, plan)
    lockfile_content = (tmp_path / "runrepo.lock").read_text(encoding="utf-8")

    # Sensitive values must NEVER be in the lockfile
    assert "super_secret_db_pass_12345" not in lockfile_content
    assert "my_jwt_secret_token_abcdef" not in lockfile_content
    assert "3000" not in lockfile_content  # even default values are excluded from lockfile env metadata

    # Only variable names and metadata are recorded
    assert "DATABASE_PASSWORD" in lockfile_content
    assert "JWT_SECRET" in lockfile_content
    assert "PORT" in lockfile_content
