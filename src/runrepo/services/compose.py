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
        EXCLUDED_DIRS = {
            "test", "tests", "integration", "e2e", "fixtures", "benchmark", "benchmarks",
            "ci", ".github", "scripts", "docker", "examples", "example", "samples", "sample",
            "docs", "documentation", "playground", "templates",
        }
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

        OFFICIAL_INFRA_PREFIXES = (
            "postgres", "mysql", "mariadb", "redis", "valkey",
            "mongo", "rabbitmq", "memcached", "mailhog", "maildev",
            "minio", "localstack", "clickhouse", "elasticsearch",
            "opensearch", "meilisearch", "traefik", "nginx", "adminer",
        )

        backing_services: list[str] = []
        all_infra_services: list[str] = []
        compose_file = cls.find_compose_file(cwd)
        actual_cwd = cwd
        if compose_file is not None:
            actual_cwd = compose_file.parent

            # Inspect compose file to filter out unbuilt dev images (e.g. appwrite-dev)
            try:
                content = yaml.safe_load(compose_file.read_text(encoding="utf-8", errors="replace"))
                if isinstance(content, dict) and "services" in content and isinstance(content["services"], dict):
                    all_services = content["services"]
                    has_dev_images = False
                    has_build = False
                    for sname, sdef in all_services.items():
                        if isinstance(sdef, dict):
                            img = str(sdef.get("image", "")).lower()
                            if "build" in sdef:
                                has_build = True
                            if img.endswith("-dev") or img.endswith(":dev") or "/dev" in img or not img:
                                has_dev_images = True
                            elif any(img.startswith(p) or f"/{p}" in img for p in OFFICIAL_INFRA_PREFIXES):
                                all_infra_services.append(sname)

                    if has_dev_images or has_build:
                        if all_infra_services:
                            # Prioritize primary DB (mariadb or postgres) + cache (redis)
                            primary_infra = []
                            for s in all_infra_services:
                                s_low = s.lower()
                                if any(db in s_low for db in ("mariadb", "postgres", "redis")):
                                    primary_infra.append(s)
                            backing_services = primary_infra if primary_infra else all_infra_services[:3]
                        else:
                            for sname, sdef in all_services.items():
                                if isinstance(sdef, dict) and "build" not in sdef and not str(sdef.get("image", "")).lower().endswith("-dev"):
                                    backing_services.append(sname)
            except Exception:
                pass

        up_cmd = ["docker", "compose", "up", "-d"]
        if backing_services:
            up_cmd.append("--no-deps")
            up_cmd.extend(backing_services)

        res = executor.execute(up_cmd, cwd=actual_cwd, timeout_s=300)

        # If pulling all services failed due to private/custom unbuilt dev images, retry with pure infra services
        if res.exit_code != 0 and all_infra_services and any(err in (res.stderr or "") for err in ("pull access denied", "does not exist", "manifest unknown", "docker login")):
            fallback_cmd = ["docker", "compose", "up", "-d", "--no-deps"] + all_infra_services
            res = executor.execute(fallback_cmd, cwd=actual_cwd, timeout_s=300)

        # If port is already allocated on host, backing service is already active and listening
        if res.exit_code != 0 and any(err in (res.stderr or "") for err in ("port is already allocated", "already in use")):
            from runrepo.executor.process import ProcessExecutionResult
            res = ProcessExecutionResult(
                exit_code=0,
                stdout=f"[runrepo] Required port already allocated on host; reusing active service.\n{res.stdout}",
                stderr="",
                duration_ms=res.duration_ms,
            )

        # If Windows container daemon cannot pull/run Linux container images or daemon is unavailable, warn and continue
        err_lower = (res.stderr or "").lower()
        if res.exit_code != 0 and any(err in err_lower for err in ("no matching manifest for windows", "cannot be used on this platform", "image operating system", "daemon in windows mode", "pipe/docker_engine", "error during connect", "is the docker daemon running", "the system cannot find the file specified")):
            from runrepo.executor.process import ProcessExecutionResult
            res = ProcessExecutionResult(
                exit_code=0,
                stdout=f"[runrepo] Host Docker daemon is unavailable or cannot run Linux compose images. Continuing with local environment.\n{res.stdout}",
                stderr="",
                duration_ms=res.duration_ms,
            )

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
