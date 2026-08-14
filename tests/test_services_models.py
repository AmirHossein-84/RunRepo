"""Unit tests for services domain models and serialization."""

import json
from runrepo.services.models import (
    DockerContainerConfig,
    OwnedResource,
    PostgresConfig,
    RedisConfig,
    ResourceType,
    ServiceStatus,
    ServiceType,
)


def test_owned_resource_serialization():
    res = OwnedResource(
        resource_type=ResourceType.CONTAINER,
        id="c123456789",
        name="runrepo-testapp-postgres",
        service_type=ServiceType.POSTGRES,
        project_path="/home/user/project",
        ports=[5432],
        labels={"runrepo.managed": "true", "runrepo.service": "postgres"},
    )

    data = json.loads(res.model_dump_json())
    assert data["resource_type"] == "CONTAINER"
    assert data["name"] == "runrepo-testapp-postgres"
    assert data["service_type"] == "POSTGRES"
    assert data["ports"] == [5432]
    assert data["labels"]["runrepo.managed"] == "true"


def test_docker_container_config():
    cfg = DockerContainerConfig(
        image="postgres:16-alpine",
        container_name="test-postgres",
        host_port=5432,
        container_port=5432,
        env_vars={"POSTGRES_PASSWORD": "secret"},
        labels={"runrepo.service": "postgres"},
    )

    assert cfg.image == "postgres:16-alpine"
    assert cfg.host_port == 5432
    assert cfg.env_vars["POSTGRES_PASSWORD"] == "secret"


def test_postgres_and_redis_configs():
    pg = PostgresConfig(
        container_name="pg-box",
        database_name="app_dev",
        host_port=5433,
    )
    assert pg.database_name == "app_dev"
    assert pg.host_port == 5433
    assert pg.username == "postgres"

    rd = RedisConfig(
        container_name="rd-box",
        host_port=6380,
    )
    assert rd.image == "redis:7-alpine"
    assert rd.host_port == 6380
