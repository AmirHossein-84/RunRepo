<div align="center">

# ⚡ RunRepo

**Deterministic Repository Analyzer & Local Environment Orchestrator**

*“I found an open-source GitHub project. I want to run it. Make the environment work.”*

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Package Manager](https://img.shields.io/badge/managed%20by-uv-purple.svg?style=flat-square)](https://github.com/astral-sh/uv)
[![Test Suite](https://img.shields.io/badge/tests-328%20passed-success.svg?style=flat-square&logo=pytest&logoColor=white)](https://github.com/AmirHossein-84/RunRepo)
[![Real-World Benchmark](https://img.shields.io/badge/benchmark-50%2F50%20(100%25%20Reliable)-brightgreen.svg?style=flat-square)](BENCHMARK_REPORT.md)
[![Platform](https://img.shields.io/badge/platform-Windows%2011%20%7C%20Ubuntu%20Linux%20%7C%20macOS-informational.svg?style=flat-square)](https://github.com/AmirHossein-84/RunRepo)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)

[English](README.md) • [فارسی (Persian)](README-fa.md)

---

</div>

## 📑 Table of Contents

- [Overview & Philosophy](#-overview--philosophy)
- [System Architecture](#-system-architecture)
- [Key Capabilities](#-key-capabilities)
- [🏆 Empirical 50-Repository Benchmark](#-empirical-50-repository-benchmark)
- [Getting Started & Installation](#-getting-started--installation)
- [CLI Command Reference](#-cli-command-reference)
- [Advanced Features & Autonomous Repair](#-advanced-features--autonomous-repair)
- [Reproducibility (`runrepo.yaml` & `runrepo.lock`)](#-reproducibility-runrepoyaml--runrepolock)
- [Safety & Sandboxing Model](#-safety--sandboxing-model)
- [Diagnostics & Port Conflict Resolution](#-diagnostics--port-conflict-resolution)
- [Optional Gemini AI Integration](#-optional-gemini-ai-integration)
- [Testing & Quality Assurance](#-testing--quality-assurance)

---

## 🌟 Overview & Philosophy

Running an unfamiliar open-source repository typically requires cloning the code, deciphering incomplete README instructions, troubleshooting conflicting runtime versions, provisioning database containers, configuring `.env` variables, and diagnosing blocked ports.

**RunRepo transforms this tedious manual process into a single deterministic command:**

```bash
runrepo setup https://github.com/owner/project
```

```text
RunRepo
─────────────────────────────────────────────────────────────────────────────
Repository:    github.com/owner/project
Runtimes:      Node.js 22.14.0 (✓ Satisfied) | Python 3.12 (✓ Satisfied)
Workspaces:    pnpm (apps/web, apps/api, packages/ui)
Services:      PostgreSQL (Docker: 5432), Redis (Docker: 6379)
Plan:          [1] Verify Runtime -> [2] Start DB -> [3] .env -> [4] Install -> [5] Start App

[1/5] Checking Node.js 22 & Python 3.12 .................. ✓ OK
[2/5] Starting managed PostgreSQL container .............. ✓ Ready (localhost:5432)
[3/5] Generating .env from .env.example .................. ✓ Generated (safe defaults)
[4/5] Installing dependencies with pnpm .................. ✓ Completed (4.2s)
[5/5] Launching development server ....................... 🚀 http://localhost:3000
```

### Core Invariants

1. **Deterministic First**: Programmatic detection via lockfiles, manifests, AST inspection, and standard tooling before any heuristics.
2. **Strict Phase Separation**: `Analyzer` (read-only facts) → `Environment Checker` (read-only host facts) → `Planner` (action DAG) → `Executor` (controlled side-effects) → `Verifier` (outcome assertion) → `Diagnostics` (failure explanation).
3. **Safe by Default**: Dangerous operations require interactive confirmation; destructive commands are blocked; dry-run mode (`--dry-run`) performs zero side-effects.
4. **Reproducible**: Persistent lockfiles (`runrepo.lock`) guarantee bit-for-bit repeatability with zero secret leaks.
5. **AI Only for Ambiguity**: Google Gemini is strictly optional for unstructured READMEs or obscure error triage.

---

## 🏛 System Architecture

```text
                     Git Repository / Local Directory
                                    │
                                    ▼
                         ┌────────────────────┐
                         │Repository Analyzer │ (Inspects package manifests,
                         │ (Read-Only Facts)  │  frameworks, docker, databases)
                         └─────────┬──────────┘
                                   │ ProjectInfo
                                   ▼
                         ┌────────────────────┐
     Local Machine ─────►│Environment Checker │ (Inspects installed runtimes,
                         │ (Read-Only Host)   │  tools, Docker daemon, ports)
                         └─────────┬──────────┘
                                   │ EnvironmentState
                                   ▼
                         ┌────────────────────┐
     runrepo.yaml ──────►│ Execution Planner  │ (Constructs topological DAG,
     (User Overrides)    │   (Plan Graph)     │  assigns risk classifications)
                         └─────────┬──────────┘
                                   │ ExecutionPlan
                                   ▼
                         ┌────────────────────┐
     Confirmation ──────►│  Execution Engine  │ (Sandboxed runner, process tracking,
     Gate (--yes)        │ (Controlled Run)   │  atomic resource allocation)
                         └─────────┬──────────┘
                                   │
                                   ▼
                         ┌────────────────────┐
                         │Step & App Verifier │ (Probes TCP/HTTP endpoints,
                         └─────────┬──────────┘  validates exit codes, disk state)
                                   │
                         ┌─────────┴──────────┐
                         │                    │
                     ✓ SUCCESS            ✗ FAILURE
                         │                    │
                         ▼                    ▼
                 ┌───────────────┐   ┌─────────────────┐
                 │ Process Logs  │   │   Diagnostics   │ (PID discovery,
                 │ & Active URLs │   │  Engine & Rules │  port owner inspect)
                 └───────────────┘   └────────┬────────┘
                                              │ (If UNKNOWN)
                                              ▼
                                     ┌─────────────────┐
                                     │Optional Gemini  │
                                     │  AI Assistant   │
                                     └─────────────────┘
```

---

## ✨ Key Capabilities

| Subsystem | Capabilities | Supported Technologies |
| :--- | :--- | :--- |
| **Language & Runtime Detectors** | Version requirements, entrypoints, script discovery, lockfile resolution | **Node.js, Python, Bun, Deno, Go, Rust (Cargo)** |
| **Package Managers** | Dependency graphs, monorepo workspaces, package scripts | **npm, pnpm, yarn (Classic & Berry), bun, uv, poetry, pipenv, pip, conda, cargo** |
| **Monorepo & Workspaces** | Workspace layout detection, subproject DAG resolution, targeted execution | **pnpm workspaces, Turborepo, Nx, Lerna, Yarn Berry, UV workspaces** |
| **Infrastructure Services** | Automated Docker container provisioning, healthchecks, atomic rollbacks | **PostgreSQL, Redis, MySQL, MariaDB, MongoDB, RabbitMQ, MinIO (S3)** |
| **Environment Configuration** | Structured `.env` generation, secret categorization, placeholder warnings | **`.env.example`, `.env.template`, `.env.sample`, docker-compose envs** |
| **Zero-Install Tool Shims** | On-demand tool execution without host pollution | **`uvx poetry`, `uvx pipenv`, `npx -y pnpm`, `npx -y yarn`** |
| **Sandboxed Execution** | Working directory boundaries, sanitized pass-through environment allowlists | **`SandboxedProcessExecutor`, `SandboxPolicy`, strict timeouts** |
| **Diagnostics & Observability** | Network socket probing, process ownership identification, PID triage | **Windows `netstat -ano`, Posix `lsof`, port conflict matching** |
| **Reproducibility** | Declarative manifest overrides and deterministic sorted lockfiles | **`runrepo.yaml` (v1) and `runrepo.lock` (v1, zero secrets)** |
| **AI Ambiguity Resolution** | Structured JSON schema validation, destructive command filtering | **Google Gemini 2.5 Flash / Pro (zero external SDKs, pure REST)** |

---

## 🏆 Empirical 50-Repository Benchmark

To validate RunRepo under real-world conditions, we established a rigorous benchmark corpus of **50 high-profile open-source repositories** and executed complete end-to-end setups with **Zero AI (`RUNREPO_NO_AI=1`)** across both **Ubuntu Linux** and **Microsoft Windows 11**.

### 📊 Benchmark Summary Statistics

| Metric | Count | Percentage |
|:---|:---:|:---:|
| **Total Real-World Repositories Evaluated** | **50 / 50** | **100.0%** |
| 🟢 **Full Autonomous Success (`FULL_SUCCESS`)** | **24** | **48.0%** |
| 🟡 **Partial Success / Bounded (`PARTIAL_SUCCESS`)** | **14** | **28.0%** |
| 🔵 **Cleanly Blocked / Unsupported Compiler (`CORRECTLY_UNSUPPORTED`)** | **12** | **24.0%** |
| 🔴 **Engine Failures / Unhandled Defects (`INCORRECT_FAILURE`)** | **0** | **0.0%** |
| **Deterministic Engine Reliability** | **38 / 38 runnable** | **100.0%** |

### 📦 Batch Highlights

- **Batch 1 (Core Node.js & Web)**: Express, Fastify, NestJS, Chalk, Commander.js, Axios, Next.js, Remix (*100% engine reliability*).
- **Batch 2 (Modern Web & Python)**: Svelte, Vue, Vite, Astro, Nuxt, FastAPI, Flask, Django, Requests, Pydantic (*100% engine reliability*).
- **Batch 3 (Data, ORM & Distributed Queues)**: SQLAlchemy, HTTPX, Typer, FastAPI Template, Cookiecutter Django, Locust, Celery, Prefect, Poetry, Supabase (*100% engine reliability*).
- **Batch 4 (Cloud Infrastructure & Headless CMS)**: Appwrite, Directus, Strapi, Ghost, Hasura, Saleor, Medusa, Cal.com, Chatwoot, Discourse (*100% engine reliability*).
- **Batch 5 (Build Systems, Compilers & ML Ecosystem)**: Focalboard, Turborepo, Nx, pnpm, Babel, Transformers, scikit-learn, pandas, PyTorch, Flask Microblog (*100% engine reliability*).

> [!TIP]
> For the complete per-repository logs, duration timings, classification details, and root-cause diagnoses, read the full **[📊 Benchmark Report](BENCHMARK_REPORT.md)** and **[🛠️ Benchmark Accomplishments](BENCHMARK_ACCOMPLISHMENTS.md)**.

---

## 🚀 Getting Started & Installation

### Prerequisites

- **Python**: `>= 3.11`
- **uv**: *(Recommended)* Ultra-fast Python package and project manager
- **Docker**: *(Optional)* Required for automatically starting backing database/cache services

### Installation via `uv` (Recommended)

```bash
# Clone the repository
git clone https://github.com/AmirHossein-84/RunRepo.git
cd RunRepo

# Install dependencies and sync virtual environment
uv sync

# Run RunRepo CLI
uv run runrepo --help
```

### Installation via `pip`

```bash
pip install -e .
runrepo --help
```

---

## 💻 CLI Command Reference

### 1. `runrepo setup` — Analyze, Provision, and Launch

```bash
# Setup from a remote GitHub repository
runrepo setup https://github.com/fastify/fastify

# Setup from a local directory non-interactively
runrepo setup ./my-project --yes

# Perform a dry-run (zero side-effects)
runrepo setup ./my-project --dry-run

# Output structured JSON execution results
runrepo setup ./my-project --yes --json
```

### 2. `runrepo plan` — Inspect Execution Graph

```bash
# Inspect the planned topological step graph and risk classifications
runrepo plan ./my-project
```

### 3. `runrepo doctor` — Validate Host Environment & Repositories

```bash
# Validate host runtimes, package managers, Docker, and ports
runrepo doctor

# Validate host compatibility for a specific project
runrepo doctor ./my-project
```

### 4. `runrepo pr` — Isolated Pull Request Reproduction

Reproduces bug reports and pull requests in an isolated cache directory without polluting your main checkout:

```bash
# Check out and verify PR #123
runrepo pr https://github.com/owner/repo/pull/123

# Run PR reproduction in ephemeral mode
runrepo pr https://github.com/owner/repo/pull/123 --ephemeral
```

### 5. `runrepo repair` — Autonomous Self-Healing

Detects and automatically heals broken local environments:

```bash
# Auto-kill colliding port processes, recreate corrupted venvs, launch Docker, and repair .env
runrepo repair ./my-project
```

### 6. `runrepo share` — Generate Standalone Onboarding Scripts

Exports reproducible, defensive bash (`setup.sh`) and strict PowerShell (`setup.ps1`) scripts for teammates:

```bash
runrepo share ./my-project --output ./scripts
```

### 7. `runrepo export` — Export Docker Compose Infrastructure

Generates standalone, production-grade `docker-compose.yml` for detected backing services:

```bash
runrepo export ./my-project --output ./docker-compose.runrepo.yml
```

### 8. `runrepo status` & `runrepo stop` — Process Management

```bash
# List all active background servers managed by RunRepo
runrepo status

# Stop background application servers and clean up allocated ports
runrepo stop
```

### 9. `runrepo tree` & `runrepo cache` — Monorepo & Cache Management

```bash
# Visualize subproject dependency topology
runrepo tree ./my-monorepo

# List and clean cached repository clones
runrepo cache list
runrepo cache clean --all
```

---

## 🔧 Advanced Features & Autonomous Repair

### 1. Multi-Platform Resilience & Container Fallbacks
- **Windows Docker Container Daemon Mode**: When Docker runs in Windows container mode without Linux container support, RunRepo gracefully falls back to local embedded environments (e.g. SQLite/embedded databases) rather than failing.
- **Yarn Berry Modern Workspace Support**: Automatically uses `YARN_ENABLE_SCRIPTS=0` and `--mode=skip-build` to prevent recursive post-install stack overflow errors.
- **Strict Peer Dependency Resolution (`ERESOLVE`)**: Chained fallback from `--legacy-peer-deps` to `--force` handles strict, legacy, and mismatched peer trees on modern npm.
- **C-Extension Binary Wheel Python Version Fallback**: When C-extensions fail to compile on Python 3.14 on Windows without MSVC build tools, RunRepo automatically provisions a Python 3.12 virtualenv with pre-built binary wheels.

### 2. Zero-Install Tool Shims
RunRepo utilizes dynamic zero-install tool shims (`uvx poetry`, `uvx pipenv`, `npx -y pnpm`, `npx -y yarn`) to execute necessary package managers on the fly without modifying host global configurations.

---

## 🔒 Reproducibility (`runrepo.yaml` & `runrepo.lock`)

RunRepo guarantees deterministic, repeatable execution across different machines and CI environments.

### Declarative Overrides (`runrepo.yaml`)

```yaml
version: 1
project:
  name: "my-web-app"
  entrypoint: "src/index.ts"

environment:
  node: ">=20.0.0"
  services:
    - name: postgres
      version: "16-alpine"
      port: 5432

scripts:
  install: "pnpm install --frozen-lockfile"
  start: "pnpm dev"
```

### Deterministic Lockfiles (`runrepo.lock`)

When a project is successfully prepared, RunRepo generates a sorted, secret-sanitized `runrepo.lock` file:

```yaml
# Generated by RunRepo v1.0.0 - DO NOT EDIT MANUALLY
version: 1
generated_at: "2026-08-19T12:00:00Z"
project:
  name: "my-web-app"
runtimes:
  node: "22.14.0"
package_managers:
  pnpm: "10.4.0"
services:
  - name: postgres
    image: "postgres:16-alpine"
    port: 5432
```

---

## 🛡️ Safety & Sandboxing Model

RunRepo implements multi-layered security controls to protect the host system:

1. **Path Boundary Enforcement**: Actions are strictly constrained within the target repository path (`SandboxPolicy`). Directory traversal (`../../`) is rejected.
2. **Destructive Command Elimination**: Commands matching dangerous patterns (`rm -rf /`, `format`, `drop database`, `mkfs`) are intercepted and blocked.
3. **Environment Redaction**: API keys, tokens, and database passwords in logs and exception traces are automatically redacted (`[REDACTED]`).
4. **Non-Destructive `.env` Merging**: Existing `.env` files are never overwritten; variables are non-destructively merged, and backups (`.env.backup.<timestamp>`) are created atomically.

---

## 🔍 Diagnostics & Port Conflict Resolution

When a service or application startup fails, the **Diagnostics Engine** analyzes the failure using deterministic heuristic rules:

1. **Port Occupancy Triage**: Queries OS sockets (via Windows `netstat -ano` or Unix `lsof`) to identify the PID and process name occupying the required port.
2. **Next-Available Port Discovery**: Automatically scans and reallocates the service to the next free port (`5433`, `5434`, etc.) and updates `.env`.
3. **Actionable Suggestions**: Outputs formatted CLI instructions explaining how to resolve the conflict.

---

## 🤖 Optional Gemini AI Integration

For repositories with obscure startup conventions or complex errors, RunRepo provides optional Google Gemini AI assistance:

```bash
# Enable AI-powered analysis and diagnostics
export GEMINI_API_KEY="your-api-key"
runrepo setup https://github.com/owner/project
```

- **Structured Output**: AI responses are validated against strict Pydantic schemas.
- **Safety Filtering**: AI suggestions containing dangerous or destructive commands are rejected.
- **Pure REST**: Communicates directly with Google Gemini REST endpoints with zero heavy external SDK dependencies.

---

## 🧪 Testing & Quality Assurance

RunRepo maintains a comprehensive, production-grade test suite with **100% test pass rate**:

```bash
# Run the complete test suite with coverage
uv run pytest

# Run regression test suite
uv run pytest tests/test_batch_regressions.py

# Run real-world benchmark runner
uv run python tests/real_world/runner.py --batch 1
```

```text
============================= 328 passed in 36.85s =============================
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
