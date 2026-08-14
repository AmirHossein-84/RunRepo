"""Unit tests for DockerDetector."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detectors.docker import DockerDetector


def test_docker_detector_compose_and_dockerfile(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "Dockerfile": "FROM node:20-alpine\nWORKDIR /app\n",
            "compose.yaml": """
services:
  web:
    build: .
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgres://user:pass@db:5432/app
    depends_on:
      - db
      - redis
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: secretpassword
      POSTGRES_DB: app
    ports:
      - "5432:5432"
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
""",
        }
    )

    detector = DockerDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    assert result.docker is not None
    assert result.docker.has_dockerfile is True
    assert "Dockerfile" in result.docker.dockerfiles
    assert "compose.yaml" in result.docker.compose_files

    services_map = {s.name: s for s in result.docker.compose_services}
    assert "web" in services_map
    assert "db" in services_map
    assert "redis" in services_map

    assert services_map["web"].ports == ["3000:3000"]
    assert "DATABASE_URL" in services_map["web"].environment_keys
    assert services_map["web"].depends_on == ["db", "redis"]
    assert services_map["db"].image == "postgres:16-alpine"
    assert services_map["redis"].image == "redis:7-alpine"
