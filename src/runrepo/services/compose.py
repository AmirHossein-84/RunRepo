"""Docker Compose service manager handling compose lifecycle and resource tracking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runrepo.executor.process import ProcessExecutionResult, ProcessExecutor
from runrepo.services.models import OwnedResource, ResourceType, ServiceType
from runrepo.services.registry import InfrastructureRegistry


class ComposeManager:
    """Manages Docker Compose operations and tracks compose-generated resources."""

    COMPOSE_FILENAMES = ["compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"]

    @classmethod
    def find_compose_file(cls, directory: Path) -> Path | None:
        """Find the primary Docker Compose file in a directory or immediate subdirectories."""
        EXCLUDED_DIRS = {"test", "tests", "integration", "e2e", "fixtures", "benchmark", "benchmarks", "ci", ".github", "scripts"}
        for name in cls.COMPOSE_FILENAMES:
            candidate = directory / name
            if candidate.exists() and candidate.is_file():
                return candidate
        for name in cls.COMPOSE_FILENAMES:
            for cand in directory.glob(f"*/{name}"):
                if cand.parent.name.lower() not in EXCLUDED_DIRS and cand.is_file():
                    return cand
        return None

    @classmethod
    def is_compose_available(cls, executor: ProcessExecutor) -> bool:
        """Check if `docker compose` plugin is functional."""
        res = executor.execute(["docker", "compose", "version"], timeout_s=3)
        return res.exit_code == 0

    @classmethod
    def up(
        cls,
        cwd: Path,
        executor: ProcessExecutor,
        project_path: str,
        registry: InfrastructureRegistry | None = None,
    ) -> ProcessExecutionResult:
        """Execute `docker compose up -d` targeting backing services, and track created resources."""
        import yaml

        backing_services: list[str] = []
        compose_file = cls.find_compose_file(cwd)
        actual_cwd = compose_file.parent if compose_file else cwd

        if compose_file:
            try:
                with open(compose_file, "r", encoding="utf-8") as f:
                    cdata = yaml.safe_load(f)
                if isinstance(cdata, dict) and isinstance(cdata.get("services"), dict):
                    all_services = cdata["services"]
                    has_build = any("build" in sdef for sdef in all_services.values() if isinstance(sdef, dict))
                    if has_build:
                        for sname, sdef in all_services.items():
                            if isinstance(sdef, dict) and "build" not in sdef:
                                backing_services.append(sname)
            except Exception:
                pass

        up_cmd = ["docker", "compose", "up", "-d"]
        if backing_services:
            up_cmd.extend(backing_services)

        res = executor.execute(up_cmd, cwd=actual_cwd, timeout_s=180)
        if res.exit_code == 0 and registry is not None:
            # Inspect containers created by compose and register them
            ps_res = executor.execute(["docker", "compose", "ps", "--format", "json"], cwd=actual_cwd, timeout_s=5)
            if ps_res.exit_code == 0 and ps_res.stdout.strip():
                try:
                    for line in ps_res.stdout.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        item = json.loads(line)
                        container_id = item.get("ID") or item.get("Name")
                        name = item.get("Name") or item.get("Service") or "compose-service"
                        if container_id:
                            registry.register_resource(
                                OwnedResource(
                                    resource_type=ResourceType.CONTAINER,
                                    id=container_id,
                                    name=name,
                                    service_type=ServiceType.DOCKER_COMPOSE,
                                    project_path=project_path,
                                    labels={"runrepo.managed": "true", "runrepo.compose": "true"},
                                )
                            )
                except Exception:
                    pass
        return res

    @classmethod
    def down(
        cls,
        cwd: Path,
        executor: ProcessExecutor,
        remove_volumes: bool = False,
    ) -> ProcessExecutionResult:
        """Execute `docker compose down` (optionally removing volumes)."""
        cmd = ["docker", "compose", "down"]
        if remove_volumes:
            cmd.append("-v")
        return executor.execute(cmd, cwd=cwd, timeout_s=30)

    @classmethod
    def ps(cls, cwd: Path, executor: ProcessExecutor) -> list[dict[str, Any]]:
        """List current compose services in JSON format."""
        res = executor.execute(["docker", "compose", "ps", "--format", "json"], cwd=cwd, timeout_s=5)
        if res.exit_code != 0 or not res.stdout.strip():
            return []

        services = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                services.append(item)
            except Exception:
                pass
        return services
