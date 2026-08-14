"""Component domain models (frameworks, scripts, env vars, databases, docker)."""

from enum import StrEnum
from pydantic import BaseModel, Field
from runrepo.models.evidence import DetectionEvidence


class FrameworkCategory(StrEnum):
    """Category classification for detected frameworks."""

    WEB_FRONTEND = "web_frontend"
    WEB_BACKEND = "web_backend"
    FULLSTACK = "fullstack"
    CLI = "cli"
    UI_LIBRARY = "ui_library"
    TESTING = "testing"
    OTHER = "other"


class FrameworkInfo(BaseModel):
    """Detected web or application framework."""

    name: str = Field(description="Framework name, e.g. 'Next.js', 'FastAPI', 'Express'")
    version: str | None = Field(default=None, description="Framework version if detected")
    category: FrameworkCategory = Field(
        default=FrameworkCategory.OTHER,
        description="High-level category of the framework",
    )
    evidence: list[DetectionEvidence] = Field(
        default_factory=list,
        description="Evidence supporting framework detection",
    )


class DependencyInfo(BaseModel):
    """Detected dependency or library requirement."""

    name: str = Field(description="Package/dependency name")
    version_spec: str | None = Field(default=None, description="Version specifier or constraint")
    is_dev: bool = Field(default=False, description="Whether this is a dev/test dependency")
    source_file: str | None = Field(default=None, description="File where dependency was declared")
    evidence: list[DetectionEvidence] = Field(default_factory=list)


class ProjectScript(BaseModel):
    """Runnable script or task declared in project configuration."""

    name: str = Field(description="Script key, e.g. 'dev', 'build', 'start', 'test'")
    command: str = Field(description="Command string to be executed")
    description: str | None = Field(default=None, description="Human readable description")
    evidence: list[DetectionEvidence] = Field(default_factory=list)


class EnvVarCategory(StrEnum):
    """Classification for environment variables."""

    DATABASE = "database"
    SECRET = "secret"
    LOCAL_DEFAULT = "local_default"
    EXTERNAL_SERVICE = "external_service"
    GENERAL = "general"


class EnvironmentVariable(BaseModel):
    """Detected environment variable requirement."""

    name: str = Field(description="Variable name, e.g. 'DATABASE_URL', 'PORT'")
    description: str | None = Field(default=None, description="Explanation or comment")
    default_value: str | None = Field(default=None, description="Default or placeholder value")
    is_required: bool = Field(default=True, description="Whether the variable is required to run")
    category: EnvVarCategory = Field(
        default=EnvVarCategory.GENERAL,
        description="Category classification",
    )
    evidence: list[DetectionEvidence] = Field(default_factory=list)


class DatabaseType(StrEnum):
    """Recognized database types."""

    POSTGRESQL = "postgresql"
    REDIS = "redis"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    UNKNOWN = "unknown"


class DatabaseRequirement(BaseModel):
    """Database requirement detected from ORM, config, env vars, or docker services."""

    name: DatabaseType = Field(description="Database type")
    version: str | None = Field(default=None, description="Database version if specified")
    orm: str | None = Field(default=None, description="ORM or migration tool, e.g. 'prisma', 'alembic'")
    connection_var: str | None = Field(default=None, description="Associated environment variable, e.g. 'DATABASE_URL'")
    evidence: list[DetectionEvidence] = Field(default_factory=list)


class ServiceRequirement(BaseModel):
    """Auxiliary background service requirement (e.g. Redis, RabbitMQ)."""

    name: str = Field(description="Service name, e.g. 'redis', 'rabbitmq'")
    service_type: str | None = Field(default=None, description="Type or purpose of service")
    image: str | None = Field(default=None, description="Associated Docker image if found")
    port: int | None = Field(default=None, description="Default or configured port")
    evidence: list[DetectionEvidence] = Field(default_factory=list)


class DockerComposeService(BaseModel):
    """Information extracted from a Docker Compose service definition."""

    name: str = Field(description="Service name in compose file")
    image: str | None = Field(default=None, description="Image reference, e.g. 'postgres:16'")
    build_context: str | None = Field(default=None, description="Build path if local Dockerfile")
    ports: list[str] = Field(default_factory=list, description="Exposed port mappings")
    environment_keys: list[str] = Field(default_factory=list, description="Referenced env variable keys")
    depends_on: list[str] = Field(default_factory=list, description="Declared service dependencies")


class DockerInfo(BaseModel):
    """Docker and container configuration detected in repository."""

    has_dockerfile: bool = Field(default=False, description="Whether Dockerfile is present")
    dockerfiles: list[str] = Field(default_factory=list, description="Relative paths to Dockerfiles")
    compose_files: list[str] = Field(default_factory=list, description="Relative paths to compose files")
    compose_services: list[DockerComposeService] = Field(
        default_factory=list,
        description="Services defined in compose configuration",
    )
    evidence: list[DetectionEvidence] = Field(default_factory=list)
