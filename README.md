# RunRepo

> **"I give RunRepo a repository. RunRepo figures out what it needs and makes it runnable."**

RunRepo is a developer CLI tool that takes an arbitrary Git repository and makes it runnable locally with minimal manual setup.

RunRepo is **not an AI coding assistant**. Deterministic repository analysis, environment detection, planning, execution, and verification form the core product. AI is only used later for ambiguity resolution and failure diagnostics.

---

## Architecture

RunRepo separates analysis, planning, and execution into clean, independent stages:

```text
Repository
    ↓
Analyzer (Milestone 1: Repository Facts)
    ↓
ProjectInfo / ProjectGraph
    +
Local Machine
    ↓
Environment Checker (Milestone 2: Host Facts)
    ↓
EnvironmentState
    ↓
Planner (Milestone 3: Decision & Execution Graph)
    ↓
ExecutionPlan
    ↓
[Future: Executor → Verification → Diagnostics]
```

### Core Architectural Invariants

1. **Strict Responsibility Separation**:
   - **Repository Analyzer** answers: *"What does this repository require?"* (Read-only on repository filesystem).
   - **Environment Checker** answers: *"What does this host machine currently provide?"* (Read-only on local system).
   - **Execution Planner** answers: *"Given repository facts and host facts, what ordered actions are necessary?"* (Read-only decision graph).
2. **Deterministic First**: Programmatic detection via manifest files, lockfiles, and standard tool probes before any AI heuristics.
3. **Explainable Facts**: Every detected fact preserves its exact `DetectionEvidence` (source file, matched line/detail, confidence score, relative path).
4. **Strict Read-Only Guarantee**: Analyzer, Environment Checker, and Planner **never** execute arbitrary scripts, install software, start services, or modify configuration.
5. **Cross-Platform Resilience**: Designed specifically for Windows 11 as the primary target and Linux as secondary. Safe subprocess execution without `shell=True` and normalized path handling.
6. **Per-Run Command Caching**: Inspection commands are cached per execution to prevent redundant process invocations.

---

## Features

### Milestone 1: Repository Analyzer (`runrepo analyze`)

Deterministic repository detectors discovering facts from codebase assets:

* **Node.js**: Versions (`.nvmrc`, `.node-version`, `package.json` `engines.node`), package managers (`pnpm`, `npm`, `yarn`, `bun`), frameworks (Next.js, Remix, Nuxt, Astro, SvelteKit, Vite, React, Vue, Express, NestJS, Fastify, Hono), scripts, dependencies, workspaces (`pnpm-workspace.yaml`, `turbo.json`, `lerna.json`, `nx.json`).
* **Python**: Versions (`.python-version`, `pyproject.toml` `requires-python`, `runtime.txt`, `Pipfile`), package managers (`uv`, `poetry`, `pipenv`, `pip`), frameworks (FastAPI, Django, Flask, Starlette, Litestar, Streamlit, Celery), entrypoints (`[project.scripts]`, `main.py`, `app.py`, `manage.py`, `cli.py`).
* **Docker & Compose**: Dockerfiles and Docker Compose files (`compose.yaml`, `docker-compose.yml`), service definitions, ports, and environment variable keys.
* **Databases & Services**: Prisma (`schema.prisma`), Alembic (`alembic.ini`), Drizzle (`drizzle.config`), PostgreSQL, Redis, MySQL, SQLite, MongoDB, RabbitMQ.
* **Environment Variables**: `.env.example`, `.env.template`, `.env.sample` parsing with categorization (`database`, `secret`, `local_default`, `external_service`).

### Milestone 2: Environment Checker (`runrepo doctor`)

Safe, read-only host inspection evaluating whether the local environment satisfies project requirements:

* **Git**: CLI presence and version.
* **Node.js**: Discovered version and semantic version requirement evaluation (`>=22`, `^20`, `~18.2`, `18.x`).
* **Python**: Discovered interpreter, version requirement evaluation (`>=3.11`, `<3.14`), and interpreter path resolution.
* **Package Managers**: npm, pnpm, yarn, uv, and pip (bound directly to discovered Python interpreter).
* **Docker & Docker Compose**: Two-tier inspection distinguishing missing CLI (`MISSING`), stopped/unreachable daemon (`BROKEN`), and operational state (`OK`). Supports modern `docker compose` plugin and legacy standalone `docker-compose`.
* **Standardized Status Model**: `OK`, `MISSING`, `WRONG_VERSION`, `BROKEN`, `UNKNOWN`.

### Milestone 3: Execution Planner (`runrepo plan`)

Deterministic, explainable execution planning that builds a directed acyclic graph of ordered actions:

* **Topological DAG Ordering**: Constructs a `PlanGraph` linking prerequisites via `depends_on` with cycle detection.
* **Risk Classification**: Steps are classified as `SAFE`, `REQUIRES_CONFIRMATION`, `BLOCKED`, or `DANGEROUS`.
* **Plan Status Model**:
  - `READY`: All prerequisites satisfied and safe to run.
  - `NEEDS_CONFIRMATION`: Steps require user approval (e.g. package installation, service startup).
  - `NEEDS_INPUT`: Requires missing credentials/secrets (`OPENAI_API_KEY`) or startup command disambiguation.
  - `BLOCKED`: Required runtime or dependency is missing/incompatible with no safe automated strategy.
* **Action Types**: `VERIFY_RUNTIME`, `VERIFY_PACKAGE_MANAGER`, `CONFIGURE_ENV`, `START_SERVICE`, `INSTALL_DEPENDENCIES`, `GENERATE_CLIENT`, `RUN_DATABASE_MIGRATION`, `START_APPLICATION`, `VERIFY_APPLICATION`.
* **Verification & Rollback Metadata**: Every step defines structured criteria for validating execution and rolling back changes.
* **Polyglot & Subproject Scoping**: Separate scopes for frontend and backend subprojects with accurate working directories (`cwd`).

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

# Sync virtual environment and dev dependencies with uv
uv sync --extra dev
```

### CLI Commands

#### Repository Analysis (`runrepo analyze`)

```bash
# Analyze a repository directory
uv run runrepo analyze .

# Analyze an external project path
uv run runrepo analyze /path/to/project

# Output structured domain model in JSON format
uv run runrepo analyze . --json

# Show granular detection evidence breakdown
uv run runrepo analyze . --evidence
```

#### Environment Check (`runrepo doctor`)

```bash
# Check host environment against current repository requirements
uv run runrepo doctor .

# Run general host environment health check (all tools)
uv run runrepo doctor

# Output structured EnvironmentState in JSON format
uv run runrepo doctor . --json
```

#### Execution Plan (`runrepo plan`)

```bash
# Generate and display the ordered execution plan
uv run runrepo plan .

# Output structured ExecutionPlan in JSON format
uv run runrepo plan . --json

# Plan with explicit dry-run flag
uv run runrepo plan . --dry-run
```

---

## Domain Model Overview

### `ProjectInfo` (Repository Facts)

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

### `EnvironmentState` (Host Facts & Evaluation)

| Field | Type | Description |
|---|---|---|
| `platform` | `str` | Host OS description (e.g. `"Windows 11"`) |
| `architecture` | `str` | CPU architecture (e.g. `"x86_64"`) |
| `is_satisfied` | `bool` | True if all required capabilities are satisfied (`OK`) |
| `missing_checks` | `list[str]` | Required tools that are completely missing |
| `wrong_version_checks` | `list[str]` | Required tools with incompatible versions |
| `broken_checks` | `list[str]` | Required tools installed but non-operational |
| `unknown_checks` | `list[str]` | Capabilities whose status could not be evaluated |
| `checks` | `list[EnvironmentCheck]` | Granular per-tool inspection and diagnostic status |

### `ExecutionPlan` (Decision & Execution Graph)

| Field | Type | Description |
|---|---|---|
| `repository_path` | `str` | Target repository path |
| `status` | `PlanStatus` | `READY`, `NEEDS_CONFIRMATION`, `NEEDS_INPUT`, `BLOCKED` |
| `steps` | `list[PlanStep]` | Topologically ordered execution steps |
| `warnings` | `list[str]` | Warnings and notes for the user |
| `blocking_reasons` | `list[str]` | Explanations for why execution is blocked |
| `input_reasons` | `list[str]` | Required user credentials or command choices |

---

## Testing

The project includes an extensive, 100% deterministic test suite using mocked command execution and realistic fixtures:

```bash
# Run all tests (78 tests)
uv run pytest -v

# Run tests with coverage report
uv run pytest --cov=runrepo --cov-report=term-missing
```
