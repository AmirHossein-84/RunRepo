"""Tests for safety boundaries, rollback behavior, and resource ownership protection."""

from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.services.docker import DockerManager
from runrepo.services.models import OwnedResource, PostgresConfig, ResourceType, ServiceType
from runrepo.services.ports import find_available_port
from runrepo.services.postgres import PostgresManager
from runrepo.services.registry import InfrastructureRegistry


def test_clean_does_not_touch_unregistered_containers(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path / ".state")
    executor = MockProcessExecutor()

    # Track only 1 resource
    res = OwnedResource(
        resource_type=ResourceType.CONTAINER,
        id="c1",
        name="runrepo-testapp-postgres",
        service_type=ServiceType.POSTGRES,
        project_path=str(tmp_path),
    )
    reg.register_resource(res)

    # When cleaning this repo's resources
    resources = reg.list_resources(repo_path=tmp_path)
    assert len(resources) == 1

    for r in resources:
        DockerManager.remove_container(r.name, executor, force=True)
        reg.unregister_resource(r.id)

    assert len(reg.list_resources()) == 0
    # Verify ONLY the registered container name was removed
    assert len(executor.executed_commands) == 1
    assert "runrepo-testapp-postgres" in executor.executed_commands[0][0]


def test_registry_handles_empty_or_corrupt_json(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path / ".state")
    (tmp_path / ".state" / "registry.json").write_text("NOT_JSON_DATA", encoding="utf-8")

    # Should not raise exception
    res_list = reg.list_resources()
    assert res_list == []


def test_docker_daemon_stopped_detection():
    executor = MockProcessExecutor(
        custom_responses={"docker info": ProcessExecutionResult(exit_code=1, stderr="error response from daemon")}
    )
    assert DockerManager.is_daemon_running(executor) is False


def test_port_already_occupied_finds_next_port(monkeypatch):
    # Mock is_port_in_use to report 5432 is in use, but 5433 is free
    def mock_is_in_use(port, host="127.0.0.1"):
        return port == 5432

    monkeypatch.setattr("runrepo.services.ports.is_port_in_use", mock_is_in_use)

    port = find_available_port(5432)
    assert port == 5433


def test_rollback_on_failed_container_startup(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path / ".state")
    executor = MockProcessExecutor(
        default_response=ProcessExecutionResult(exit_code=125, stderr="docker: Error response from daemon: Conflict")
    )
    cfg = PostgresConfig(
        container_name="runrepo-test-postgres",
        database_name="test_dev",
        host_port=5432,
    )

    success, msg, res = PostgresManager.provision(cfg, str(tmp_path), executor, reg)
    assert success is False
    assert res is None
    # Container was cleaned up
    assert any("rm" in cmd[0] for cmd in executor.executed_commands)
