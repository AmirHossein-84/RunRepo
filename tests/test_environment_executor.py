"""Unit tests for environment manager execution, backup creation, and safe merging."""

from pathlib import Path
from runrepo.env.manager import EnvManager
from runrepo.env.models import EnvClassification, EnvRequirement
from runrepo.executor.handlers.env import EnvConfigStepHandler
from runrepo.executor.models import ExecutionStatus
from runrepo.executor.process import MockProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep, RiskLevel


def test_env_manager_backup_creation(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("PORT=3000\n", encoding="utf-8")

    backup_path = EnvManager.backup_env_file(env_file)
    assert backup_path is not None
    assert backup_path.exists()
    assert ".env.backup." in backup_path.name
    assert backup_path.read_text(encoding="utf-8") == "PORT=3000\n"


def test_env_manager_non_destructive_merge(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("PORT=8080\nCUSTOM_VAR=keep_me\n", encoding="utf-8")

    reqs = [
        EnvRequirement(name="PORT", classification=EnvClassification.LOCAL_DEFAULT, is_required=True, default_value="3000"),
        EnvRequirement(name="JWT_SECRET", classification=EnvClassification.AUTO_GENERATABLE, is_required=True),
        EnvRequirement(name="OPENAI_API_KEY", classification=EnvClassification.EXTERNAL_SERVICE, is_required=True),
    ]

    success, msg, added = EnvManager.apply_env_updates(
        root_path=tmp_path,
        requirements=reqs,
        include_external_stubs=True,
    )

    assert success is True
    assert "JWT_SECRET" in added
    assert "PORT" not in added  # Not overwritten

    updated_text = env_file.read_text(encoding="utf-8")
    assert "PORT=8080" in updated_text
    assert "CUSTOM_VAR=keep_me" in updated_text
    assert "JWT_SECRET=" in updated_text
    assert "# OPENAI_API_KEY=" in updated_text


def test_env_config_step_handler_execution(tmp_path):
    (tmp_path / ".env.example").write_text("APP_NAME=my_app\nJWT_SECRET=\n", encoding="utf-8")

    handler = EnvConfigStepHandler()
    step = PlanStep(
        id="configure-env",
        description="Configure .env",
        action_type=ActionType.CONFIGURE_ENV,
        risk=RiskLevel.SAFE,
        reason="Setup env",
    )

    executor = MockProcessExecutor()
    pm = ProcessManager()

    # Dry run
    dry_res = handler.execute(step, tmp_path, executor, pm, dry_run=True)
    assert dry_res.status == ExecutionStatus.SUCCESS
    assert "[dry-run]" in dry_res.stdout

    # Real run
    real_res = handler.execute(step, tmp_path, executor, pm, dry_run=False)
    assert real_res.status == ExecutionStatus.SUCCESS
    assert (tmp_path / ".env").exists()
    content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "APP_NAME=my_app" in content
    assert "JWT_SECRET=" in content
