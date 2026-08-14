# RunRepo

> **"I give RunRepo a repository. RunRepo figures out what it needs and makes it runnable."**

RunRepo is a developer CLI tool that takes an arbitrary Git repository and makes it runnable locally with minimal manual setup.

RunRepo is **not an AI coding assistant**. Deterministic repository analysis, environment detection, planning, execution, and verification form the core product. AI is only used later for ambiguity resolution and failure diagnostics.

---

## Architecture

RunRepo separates analysis, planning, and execution into clean, independent stages:

```text
CLI (`runrepo analyze`)
 ↓
Repository Analyzer & ScanContext
 ↓
Deterministic Domain Detectors (Node, Python, Docker, Database, Environment)
 ↓
Structured Project Graph & Evidence Synthesis (`ProjectInfo`)
 ↓
[Future Milestones: Environment Checker → Planner → Executor → Verification → Diagnostics]
```

### Core Architectural Invariants

1. **Deterministic First**: Programmatic detection via manifest files, lockfiles, and configuration before any AI heuristics.
2. **Explainable Facts**: Every detected fact preserves its exact `DetectionEvidence` (source file, matched line/detail, confidence score, relative path).
3. **Strict Read-Only Analysis**: The analyzer never executes setup actions, creates virtual environments, installs dependencies, or alters the repository.
4. **Cross-Platform Resilience**: Designed specifically for Windows 11 as the primary target and Linux as secondary. Normalized path handling and terminal encoding safety.
5. **Polyglot & Monorepo Support**: Captures subprojects (e.g. Node frontend + Python backend) with independent runtimes and framework metadata.

---

## Milestone 1 Features

### Detectors Implemented

* **Node.js**:
  * Runtime versions (`.nvmrc`, `.node-version`, `package.json` `engines.node`)
  * Package managers (`pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `bun.lock`, `package.json` `packageManager`)
  * Frameworks (Next.js, Remix, Nuxt, Astro, SvelteKit, Vite, React, Vue, Svelte, Express, NestJS, Fastify, Hono, Koa)
  * Scripts & dependencies (`package.json` `scripts`, `dependencies`, `devDependencies`)
  * Monorepo workspaces (`pnpm-workspace.yaml`, `turbo.json`, `lerna.json`, `nx.json`, `workspaces`)
* **Python**:
  * Runtime versions (`.python-version`, `pyproject.toml` `requires-python`, `runtime.txt`, `Pipfile`)
  * Package managers (`uv.lock` / `tool.uv`, `poetry.lock` / `tool.poetry`, `Pipfile.lock` / `Pipfile`, `requirements.txt`, `setup.py`)
  * Frameworks (FastAPI, Django, Flask, Starlette, Litestar, Tornado, Sanic, Streamlit, Celery)
  * Dependencies (`requirements.txt`, `pyproject.toml` dependencies and optional-dependencies)
  * Entry points (`main.py`, `app.py`, `manage.py`, `wsgi.py`, `asgi.py`, `cli.py`, `[project.scripts]`)
* **Docker & Compose**:
  * Containerfiles (`Dockerfile`, `Dockerfile.*`, `docker/Dockerfile`)
  * Compose files (`compose.yaml`, `compose.yml`, `docker-compose.yaml`, `docker-compose.yml`)
  * Service definitions, image references, ports, and declared environment variable keys
* **Databases & Services**:
  * ORMs & Migrations (Prisma `schema.prisma`, Alembic `alembic.ini`, Drizzle `drizzle.config`)
  * Services (PostgreSQL, Redis, MySQL, SQLite, MongoDB, RabbitMQ)
* **Environment Variables**:
  * Template parsing (`.env.example`, `.env.template`, `.env.sample`, `.env.local.example`)
  * Categorization (`database`, `secret`, `local_default`, `external_service`, `general`)
  * Required vs optional detection

---

## Installation & Usage

### Prerequisites

- Python `>= 3.11`
- `uv` (recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/AmirHossein-84/RunRepo.git
cd RunRepo

# Sync virtual environment and dependencies with uv
uv sync --extra dev
```

### CLI Commands

```bash
# Analyze a repository directory
uv run runrepo analyze .

# Analyze an external project path
uv run runrepo analyze /path/to/project

# Output structured domain model in JSON format
uv run runrepo analyze . --json

# Show full evidence breakdown and confidence scores
uv run runrepo analyze . --evidence
```

---

## Domain Model Overview

The core domain model is `ProjectInfo`, which contains:

| Field | Type | Description |
|---|---|---|
| `path` | `str` | Absolute path to analyzed repository |
| `name` | `str` | Inferred repository or package name |
| `project_type` | `ProjectType` | `web_application`, `api_service`, `cli_tool`, `polyglot_fullstack`, `library`, `unknown` |
| `is_monorepo` | `bool` | Whether repository contains multiple subprojects or workspace packages |
| `languages` | `list[str]` | Detected programming languages (e.g. `["JavaScript", "TypeScript"]`) |
| `runtimes` | `list[RuntimeInfo]` | Runtimes with version constraints and provenance evidence |
| `package_managers` | `list[PackageManagerInfo]` | Detected package managers with lockfile references |
| `frameworks` | `list[FrameworkInfo]` | Detected web/backend frameworks and categories |
| `scripts` | `list[ProjectScript]` | Runnable tasks and script commands |
| `dependencies` | `list[DependencyInfo]` | Direct and development dependencies |
| `environment_variables` | `list[EnvironmentVariable]` | Detected required and optional environment variables |
| `databases` | `list[DatabaseRequirement]` | Databases inferred from ORMs, Compose, and env vars |
| `services` | `list[ServiceRequirement]` | Auxiliary services (e.g. Redis cache/queue, RabbitMQ) |
| `docker` | `DockerInfo` | Dockerfiles and Docker Compose service configurations |
| `subprojects` | `list[SubprojectInfo]` | Isolated subprojects in monorepo/polyglot setups |
| `entrypoints` | `list[str]` | Discovered executable entrypoints |
| `warnings` | `list[AnalysisWarning]` | Non-fatal parser warnings (e.g. malformed configs) |
| `evidence` | `list[DetectionEvidence]` | Provenance details for detected facts |

---

## Testing

The project includes an extensive test suite covering unit tests, domain models, individual detectors, and end-to-end integration tests across 12 realistic fixtures:

```bash
# Run all tests
uv run pytest -v

# Run tests with coverage report
uv run pytest --cov=runrepo --cov-report=term-missing
```
