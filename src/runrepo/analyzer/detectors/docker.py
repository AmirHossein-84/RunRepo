"""Deterministic Docker and Docker Compose configuration detector."""

from typing import Any

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.models import (
    Confidence,
    DetectionEvidence,
    DockerComposeService,
    DockerInfo,
)

COMPOSE_FILENAMES = (
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
    "compose.override.yaml",
    "compose.override.yml",
    "docker-compose.override.yaml",
    "docker-compose.override.yml",
)


class DockerDetector(BaseDetector):
    """Detects Dockerfile presence and parses Docker Compose services and configurations."""

    @property
    def name(self) -> str:
        return "docker"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()

        discovered_dockerfiles: list[str] = []
        for file_path in context.get_all_files():
            file_name = file_path.split("/")[-1]
            if file_name == "Dockerfile" or file_name.startswith("Dockerfile."):
                discovered_dockerfiles.append(file_path)

        EXCLUDED_COMPOSE_DIRS = ("test/", "tests/", "integration/", "e2e/", "fixtures/", "benchmark/", "benchmarks/", "ci/", ".github/")
        discovered_compose_files: list[str] = []
        for compose_name in COMPOSE_FILENAMES:
            for file_path in context.get_all_files():
                if any(file_path.startswith(ex) or f"/{ex}" in file_path for ex in EXCLUDED_COMPOSE_DIRS):
                    continue
                if file_path == compose_name or file_path.endswith(f"/{compose_name}"):
                    if file_path not in discovered_compose_files:
                        discovered_compose_files.append(file_path)

        if not discovered_dockerfiles and not discovered_compose_files:
            return result

        docker_evidence: list[DetectionEvidence] = []
        compose_services: list[DockerComposeService] = []

        if discovered_dockerfiles:
            for df in discovered_dockerfiles:
                docker_evidence.append(
                    DetectionEvidence(
                        source="Dockerfile",
                        detail=f"Containerfile definition at {df}",
                        confidence=Confidence.HIGH,
                        path=df,
                    )
                )

        for cf in discovered_compose_files:
            docker_evidence.append(
                DetectionEvidence(
                    source=cf,
                    detail=f"Docker Compose configuration at {cf}",
                    confidence=Confidence.HIGH,
                    path=cf,
                )
            )

            compose_data = context.read_yaml(cf)
            if not isinstance(compose_data, dict):
                continue

            raw_services = compose_data.get("services")
            if isinstance(raw_services, dict):
                for s_name, s_def in raw_services.items():
                    if not isinstance(s_def, dict):
                        continue

                    # Extract ports
                    raw_ports = s_def.get("ports", [])
                    ports: list[str] = []
                    if isinstance(raw_ports, list):
                        for p in raw_ports:
                            if isinstance(p, (str, int)):
                                ports.append(str(p))
                            elif isinstance(p, dict) and "target" in p:
                                ports.append(f"{p.get('published', '')}:{p['target']}")

                    # Extract env keys
                    raw_env = s_def.get("environment")
                    env_keys: list[str] = []
                    if isinstance(raw_env, list):
                        for item in raw_env:
                            if isinstance(item, str) and "=" in item:
                                env_keys.append(item.split("=")[0].strip())
                            elif isinstance(item, str):
                                env_keys.append(item.strip())
                    elif isinstance(raw_env, dict):
                        env_keys.extend(str(k) for k in raw_env.keys())

                    # Extract depends_on
                    raw_dep = s_def.get("depends_on")
                    deps: list[str] = []
                    if isinstance(raw_dep, list):
                        deps.extend(str(d) for d in raw_dep)
                    elif isinstance(raw_dep, dict):
                        deps.extend(str(d) for d in raw_dep.keys())

                    # Build context
                    build_ctx: str | None = None
                    raw_build = s_def.get("build")
                    if isinstance(raw_build, str):
                        build_ctx = raw_build
                    elif isinstance(raw_build, dict) and "context" in raw_build:
                        build_ctx = str(raw_build["context"])

                    img_val = str(s_def["image"]) if "image" in s_def else None

                    compose_services.append(
                        DockerComposeService(
                            name=str(s_name),
                            image=img_val,
                            build_context=build_ctx,
                            ports=ports,
                            environment_keys=env_keys,
                            depends_on=deps,
                        )
                    )

        result.docker = DockerInfo(
            has_dockerfile=bool(discovered_dockerfiles),
            dockerfiles=discovered_dockerfiles,
            compose_files=discovered_compose_files,
            compose_services=compose_services,
            evidence=docker_evidence,
        )

        return result
