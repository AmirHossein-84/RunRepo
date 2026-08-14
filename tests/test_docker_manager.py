"""Unit tests for DockerManager command formatting and process execution."""

from runrepo.executor.process import MockProcessExecutor, ProcessExecutionResult
from runrepo.services.docker import DockerManager
from runrepo.services.models import DockerContainerConfig


def test_build_run_command():
    cfg = DockerContainerConfig(
        image="postgres:16-alpine",
        container_name="test-pg",
        host_port=5432,
        container_port=5432,
        env_vars={"POSTGRES_DB": "app_dev", "POSTGRES_PASSWORD": "secret"},
        volumes=["pgdata:/var/lib/postgresql/data"],
        healthcheck_cmd=["pg_isready", "-U", "postgres"],
        labels={"runrepo.service": "postgres"},
    )

    cmd = DockerManager.build_run_command(cfg)
    assert cmd[0] == "docker"
    assert cmd[1] == "run"
    assert "-d" in cmd
    assert "--name" in cmd
    assert "test-pg" in cmd
    assert "-p" in cmd
    assert "5432:5432" in cmd
    assert "-e" in cmd
    assert "POSTGRES_DB=app_dev" in cmd
    assert "-v" in cmd
    assert "pgdata:/var/lib/postgresql/data" in cmd
    assert "--label" in cmd
    assert "runrepo.managed=true" in cmd
    assert "postgres:16-alpine" in cmd


def test_docker_manager_run_and_stop():
    executor = MockProcessExecutor()
    cfg = DockerContainerConfig(
        image="redis:7-alpine",
        container_name="test-redis",
        host_port=6379,
        container_port=6379,
    )

    run_res = DockerManager.run_container(cfg, executor)
    assert run_res.exit_code == 0
    assert len(executor.executed_commands) == 1
    assert "test-redis" in executor.executed_commands[0][0]

    stop_res = DockerManager.stop_container("test-redis", executor)
    assert stop_res.exit_code == 0
    assert "stop" in executor.executed_commands[1][0]


def test_docker_manager_is_docker_available():
    executor = MockProcessExecutor(custom_responses={"docker --version": ProcessExecutionResult(exit_code=0, stdout="Docker version 27.0.0")})
    assert DockerManager.is_docker_available(executor) is True

    failing_executor = MockProcessExecutor(custom_responses={"docker --version": ProcessExecutionResult(exit_code=1, stderr="not found")})
    assert DockerManager.is_docker_available(failing_executor) is False
