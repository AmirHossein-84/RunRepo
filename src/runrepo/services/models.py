"""Domain models for Docker services, infrastructure configurations, and resource ownership."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class ServiceType(StrEnum):
    """Types of infrastructure services managed by RunRepo."""

    DOCKER_COMPOSE = "DOCKER_COMPOSE"
    POSTGRES = "POSTGRES"
    REDIS = "REDIS"
    CUSTOM = "CUSTOM"


class ServiceStatus(StrEnum):
    """Lifecycle status of managed infrastructure services."""

    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    FAILED = "FAILED"


class ResourceType(StrEnum):
    """Classification of infrastructure resources for ownership and cleanup tracking."""

    CONTAINER = "CONTAINER"
    VOLUME = "VOLUME"
    NETWORK = "NETWORK"


class OwnedResource(BaseModel):
    """Record of a resource created and owned by RunRepo."""

    resource_type: ResourceType = Field(description="Type of resource (CONTAINER, VOLUME, NETWORK)")
    id: str = Field(description="Docker resource ID or unique name")
    name: str = Field(description="Human-readable resource name")
    service_type: ServiceType = Field(description="Associated service type")
    project_path: str = Field(description="Absolute path to the repository that owns this resource")
    ports: list[int] = Field(default_factory=list, description="Allocated host ports")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO UTC creation timestamp",
    )
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Docker metadata labels attached to the resource",
    )


class DockerContainerConfig(BaseModel):
    """Configuration for running a standalone Docker container."""

    image: str = Field(description="Container image name (e.g. postgres:16-alpine)")
    container_name: str = Field(description="Name assigned to the container")
    host_port: int | None = Field(default=None, description="Host port bound to container")
    container_port: int | None = Field(default=None, description="Internal container port")
    env_vars: dict[str, str] = Field(default_factory=dict, description="Environment variables passed to container")
    volumes: list[str] = Field(default_factory=list, description="Volume mount specifications (e.g. vol_name:/data)")
    network: str | None = Field(default=None, description="Docker network name")
    healthcheck_cmd: list[str] | None = Field(default=None, description="Health check command tokens")
    labels: dict[str, str] = Field(default_factory=dict, description="Docker labels attached for tracking")


class PostgresConfig(BaseModel):
    """Configuration for auto-provisioning a PostgreSQL database container."""

    image: str = Field(default="postgres:16-alpine", description="Docker image for PostgreSQL")
    container_name: str = Field(description="Unique container name (e.g. runrepo-webapp-postgres)")
    host_port: int = Field(default=5432, description="Host port mapped to PostgreSQL")
    database_name: str = Field(description="Default database name to initialize")
    username: str = Field(default="postgres", description="Database superuser username")
    password: str = Field(default="postgres", description="Database superuser password")
    volume_name: str | None = Field(default=None, description="Persistent volume name if enabled")


class RedisConfig(BaseModel):
    """Configuration for auto-provisioning a Redis cache container."""

    image: str = Field(default="redis:7-alpine", description="Docker image for Redis")
    container_name: str = Field(description="Unique container name (e.g. runrepo-webapp-redis)")
    host_port: int = Field(default=6379, description="Host port mapped to Redis")
    volume_name: str | None = Field(default=None, description="Persistent volume name if enabled")
