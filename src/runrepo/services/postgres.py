"""PostgreSQL database container provisioner with health checks and rollback support."""

from runrepo.executor.process import ProcessExecutor
from runrepo.services.docker import DockerManager
from runrepo.services.models import DockerContainerConfig, OwnedResource, PostgresConfig, ResourceType, ServiceType
from runrepo.services.registry import InfrastructureRegistry


class PostgresManager:
    """Provisions and manages standalone PostgreSQL containers for projects requiring a database."""

    @classmethod
    def create_container_config(cls, config: PostgresConfig, project_path: str) -> DockerContainerConfig:
        """Translate PostgresConfig to DockerContainerConfig with RunRepo tracking labels."""
        env_vars = {
            "POSTGRES_DB": config.database_name,
            "POSTGRES_USER": config.username,
            "POSTGRES_PASSWORD": config.password,
        }
        volumes = [f"{config.volume_name}:/var/lib/postgresql/data"] if config.volume_name else []
        labels = {
            "runrepo.service": "postgres",
            "runrepo.project_path": project_path,
        }
        healthcheck_cmd = ["pg_isready", "-U", config.username, "-d", config.database_name]

        return DockerContainerConfig(
            image=config.image,
            container_name=config.container_name,
            host_port=config.host_port,
            container_port=5432,
            env_vars=env_vars,
            volumes=volumes,
            healthcheck_cmd=healthcheck_cmd,
            labels=labels,
        )

    @classmethod
    def provision(
        cls,
        config: PostgresConfig,
        project_path: str,
        executor: ProcessExecutor,
        registry: InfrastructureRegistry | None = None,
    ) -> tuple[bool, str, OwnedResource | None]:
        """Provision a PostgreSQL container, registering ownership or rolling back on failure."""
        container_config = cls.create_container_config(config, project_path)

        # 1. Run container
        res = DockerManager.run_container(container_config, executor)
        if res.exit_code != 0:
            # Perform rollback in case partial state was created
            DockerManager.remove_container(config.container_name, executor, force=True)
            if config.volume_name:
                DockerManager.remove_volume(config.volume_name, executor)
            err_msg = res.stderr.strip() or f"Docker exited with code {res.exit_code}"
            return False, f"Failed to start PostgreSQL container: {err_msg}", None

        # 2. Register ownership
        container_id = res.stdout.strip() or config.container_name
        resource = OwnedResource(
            resource_type=ResourceType.CONTAINER,
            id=container_id,
            name=config.container_name,
            service_type=ServiceType.POSTGRES,
            project_path=project_path,
            ports=[config.host_port],
            labels={"runrepo.managed": "true", "runrepo.service": "postgres"},
        )

        if registry is not None:
            registry.register_resource(resource)
            if config.volume_name:
                registry.register_resource(
                    OwnedResource(
                        resource_type=ResourceType.VOLUME,
                        id=config.volume_name,
                        name=config.volume_name,
                        service_type=ServiceType.POSTGRES,
                        project_path=project_path,
                        labels={"runrepo.managed": "true", "runrepo.service": "postgres"},
                    )
                )

        return True, f"PostgreSQL container '{config.container_name}' started on port {config.host_port}", resource
