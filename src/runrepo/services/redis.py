"""Redis cache container provisioner with health checks and rollback support."""

from runrepo.executor.process import ProcessExecutor
from runrepo.services.docker import DockerManager
from runrepo.services.models import DockerContainerConfig, OwnedResource, RedisConfig, ResourceType, ServiceType
from runrepo.services.registry import InfrastructureRegistry


class RedisManager:
    """Provisions and manages standalone Redis containers for projects requiring in-memory cache/queues."""

    @classmethod
    def create_container_config(cls, config: RedisConfig, project_path: str) -> DockerContainerConfig:
        """Translate RedisConfig to DockerContainerConfig with RunRepo tracking labels."""
        volumes = [f"{config.volume_name}:/data"] if config.volume_name else []
        labels = {
            "runrepo.service": "redis",
            "runrepo.project_path": project_path,
        }
        healthcheck_cmd = ["redis-cli", "ping"]

        return DockerContainerConfig(
            image=config.image,
            container_name=config.container_name,
            host_port=config.host_port,
            container_port=6379,
            volumes=volumes,
            healthcheck_cmd=healthcheck_cmd,
            labels=labels,
        )

    @classmethod
    def provision(
        cls,
        config: RedisConfig,
        project_path: str,
        executor: ProcessExecutor,
        registry: InfrastructureRegistry | None = None,
    ) -> tuple[bool, str, OwnedResource | None]:
        """Provision a Redis container, registering ownership or rolling back on failure."""
        container_config = cls.create_container_config(config, project_path)

        # 1. Run container
        res = DockerManager.run_container(container_config, executor)
        if res.exit_code != 0:
            # Perform rollback
            DockerManager.remove_container(config.container_name, executor, force=True)
            if config.volume_name:
                DockerManager.remove_volume(config.volume_name, executor)
            err_msg = res.stderr.strip() or f"Docker exited with code {res.exit_code}"
            return False, f"Failed to start Redis container: {err_msg}", None

        # 2. Register ownership
        container_id = res.stdout.strip() or config.container_name
        resource = OwnedResource(
            resource_type=ResourceType.CONTAINER,
            id=container_id,
            name=config.container_name,
            service_type=ServiceType.REDIS,
            project_path=project_path,
            ports=[config.host_port],
            labels={"runrepo.managed": "true", "runrepo.service": "redis"},
        )

        if registry is not None:
            registry.register_resource(resource)
            if config.volume_name:
                registry.register_resource(
                    OwnedResource(
                        resource_type=ResourceType.VOLUME,
                        id=config.volume_name,
                        name=config.volume_name,
                        service_type=ServiceType.REDIS,
                        project_path=project_path,
                        labels={"runrepo.managed": "true", "runrepo.service": "redis"},
                    )
                )

        return True, f"Redis container '{config.container_name}' started on port {config.host_port}", resource
