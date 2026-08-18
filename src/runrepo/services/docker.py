"""Docker operations manager constructing safe docker CLI commands and inspecting containers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runrepo.executor.process import ProcessExecutionResult, ProcessExecutor
from runrepo.services.models import DockerContainerConfig


class DockerManager:
    """Provides structured Docker container and volume management via the ProcessExecutor."""

    @classmethod
    def is_docker_available(cls, executor: ProcessExecutor) -> bool:
        """Check if docker CLI is available on the system PATH."""
        res = executor.execute(["docker", "--version"], timeout_s=3)
        return res.exit_code == 0

    @classmethod
    def is_daemon_running(cls, executor: ProcessExecutor) -> bool:
        """Check if the Docker daemon / Docker Desktop engine is responsive."""
        res = executor.execute(["docker", "info"], timeout_s=5)
        return res.exit_code == 0

    @classmethod
    def build_run_command(cls, config: DockerContainerConfig) -> list[str]:
        """Construct the deterministic `docker run` argument list."""
        cmd = ["docker", "run", "-d", "--name", config.container_name]

        # Port mapping
        if config.host_port and config.container_port:
            cmd.extend(["-p", f"{config.host_port}:{config.container_port}"])

        # Environment variables
        for k, v in sorted(config.env_vars.items()):
            cmd.extend(["-e", f"{k}={v}"])

        # Volume mounts
        for vol in config.volumes:
            cmd.extend(["-v", vol])

        # Network
        if config.network:
            cmd.extend(["--network", config.network])

        # Labels for ownership tracking
        labels = {"runrepo.managed": "true", **config.labels}
        for k, v in sorted(labels.items()):
            cmd.extend(["--label", f"{k}={v}"])

        # Healthcheck if configured
        if config.healthcheck_cmd:
            cmd.extend(["--health-cmd", " ".join(config.healthcheck_cmd), "--health-interval", "2s", "--health-retries", "10"])

        # Image specification
        image_spec = f"{config.image}:{config.tag}" if ":" not in config.image else config.image
        cmd.append(image_spec)

        return cmd

    @classmethod
    def run_container(cls, config: DockerContainerConfig, executor: ProcessExecutor) -> ProcessExecutionResult:
        """Execute `docker run -d` to spawn a managed container."""
        cmd = cls.build_run_command(config)
        return executor.execute(cmd, timeout_s=30)

    @classmethod
    def stop_container(cls, container_name: str, executor: ProcessExecutor) -> ProcessExecutionResult:
        """Stop a running container."""
        return executor.execute(["docker", "stop", container_name], timeout_s=15)

    @classmethod
    def remove_container(cls, container_name: str, executor: ProcessExecutor, force: bool = True) -> ProcessExecutionResult:
        """Remove a container (with force if requested)."""
        cmd = ["docker", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(container_name)
        return executor.execute(cmd, timeout_s=15)

    @classmethod
    def remove_volume(cls, volume_name: str, executor: ProcessExecutor) -> ProcessExecutionResult:
        """Remove a Docker volume."""
        return executor.execute(["docker", "volume", "rm", "-f", volume_name], timeout_s=10)

    @classmethod
    def inspect_container(cls, container_name: str, executor: ProcessExecutor) -> dict[str, Any] | None:
        """Inspect a container and return its structured metadata."""
        res = executor.execute(["docker", "inspect", container_name], timeout_s=5)
        if res.exit_code == 0 and res.stdout.strip():
            try:
                data = json.loads(res.stdout)
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
            except Exception:
                pass
        return None

    @classmethod
    def list_managed_containers(cls, executor: ProcessExecutor, project_path: str | None = None) -> list[dict[str, Any]]:
        """List containers tagged with RunRepo labels."""
        cmd = ["docker", "ps", "-a", "--filter", "label=runrepo.managed=true", "--format", "{{json .}}"]
        res = executor.execute(cmd, timeout_s=10)
        if res.exit_code != 0 or not res.stdout.strip():
            return []

        containers = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                containers.append(item)
            except Exception:
                pass
        return containers
