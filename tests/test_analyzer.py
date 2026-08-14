"""End-to-end integration tests for RepositoryAnalyzer across realistic project fixtures."""

from runrepo.analyzer import RepositoryAnalyzer
from runrepo.models import (
    DatabaseType,
    EnvVarCategory,
    FrameworkCategory,
    ProjectType,
)


def test_fixture_1_node_npm(create_fixture_repo):
    repo = create_fixture_repo(
        {
            ".nvmrc": "20.10.0\n",
            "package.json": '{"name": "express-api", "scripts": {"start": "node index.js"}, "dependencies": {"express": "^4.19.2"}}',
            "package-lock.json": '{"name": "express-api", "lockfileVersion": 3}',
            "index.js": "const express = require('express');",
        }
    )

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    assert info.name == "express-api"
    assert info.project_type == ProjectType.API_SERVICE
    assert "JavaScript" in info.languages
    assert len(info.runtimes) == 1
    assert info.runtimes[0].name == "node"
    assert info.runtimes[0].version == "20.10.0"
    assert len(info.package_managers) == 1
    assert info.package_managers[0].name == "npm"
    assert len(info.frameworks) == 1
    assert info.frameworks[0].name == "Express"
    assert len(info.warnings) == 0


def test_fixture_2_node_pnpm_nextjs(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "package.json": '{"name": "nextjs-web", "packageManager": "pnpm@9.5.0", "scripts": {"dev": "next dev", "build": "next build"}, "dependencies": {"next": "14.2.3", "react": "18.3.1"}}',
            "pnpm-lock.yaml": "lockfileVersion: '9.0'\n",
            "tsconfig.json": "{}",
            "app/page.tsx": "export default function Page() {}",
        }
    )

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    assert info.name == "nextjs-web"
    assert info.project_type == ProjectType.WEB_APPLICATION
    assert "TypeScript" in info.languages
    assert any(pm.name == "pnpm" for pm in info.package_managers)
    assert any(f.name == "Next.js" for f in info.frameworks)


def test_fixture_3_node_yarn(create_fixture_repo):
    repo = create_fixture_repo(
        {
            ".node-version": "18.19.0\n",
            "package.json": '{"name": "yarn-app", "scripts": {"dev": "vite"}, "dependencies": {"vite": "^5.2.0"}}',
            "yarn.lock": "# yarn lockfile v1\n",
            "vite.config.js": "export default {}",
        }
    )

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    assert info.name == "yarn-app"
    assert any(pm.name == "yarn" for pm in info.package_managers)
    assert any(f.name == "Vite" for f in info.frameworks)
    assert info.runtimes[0].version == "18.19.0"


def test_fixture_4_python_requirements(create_fixture_repo):
    repo = create_fixture_repo(
        {
            ".python-version": "3.11.8\n",
            "requirements.txt": "Flask==3.0.3\ngunicorn>=22.0.0\n",
            "app.py": "from flask import Flask\napp = Flask(__name__)\n",
        }
    )

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    assert "Python" in info.languages
    assert info.runtimes[0].name == "python"
    assert info.runtimes[0].version == "3.11.8"
    assert any(pm.name == "pip" for pm in info.package_managers)
    assert any(f.name == "Flask" for f in info.frameworks)
    assert "app.py" in info.entrypoints


def test_fixture_5_python_pyproject_fastapi(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "pyproject.toml": """
[project]
name = "fastapi-service"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn>=0.30.0",
]
""",
            "main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
        }
    )

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    assert info.name == "fastapi-service"
    assert info.runtimes[0].version == ">=3.12"
    assert any(f.name == "FastAPI" for f in info.frameworks)
    assert "main.py" in info.entrypoints


def test_fixture_6_python_uv(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "pyproject.toml": """
[project]
name = "uv-service"
version = "0.1.0"
dependencies = ["httpx>=0.27.0"]
""",
            "uv.lock": "version = 1\n",
        }
    )

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    assert info.name == "uv-service"
    assert any(pm.name == "uv" for pm in info.package_managers)


def test_fixture_7_node_docker_compose(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "package.json": '{"name": "docker-node-app", "dependencies": {"next": "14.0.0"}}',
            "Dockerfile": "FROM node:20-alpine\n",
            "compose.yaml": """
services:
  web:
    build: .
    ports:
      - "3000:3000"
  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
""",
        }
    )

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    assert info.docker.has_dockerfile is True
    assert len(info.docker.compose_services) == 3
    db_types = {d.name for d in info.databases}
    assert DatabaseType.POSTGRESQL in db_types
    assert DatabaseType.REDIS in db_types
    assert any(s.name == "redis" for s in info.services)


def test_fixture_8_node_prisma_postgres(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "package.json": '{"name": "prisma-app", "dependencies": {"@prisma/client": "^5.14.0"}}',
            "prisma/schema.prisma": """
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
""",
            ".env.example": "DATABASE_URL=postgresql://user:pass@localhost:5432/db\n",
        }
    )

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    assert len(info.databases) == 1
    assert info.databases[0].name == DatabaseType.POSTGRESQL
    assert info.databases[0].orm == "prisma"
    assert info.databases[0].connection_var == "DATABASE_URL"
    assert any(e.name == "DATABASE_URL" and e.category == EnvVarCategory.DATABASE for e in info.environment_variables)


def test_fixture_9_polyglot_node_frontend_python_backend(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "frontend/package.json": '{"name": "frontend-app", "dependencies": {"next": "14.2.0"}}',
            "frontend/pnpm-lock.yaml": "lockfileVersion: '9.0'\n",
            "backend/pyproject.toml": """
[project]
name = "backend-service"
requires-python = ">=3.11"
dependencies = ["fastapi>=0.110.0"]
""",
            "backend/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "backend/requirements.txt": "fastapi>=0.110.0\n",
        }
    )

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    assert "JavaScript" in info.languages
    assert "Python" in info.languages
    assert info.is_monorepo is True

    # Verify subproject path isolation (Constraint 5)
    sub_paths = {sp.path: sp for sp in info.subprojects}
    assert "frontend" in sub_paths
    assert "backend" in sub_paths

    fe_sp = sub_paths["frontend"]
    assert any(f.name == "Next.js" for f in fe_sp.frameworks)

    be_sp = sub_paths["backend"]
    assert any(f.name == "FastAPI" for f in be_sp.frameworks)
    assert any(r.name == "python" for r in be_sp.runtimes)


def test_fixture_10_empty_repo(create_fixture_repo):
    repo = create_fixture_repo({})

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    assert info.name == repo.name
    assert info.project_type == ProjectType.UNKNOWN
    assert len(info.languages) == 0
    assert len(info.runtimes) == 0
    assert len(info.package_managers) == 0
    assert len(info.warnings) == 0


def test_fixture_11_malformed_config_graceful_recovery(create_fixture_repo):
    # Constraint 7: Analyzer should fail gracefully and report warnings rather than crashing
    repo = create_fixture_repo(
        {
            "package.json": "{ invalid json content here ...",
            "pyproject.toml": "broken toml [[[]]",
            "compose.yaml": ": invalid yaml content @#$%",
            ".nvmrc": "20.12.0\n",
        }
    )

    analyzer = RepositoryAnalyzer()
    info = analyzer.analyze(repo)

    # Should not crash, and should capture warnings
    assert len(info.warnings) >= 1
    warn_files = {w.file_path for w in info.warnings}
    assert "package.json" in warn_files or "pyproject.toml" in warn_files or "compose.yaml" in warn_files

    # Still successfully detects nvmrc Node runtime
    assert any(r.name == "node" and r.version == "20.12.0" for r in info.runtimes)
