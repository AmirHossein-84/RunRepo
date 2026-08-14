"""MongoDB database container provisioner with health checks and rollback support."""

from runrepo.executor.process import ProcessExecutor
from runrepo.services.docker import DockerManager
from runrepo.services.models import DockerContainerConfig, MongoDBConfig, OwnedResource, ResourceType, ServiceType
from runrepo.services.registry import InfrastructureRegistry


class MongoDBManager:
    """Provisions and manages standalone MongoDB containers."""

    @classmethod
    def create_container_config(cls, config: MongoDBConfig, project_path: str) -> DockerContainerConfig:
        """Translate MongoDBConfig to DockerContainerConfig with RunRepo tracking labels."""
        env_vars = {}
        if config.username and config.password:
            env_vars["MONGO_INITDB_ROOT_USERNAME"] = config.username
            env_vars["MONGO_INITDB_ROOT_PASSWORD"] = config.password
        if config.database_name:
            env_vars["MONGO_INITDB_DATABASE"] = config.database_name

        volumes = [f"{config.volume_name}:/data/db"] if config.volume_name else []
        labels = {
            "runrepo.service": "mongodb",
            "runrepo.project_path": project_path,
        }
        healthcheck_cmd = ["mongosh", "--eval", "db.adminCommand('ping')"]

        return DockerContainerConfig(
            image=config.image,
            container_name=config.container_name,
            host_port=config.host_port,
            container_port=27017,
            env_vars=env_vars,
            volumes=volumes,
            healthcheck_cmd=healthcheck_cmd,
            labels=labels,
        )

    @classmethod
    def provision(
        cls,
        config: MongoDBConfig,
        project_path: str,
        executor: ProcessExecutor,
        registry: InfrastructureRegistry | None = None,
    ) -> tuple[bool, str, OwnedResource | None]:
        """Provision a MongoDB container, registering ownership or rolling back on failure."""
        container_config = cls.create_container_config(config, project_path)

        res = DockerManager.run_container(container_config, executor)
        if res.exit_code != 0:
            DockerManager.remove_container(config.container_name, executor, force=True)
            if config.volume_name:
                DockerManager.remove_volume(config.volume_name, executor)
            err_msg = res.stderr.strip() or f"Docker exited with code {res.exit_code}"
            return False, f"Failed to start MongoDB container: {err_msg}", None

        container_id = res.stdout.strip() or config.container_name
        resource = OwnedResource(
            resource_type=ResourceType.CONTAINER,
            id=container_id,
            name=config.container_name,
            service_type=ServiceType.MONGODB,
            project_path=project_path,
            ports=[config.host_port],
            labels=container_config.labels,
        )

        if registry:
            registry.register(resource)

        return True, f"MongoDB container '{config.container_name}' started successfully on port {config.host_port}", resource
