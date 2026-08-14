"""MinIO S3 object storage container provisioner with health checks and rollback support."""

from runrepo.executor.process import ProcessExecutor
from runrepo.services.docker import DockerManager
from runrepo.services.models import DockerContainerConfig, MinioConfig, OwnedResource, ResourceType, ServiceType
from runrepo.services.registry import InfrastructureRegistry


class MinioManager:
    """Provisions and manages standalone MinIO containers for local S3 simulation."""

    @classmethod
    def create_container_config(cls, config: MinioConfig, project_path: str) -> DockerContainerConfig:
        """Translate MinioConfig to DockerContainerConfig with RunRepo tracking labels."""
        env_vars = {
            "MINIO_ROOT_USER": config.root_user,
            "MINIO_ROOT_PASSWORD": config.root_password,
        }
        volumes = [f"{config.volume_name}:/data"] if config.volume_name else []
        labels = {
            "runrepo.service": "minio",
            "runrepo.project_path": project_path,
        }
        healthcheck_cmd = ["curl", "-f", f"http://localhost:{config.host_port}/minio/health/live"]

        return DockerContainerConfig(
            image=config.image,
            container_name=config.container_name,
            host_port=config.host_port,
            container_port=9000,
            env_vars=env_vars,
            volumes=volumes,
            healthcheck_cmd=healthcheck_cmd,
            labels=labels,
        )

    @classmethod
    def provision(
        cls,
        config: MinioConfig,
        project_path: str,
        executor: ProcessExecutor,
        registry: InfrastructureRegistry | None = None,
    ) -> tuple[bool, str, OwnedResource | None]:
        """Provision a MinIO container, registering ownership or rolling back on failure."""
        container_config = cls.create_container_config(config, project_path)

        res = DockerManager.run_container(container_config, executor)
        if res.exit_code != 0:
            DockerManager.remove_container(config.container_name, executor, force=True)
            if config.volume_name:
                DockerManager.remove_volume(config.volume_name, executor)
            err_msg = res.stderr.strip() or f"Docker exited with code {res.exit_code}"
            return False, f"Failed to start MinIO container: {err_msg}", None

        container_id = res.stdout.strip() or config.container_name
        resource = OwnedResource(
            resource_type=ResourceType.CONTAINER,
            id=container_id,
            name=config.container_name,
            service_type=ServiceType.MINIO,
            project_path=project_path,
            ports=[config.host_port, config.console_port],
            labels=container_config.labels,
        )

        if registry:
            registry.register(resource)

        return True, f"MinIO container '{config.container_name}' started successfully on ports {config.host_port} and {config.console_port}", resource
