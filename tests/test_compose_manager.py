"""Unit tests for ComposeManager finding files and running compose commands."""

from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.services.compose import ComposeManager
from runrepo.services.models import ServiceType
from runrepo.services.registry import InfrastructureRegistry


def test_compose_manager_find_file(tmp_path):
    assert ComposeManager.find_compose_file(tmp_path) is None

    (tmp_path / "compose.yaml").write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")
    found = ComposeManager.find_compose_file(tmp_path)
    assert found is not None
    assert found.name == "compose.yaml"


def test_compose_manager_up_and_register(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path / ".state")
    ps_json = '{"ID": "c100", "Name": "my-app-db-1", "Service": "db"}\n'
    executor = MockProcessExecutor(
        custom_responses={
            "docker compose ps --format json": ProcessExecutionResult(exit_code=0, stdout=ps_json),
        }
    )

    res = ComposeManager.up(cwd=tmp_path, executor=executor, project_path=str(tmp_path), registry=reg)
    assert res.exit_code == 0

    resources = reg.list_resources(repo_path=tmp_path)
    assert len(resources) == 1
    assert resources[0].name == "my-app-db-1"
    assert resources[0].service_type == ServiceType.DOCKER_COMPOSE


def test_compose_manager_down(tmp_path):
    executor = MockProcessExecutor()
    res = ComposeManager.down(cwd=tmp_path, executor=executor, remove_volumes=True)
    assert res.exit_code == 0
    assert "-v" in executor.executed_commands[0][0]
