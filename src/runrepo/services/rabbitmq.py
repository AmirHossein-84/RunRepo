"""RabbitMQ message broker container provisioner with health checks and rollback support."""

from runrepo.executor.process import ProcessExecutor
from runrepo.services.docker import DockerManager
from runrepo.services.models import DockerContainerConfig, OwnedResource, RabbitMQConfig, ResourceType, ServiceType
from runrepo.services.registry import InfrastructureRegistry


class RabbitMQManager:
    """Provisions and manages standalone RabbitMQ containers with management UI."""

    @classmethod
    def create_container_config(cls, config: RabbitMQConfig, project_path: str) -> DockerContainerConfig:
        """Translate RabbitMQConfig to DockerContainerConfig with RunRepo tracking labels."""
        env_vars = {
            "RABBITMQ_DEFAULT_USER": config.username,
            "RABBITMQ_DEFAULT_PASS": config.password,
        }
        volumes = [f"{config.volume_name}:/var/lib/rabbitmq"] if config.volume_name else []
        labels = {
            "runrepo.service": "rabbitmq",
            "runrepo.project_path": project_path,
        }
        healthcheck_cmd = ["rabbitmq-diagnostics", "-q", "ping"]

        return DockerContainerConfig(
            image=config.image,
            container_name=config.container_name,
            host_port=config.host_port,
            container_port=5672,
            env_vars=env_vars,
            volumes=volumes,
            healthcheck_cmd=healthcheck_cmd,
            labels=labels,
        )

    @classmethod
    def provision(
        cls,
        config: RabbitMQConfig,
        project_path: str,
        executor: ProcessExecutor,
        registry: InfrastructureRegistry | None = None,
    ) -> tuple[bool, str, OwnedResource | None]:
        """Provision a RabbitMQ container, registering ownership or rolling back on failure."""
        container_config = cls.create_container_config(config, project_path)

        res = DockerManager.run_container(container_config, executor)
        if res.exit_code != 0:
            DockerManager.remove_container(config.container_name, executor, force=True)
            if config.volume_name:
                DockerManager.remove_volume(config.volume_name, executor)
            err_msg = res.stderr.strip() or f"Docker exited with code {res.exit_code}"
            return False, f"Failed to start RabbitMQ container: {err_msg}", None

        container_id = res.stdout.strip() or config.container_name
        resource = OwnedResource(
            resource_type=ResourceType.CONTAINER,
            id=container_id,
            name=config.container_name,
            service_type=ServiceType.RABBITMQ,
            project_path=project_path,
            ports=[config.host_port, config.mgmt_port],
            labels=container_config.labels,
        )

        if registry:
            registry.register(resource)

        return True, f"RabbitMQ container '{config.container_name}' started successfully on ports {config.host_port} and {config.mgmt_port}", resource
