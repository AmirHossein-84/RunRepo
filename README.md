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
Executor (Milestone 4: Controlled Execution & Process Tracking)
    ↓
ExecutionResult
    ↓
[Future: Verification → Diagnostics]
```

### Core Architectural Invariants

1. **Strict Responsibility Separation**:
   - **Repository Analyzer** answers: *"What does this repository require?"* (Read-only on repository filesystem).
   - **Environment Checker** answers: *"What does this host machine currently provide?"* (Read-only on local system).
   - **Execution Planner** answers: *"Given repository facts and host facts, what ordered actions are necessary?"* (Read-only decision graph).
   - **Execution Engine** answers: *"How do we safely execute approved actions?"* (Controlled execution, process management, confirmation gates).
2. **Deterministic First**: Programmatic detection via manifest files, lockfiles, and standard tool probes before any AI heuristics.
3. **Safety & Confirmation Gates**: Commands marked `REQUIRES_CONFIRMATION` prompt the user unless `--yes` is supplied; `DANGEROUS` commands require explicit confirmation; `BLOCKED` commands never run.
4. **Zero-Side-Effects Dry Run**: `--dry-run` simulates the entire pipeline without running processes or writing files.
5. **Cross-Platform Resilience**: Designed specifically for Windows 11 as the primary target and Linux as secondary. Safe subprocess execution without `shell=True` and normalized process group management.
6. **Isolated Process Lifecycle**: Background applications are managed via `ProcessManager` with logs written to user data storage (`platformdirs.user_data_dir("runrepo")`).

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
* **Plan Status Model**: `READY`, `NEEDS_CONFIRMATION`, `NEEDS_INPUT`, `BLOCKED`.
* **Action Types**: `VERIFY_RUNTIME`, `VERIFY_PACKAGE_MANAGER`, `CONFIGURE_ENV`, `START_SERVICE`, `INSTALL_DEPENDENCIES`, `GENERATE_CLIENT`, `RUN_DATABASE_MIGRATION`, `START_APPLICATION`, `VERIFY_APPLICATION`.
* **Verification & Rollback Metadata**: Every step defines structured criteria for validating execution and rolling back changes.

### Milestone 4: Execution Engine (`runrepo setup`)

Controlled, safe execution engine and background process manager:

* **Fail-Fast DAG Execution**: Steps execute in topological order; failures halt execution immediately and downstream steps are marked `SKIPPED`.
* **Confirmation Handlers**: Interactive terminal prompts (`ConsoleConfirmationHandler`), automated CI/CD mode (`AutoConfirmationHandler` for `--yes`), and strict non-interactive checks (`NonInteractiveConfirmationHandler`).
* **Dedicated Step Handlers**: Modular handlers for environment preparation, dependency installation, Docker Compose services, database migrations, and application startup.
* **Background Process Lifecycle**: Long-running applications run as managed background processes with real-time log capturing and Windows-compatible termination (`taskkill` / process groups).
* **Step Verification**: Automatically evaluates exit codes, file existence, TCP ports, and HTTP endpoints.

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

#### 1. Setup & Run Repository (`runrepo setup`)

```bash
# Run end-to-end repository setup (analyze -> doctor -> plan -> execute)
uv run runrepo setup .

# Simulate execution without running processes or writing files
uv run runrepo setup . --dry-run

# Run with automatic confirmation for all safe and confirmation steps
uv run runrepo setup . --yes

# Output structured ExecutionResult in JSON format
uv run runrepo setup . --dry-run --json
```

#### 2. Execution Plan (`runrepo plan`)

```bash
# Generate and display the ordered execution plan
uv run runrepo plan .

# Output structured ExecutionPlan in JSON format
uv run runrepo plan . --json
```

#### 3. Environment Health Check (`runrepo doctor`)

```bash
# Check host environment against current repository requirements
uv run runrepo doctor .

# Run general host environment health check (all tools)
uv run runrepo doctor
```

#### 4. Repository Analysis (`runrepo analyze`)

```bash
# Analyze repository facts
uv run runrepo analyze .

# Show granular detection evidence breakdown
uv run runrepo analyze . --evidence
```

#### 5. Background Process Management (`runrepo status`, `stop`, `logs`)

```bash
# List all active background applications
uv run runrepo status

# View recent output logs of a running process
uv run runrepo logs

# Stop running background processes
uv run runrepo stop
```

---

## Testing

The project includes an extensive, 100% deterministic test suite using mocked command execution and realistic fixtures:

```bash
# Run all tests (107 tests)
uv run pytest -v

# Run tests with coverage report
uv run pytest --cov=runrepo --cov-report=term-missing
```
