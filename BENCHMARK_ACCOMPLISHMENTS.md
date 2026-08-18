# RunRepo — Real-World 50-Repository Benchmark Accomplishments

This document serves as the persistent, auditable record of all real-world validation batches executed against the 50-repository corpus. It records baseline environments, per-repository outcomes, defect analyses, architectural fixes, regression tests, and verification metrics.

---

## Host Environment Baseline Snapshot

Recorded prior to benchmark execution on host machine:
* **OS**: Microsoft Windows 11 Pro (AMD64)
* **Hardware**: 15.64 GB RAM | ~48.9 GB Free Disk (C:)
* **Python**: 3.12.10 (Standard), uv 0.12.0, pip 26.2.1
* **Node Ecosystem**: Node v24.18.0, npm 11.18.0, pnpm 11.21.0, yarn 1.22.22
* **Container Runtime**: Docker 28.5.1 (Community), Docker Compose v2.40.3-desktop.1
* **Benchmark Constraints**: `RUNREPO_NO_AI=1` (Strict deterministic rule-based benchmarking, 0 LLM calls).

---

## Batch 1: Core Node.js & Fullstack Web (Repositories 1–10)

* **Status**: **100% COMPLETE & VERIFIED**
* **Test Suite**: 311 / 311 unit & integration tests passing (`uv run pytest`).
* **Summary Score**: 6 `FULL_SUCCESS`, 3 `PARTIAL_SUCCESS`, 1 `CORRECTLY_UNSUPPORTED`, 0 `INCORRECT_FAILURE`.

### Results Matrix

| ID | Repository | Category | Difficulty | Classification | Duration | Summary & Verification Details |
|:---|:---|:---|:---|:---|:---|:---|
| **1** | **[Express](https://github.com/expressjs/express)** | `WEB_BACKEND` | `MEDIUM` | `FULL_SUCCESS` | 4.85s | Analyzed `package.json`, installed dependencies cleanly, validated package manager & directory integrity. |
| **2** | **[Fastify](https://github.com/fastify/fastify)** | `WEB_BACKEND` | `MEDIUM` | `FULL_SUCCESS` | 21.02s | Analyzed `package.json`, detected npm scripts, installed dependencies cleanly with exit code 0. |
| **3** | **[NestJS](https://github.com/nestjs/nest)** | `FULLSTACK` | `HARD` | `PARTIAL_SUCCESS` | 47.66s | Root monorepo workspace dependencies cleanly installed (audited 1,600+ packages); handled libuv postinstall scripts (`opencollective`); skipped 31 educational sample folders from redundant sequential installs; successfully scoped and executed app planning. |
| **4** | **[Fastify Example](https://github.com/fastify/example)** | `WEB_BACKEND` | `EASY` | `PARTIAL_SUCCESS` | 38.48s | Discovered subdirectory Docker Compose file (`fastify-postgres/docker-compose.yaml`), provisioned PostgreSQL container with port verification, installed npm dependencies across subprojects. Accurately detected and reported upstream Fastify 5 `listen(3000)` syntax crash. |
| **5** | **[p-map](https://github.com/sindresorhus/p-map)** | `LIBRARY` | `EASY` | `FULL_SUCCESS` | 5.89s | Detected pure ESM Node library, verified npm dependencies with retry mechanism for transient socket hang-ups. |
| **6** | **[Chalk](https://github.com/chalk/chalk)** | `LIBRARY` | `EASY` | `FULL_SUCCESS` | 5.01s | Verified Node.js runtime and npm package manager; installed dependencies cleanly. |
| **7** | **[Commander.js](https://github.com/tj/commander.js)** | `CLI_TOOL` | `EASY` | `FULL_SUCCESS` | 3.13s | Verified CLI tool manifest and successfully installed dependencies. |
| **8** | **[Axios](https://github.com/axios/axios)** | `LIBRARY` | `MEDIUM` | `FULL_SUCCESS` | 23.20s | Detected npm monorepo workspaces and dependencies, installed all packages cleanly. |
| **9** | **[Next.js](https://github.com/vercel/next.js)** | `FULLSTACK` | `VERY_HARD` | `CORRECTLY_UNSUPPORTED` | 14.74s | Cloned with Windows long-paths enabled (`core.longpaths=true`); accurately identified blocking prerequisites without crashing (requires Node 20 strictly, while host has Node 24; requires Rust runtime and Cargo package manager for Turbopack which are absent on host). |
| **10** | **[Remix](https://github.com/remix-run/remix)** | `FULLSTACK` | `HARD` | `PARTIAL_SUCCESS` | 108.75s | Detected pnpm workspace monorepo, installed dependencies via `npx -y pnpm install`, launched background app and dynamically detected listening ports via process logs. |

---

## Genuine Defects Identified & Architectural Fixes Applied

1. **Transient Network Disconnects & Retries (`InstallDepsStepHandler`)**:
   - *Problem*: Transient network drops (`ECONNRESET`, `ETIMEDOUT`, `fetch failed`) caused dependency steps to fail immediately.
   - *Fix*: Added automatic retry on transient socket errors in `src/runrepo/executor/handlers/install.py`.
2. **Windows Long File Paths on Deep Repositories (`GitManager`)**:
   - *Problem*: Git clone failed on deep monorepos (e.g. Next.js, Turbopack) due to Windows 260-character `MAX_PATH` limits.
   - *Fix*: Added `-c core.longpaths=true` to `git clone` and `git init` in `src/runrepo/repository/git.py`.
3. **Subproject Step ID Collisions in Monorepos (`ExecutionPlanner`)**:
   - *Problem*: Monorepos with identical subproject directory names caused step ID collisions in the execution graph.
   - *Fix*: Disambiguated scope prefixes using sanitized relative paths and added step ID deduplication in `src/runrepo/planner/planner.py`.
4. **Subdirectory Docker Compose Discovery & Directory Scoping (`ComposeManager`)**:
   - *Problem*: Docker Compose files located in subfolders (e.g., `fastify-postgres/docker-compose.yaml`) were not discovered, or executed with wrong root working directory.
   - *Fix*: Enhanced `ComposeManager.find_compose_file` and `ComposeManager.up` (`src/runrepo/services/compose.py`) to search immediate subdirectories and set `cwd` to the compose file folder.
5. **Root Package Manager Propagation to Subprojects (`ExecutionPlanner`)**:
   - *Problem*: Subprojects without an explicit `packageManager` field defaulted to `npm` even when the monorepo root was `pnpm` or `yarn`.
   - *Fix*: Inherited root package manager in subproject detection and startup resolution (`src/runrepo/planner/planner.py`).
6. **Peer Dependency Conflict Handling (`InstallDepsStepHandler`)**:
   - *Problem*: npm 7+ `ERESOLVE` errors halted installations for repos with conflicting peer dependencies (e.g. NestJS).
   - *Fix*: Added automatic `--legacy-peer-deps` retry fallback in `src/runrepo/executor/handlers/install.py`.
7. **Windows Read-Only Git File Locks on Cache Cleanup (`_safe_rmtree`)**:
   - *Problem*: Standard `shutil.rmtree(..., ignore_errors=True)` silently failed to remove Git pack files on Windows due to read-only attributes (`stat.S_IWRITE`).
   - *Fix*: Created robust `_safe_rmtree` handling Windows file permission errors in `src/runrepo/repository/manager.py` and `git.py`.
8. **Broken Lifecycle Postinstall Script Crashes (`InstallDepsStepHandler`)**:
   - *Problem*: Advertising/donation postinstall scripts (`opencollective`) crashed libuv on Windows with code `3221226505`.
   - *Fix*: Added `--ignore-scripts` fallback in `src/runrepo/executor/handlers/install.py`.
9. **Monorepo Sample Directory Explosion Skip (`ExecutionPlanner`)**:
   - *Problem*: Monorepos containing dozens of demonstration samples (e.g. NestJS with 31 samples) spent 15+ minutes running redundant sequential installs.
   - *Fix*: Added `skip_sub_install` for `sample/`, `samples/`, `example/`, `examples/` in monorepos where root dependencies were already installed (`src/runrepo/planner/planner.py`).
10. **Test & Integration Compose File Exclusion (`DockerDetector` & `ComposeManager`)**:
    - *Problem*: Compose files in `integration/` or `tests/` directories containing heavy test harnesses (Kafka, Zookeeper, NATS, Mongo, RabbitMQ, Redis) were erroneously treated as development backing services.
    - *Fix*: Excluded `test/`, `tests/`, `integration/`, `e2e/`, `fixtures/`, `benchmarks/`, `ci/` in `src/runrepo/analyzer/detectors/docker.py` and `src/runrepo/services/compose.py`.
11. **Per-Directory Scoping for Prisma and Alembic (`ExecutionPlanner`)**:
    - *Problem*: Global Prisma/Alembic detection generated generate/migrate steps across unrelated scopes.
    - *Fix*: Strictly scoped Prisma and Alembic steps to directories containing `schema.prisma` or `alembic.ini` in `src/runrepo/planner/planner.py`.
12. **Dynamic URL & Port Discovery (`HttpVerifier`)**:
    - *Problem*: Apps listening on non-standard ports (e.g. 44100, 5173) timed out when probed against port 3000.
    - *Fix*: Added live regex scanning of process stdout/stderr in `HttpVerifier` to detect listening URLs/ports dynamically.

---

## Regression Tests Added

Added in `tests/test_batch_regressions.py`:
1. `test_regression_duplicate_subproject_names_step_id_uniqueness`
2. `test_regression_find_compose_file_in_subdirectory`
3. `test_regression_workspace_pm_propagation_to_subproject_startup`

All 311 tests passing in 78.52s.

---

## Next Steps: Batch 2 Readiness

* **Target**: Batch 2 (Repositories 11–20: Svelte, Vue, Vite, Astro, Nuxt, FastAPI, Flask, Django, Requests, Pydantic).
* **Focus**: Modern Frontend (Vite/Svelte/Vue/Astro/Nuxt) and Core Python web frameworks & libraries (FastAPI, Flask, Django, Requests, Pydantic).
