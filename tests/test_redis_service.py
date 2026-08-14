"""Unit tests for RedisManager provisioning and rollback."""

from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.services.models import RedisConfig, ServiceType
from runrepo.services.redis import RedisManager
from runrepo.services.registry import InfrastructureRegistry


def test_redis_manager_provision_success(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path / ".state")
    executor = MockProcessExecutor()
    cfg = RedisConfig(
        container_name="runrepo-testapp-redis",
        host_port=6379,
    )

    success, msg, res = RedisManager.provision(
        config=cfg,
        project_path=str(tmp_path),
        executor=executor,
        registry=reg,
    )

    assert success is True
    assert "started on port 6379" in msg
    assert res is not None
    assert res.name == "runrepo-testapp-redis"
    assert res.service_type == ServiceType.REDIS

    # Registry has container
    tracked = reg.list_resources(repo_path=tmp_path)
    assert len(tracked) == 1
    assert tracked[0].name == "runrepo-testapp-redis"


def test_redis_manager_provision_rollback_on_failure(tmp_path):
    reg = InfrastructureRegistry(state_dir=tmp_path / ".state")
    executor = MockProcessExecutor(
        default_response=ProcessExecutionResult(exit_code=1, stderr="port 6379 in use")
    )
    cfg = RedisConfig(
        container_name="runrepo-testapp-redis",
        host_port=6379,
        volume_name="redisdata_test",
    )

    success, msg, res = RedisManager.provision(
        config=cfg,
        project_path=str(tmp_path),
        executor=executor,
        registry=reg,
    )

    assert success is False
    assert "Failed to start Redis" in msg
    assert res is None

    # Verify rollback was called
    rm_cmds = [cmd for cmd in executor.executed_commands if "rm" in cmd[0]]
    assert len(rm_cmds) >= 1
    assert len(reg.list_resources()) == 0
