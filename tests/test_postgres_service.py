"""Unit tests for PostgresManager provisioning and rollback."""

from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.services.models import PostgresConfig, ServiceType
from runrepo.services.postgres import PostgresManager
from runrepo.services.registry import InfrastructureRegistry


def test_postgres_manager_provision_success(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path / ".state")
    executor = MockProcessExecutor()
    cfg = PostgresConfig(
        container_name="runrepo-testapp-postgres",
        database_name="testapp_dev",
        host_port=5432,
    )

    success, msg, res = PostgresManager.provision(
        config=cfg,
        project_path=str(tmp_path),
        executor=executor,
        registry=reg,
    )

    assert success is True
    assert "started on port 5432" in msg
    assert res is not None
    assert res.name == "runrepo-testapp-postgres"
    assert res.service_type == ServiceType.POSTGRES

    # Registry has container
    tracked = reg.list_resources(repo_path=tmp_path)
    assert len(tracked) == 1
    assert tracked[0].name == "runrepo-testapp-postgres"


def test_postgres_manager_provision_rollback_on_failure(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path / ".state")
    # Simulate failed docker run
    executor = MockProcessExecutor(
        default_response=ProcessExecutionResult(exit_code=1, stderr="port 5432 already allocated")
    )
    cfg = PostgresConfig(
        container_name="runrepo-testapp-postgres",
        database_name="testapp_dev",
        host_port=5432,
        volume_name="pgdata_test",
    )

    success, msg, res = PostgresManager.provision(
        config=cfg,
        project_path=str(tmp_path),
        executor=executor,
        registry=reg,
    )

    assert success is False
    assert "Failed to start PostgreSQL" in msg
    assert res is None

    # Verify rollback was called (docker rm -f and docker volume rm)
    rm_cmds = [cmd for cmd in executor.executed_commands if "rm" in cmd[0]]
    assert len(rm_cmds) >= 1

    # Registry should be empty
    assert len(reg.list_resources()) == 0
