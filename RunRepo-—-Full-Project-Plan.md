# RunRepo — Full Project Plan

## 1. Project concept

**RunRepo** is a developer tool that takes an arbitrary Git repository and attempts to make it runnable on the user's machine with minimal manual setup.

Example:

```bash
runrepo https://github.com/user/project
```

RunRepo should inspect the repository, determine what it needs, provision the required environment, install dependencies, configure services, and start the project.

The goal is **not** to create another AI coding assistant.

The goal is:

> **“I found a GitHub project. I want to run it. Make the environment work.”**

AI can optionally help interpret ambiguous setup instructions, but the core system must work deterministically without AI whenever possible.

---

# 2. The problem

Running an unfamiliar open-source repository frequently involves:

```text
git clone
↓
read README
↓
figure out language/runtime
↓
install correct runtime version
↓
install package manager
↓
install dependencies
↓
create .env
↓
figure out environment variables
↓
start PostgreSQL/Redis/etc.
↓
run migrations
↓
generate code
↓
start backend
↓
start frontend
↓
debug errors
```

The documentation may be:

* incomplete
* outdated
* Linux-only
* written for macOS
* missing Windows instructions
* assuming globally installed software
* dependent on undocumented services
* using obsolete package versions

RunRepo should turn that into something closer to:

```bash
runrepo https://github.com/example/project
```

---

# 3. Core philosophy

The project should follow these principles.

### Deterministic first

Use normal programmatic detection before AI.

For example:

```text
package.json → Node
pnpm-lock.yaml → pnpm
requirements.txt → Python
pyproject.toml → Python
Cargo.toml → Rust
go.mod → Go
docker-compose.yml → Docker
prisma/schema.prisma → Prisma
```

Do not ask Gemini something that can be determined reliably from a file.

### AI only for ambiguity

Use Gemini when the repository contains something humans would normally have to interpret.

For example:

> README says "configure the database appropriately."

AI can determine what configuration the project expects based on the repository.

### Reproducibility

Everything RunRepo does should be observable and reproducible.

### Safe by default

RunRepo should not silently execute arbitrary destructive commands.

Commands should have classifications:

```text
SAFE
REQUIRES_CONFIRMATION
DANGEROUS
BLOCKED
```

---

# 4. MVP

Do **not** attempt to support every programming language initially.

The first release should target:

### Languages

* Node.js
* Python

### Package managers

* npm
* pnpm
* yarn
* pip
* uv

### Infrastructure

* Docker / Docker Compose
* PostgreSQL
* Redis

### Platforms

Primary:

* Windows 11

Secondary:

* Linux

macOS can come later.

This is a deliberate choice because Windows is particularly useful as a differentiator.

---

# 5. Example user experience

The main command:

```bash
runrepo https://github.com/user/project
```

RunRepo:

```text
RunRepo
────────────────────────────────────────

Repository:
github.com/user/project

Cloning repository...        ✓
Analyzing project...         ✓

Detected:
  Node.js 22
  pnpm 10
  PostgreSQL
  Docker Compose

Checking environment...

Node.js                    ✓ 22.15.0
pnpm                       ✓ 10.12.1
Docker                     ✓ Running
PostgreSQL                 ✗ Missing

A PostgreSQL service is required.

Recommended:
  Start PostgreSQL with Docker

[1] Start automatically
[2] Show instructions
[3] Cancel
```

Then:

```text
Starting PostgreSQL...      ✓
Installing dependencies...  ✓
Creating .env...            ✓
Running migrations...       ✓
Generating Prisma client... ✓

Starting application...

Frontend:
http://localhost:3000

Backend:
http://localhost:8000
```

---

# 6. Architecture

Use a modular architecture rather than putting everything inside one CLI file.

```text
runrepo/
│
├── cli/
│   ├── commands/
│   ├── output/
│   └── prompts/
│
├── core/
│   ├── analyzer/
│   ├── detector/
│   ├── planner/
│   ├── executor/
│   ├── environment/
│   ├── services/
│   ├── process/
│   └── diagnostics/
│
├── providers/
│   ├── node/
│   ├── python/
│   ├── docker/
│   ├── postgres/
│   ├── redis/
│   └── git/
│
├── ai/
│   ├── gemini/
│   ├── prompts/
│   └── schemas/
│
├── workspace/
│
├── tests/
│
└── docs/
```

---

# 7. Recommended technology

Since your target is primarily Windows and you already work heavily with Python:

## Core

**Python**

Use:

* `typer` for CLI
* `rich` for terminal UI
* `pydantic` for structured models
* `httpx` for HTTP
* `psutil` for process/system information
* `subprocess` for executing tools
* `pathlib` for filesystem
* `platformdirs` for application directories

Potentially:

* `watchdog`
* `PyYAML`
* `tomllib`

### Why Python?

Because RunRepo will spend most of its time doing:

* filesystem inspection
* process execution
* environment detection
* parsing configuration
* networking
* orchestration

Python is very good at these.

---

# 8. Repository analyzer

This is the heart of RunRepo.

Given:

```text
/path/to/repository
```

the analyzer creates a structured representation:

```python
ProjectInfo(
    languages=["javascript"],
    frameworks=["nextjs"],
    package_manager="pnpm",
    runtime={"node": "22"},
    databases=["postgresql"],
    services=["redis"],
    package_scripts=["dev", "build", "start"],
    environment_variables=[...],
    docker=True,
    entrypoints=[...],
)
```

---

# 9. Detection engine

Do not use AI here.

Create detectors.

### Node detector

Look for:

```text
package.json
package-lock.json
pnpm-lock.yaml
yarn.lock
bun.lock
.nvmrc
.node-version
```

Determine:

```text
Node version
Package manager
Framework
Scripts
Dependencies
Workspace/monorepo
```

### Python detector

Look for:

```text
requirements.txt
pyproject.toml
Pipfile
Pipfile.lock
poetry.lock
uv.lock
.python-version
```

Determine:

```text
Python version
Package manager
Framework
Dependencies
Entry point
```

### Database detector

Look for:

```text
prisma/
alembic/
migrations/
db/
docker-compose.yml
```

Search source files for:

```text
DATABASE_URL
POSTGRES_
MYSQL_
MONGODB_
REDIS_URL
```

### Infrastructure detector

Detect:

```text
Dockerfile
docker-compose.yml
compose.yaml
Makefile
Taskfile
justfile
devcontainer.json
```

---

# 10. Dependency graph

After detecting everything, RunRepo should build a dependency graph.

Example:

```text
Next.js application
       │
       ├── Node 22
       ├── pnpm
       │
       └── API
            │
            ├── PostgreSQL
            └── Redis
```

Represent this internally as something like:

```text
Project
 ├── Runtime
 ├── PackageManager
 ├── Service
 ├── Database
 └── Command
```

This graph becomes extremely important later.

---

# 11. Environment inspection

Before installing anything, RunRepo checks the machine.

Example:

```text
Node:
installed = true
version = 22.14.0

pnpm:
installed = true
version = 10.8.1

Docker:
installed = true
running = false

Git:
installed = true

Python:
installed = true
version = 3.12.3
```

Create standardized checks:

```python
EnvironmentCheck(
    name="Node.js",
    status="ok",
    installed_version="22.14.0",
    required_version="22",
)
```

Possible statuses:

```text
OK
MISSING
WRONG_VERSION
BROKEN
UNKNOWN
```

---

# 12. Version management

Don't immediately install software globally.

RunRepo should eventually support multiple strategies.

Example:

```text
Node:
1. Existing system Node
2. nvm
3. Volta
4. Docker
```

Python:

```text
1. Existing Python
2. uv
3. pyenv
4. virtualenv
5. Docker
```

For MVP, keep this simple.

Prefer existing system software.

If something is missing:

```text
Would you like RunRepo to install it?
```

Later add automatic runtime managers.

---

# 13. Environment variables

This is one of the most important features.

RunRepo should detect:

```text
.env.example
.env.template
README references
source-code references
docker-compose variables
```

Then produce:

```text
Required environment variables:

DATABASE_URL       required
JWT_SECRET         required
NEXT_PUBLIC_API    required
STRIPE_SECRET_KEY  optional
```

Categorize them:

```text
AUTO_GENERATABLE
LOCAL_DEFAULT
USER_REQUIRED
EXTERNAL_SERVICE
SECRET
```

For example:

```text
JWT_SECRET
```

can be automatically generated.

But:

```text
OPENAI_API_KEY
STRIPE_SECRET_KEY
```

cannot.

RunRepo should explicitly tell the user.

---

# 14. Automatic local service provisioning

This is one of RunRepo's biggest differentiators.

Suppose the repository expects PostgreSQL.

Rather than saying:

> Install PostgreSQL.

RunRepo can detect Docker and do:

```text
docker compose up -d postgres
```

or generate a temporary managed container.

Eventually:

```text
runrepo service start postgres
```

RunRepo should know:

```text
container name
port
username
password
database
volume
health status
```

Same for:

* PostgreSQL
* Redis
* MySQL
* MongoDB

Initially only support PostgreSQL and Redis.

---

# 15. Installation planner

The analyzer shouldn't execute commands directly.

It creates a plan.

Example:

```text
Plan:

1. Verify Git
2. Verify Node 22
3. Verify pnpm
4. Start PostgreSQL container
5. Generate .env
6. Install dependencies
7. Run Prisma generate
8. Run migrations
9. Start development server
```

Represent this as executable steps:

```python
PlanStep(
    id="postgres",
    description="Start PostgreSQL",
    action=...
)
```

Each step should have:

```text
description
dependencies
command
risk level
rollback
verification
```

---

# 16. Executor

Executor runs the plan.

It should provide:

```text
✓ Completed
✗ Failed
⚠ Warning
→ Running
○ Skipped
```

Example:

```text
[1/8] Checking Node.js       ✓
[2/8] Checking pnpm          ✓
[3/8] Starting PostgreSQL    ✓
[4/8] Creating environment   ✓
[5/8] Installing packages    →
```

Capture:

* stdout
* stderr
* exit code
* duration
* command

Never hide command output completely.

---

# 17. Verification

After every important step, verify it.

Don't assume:

```bash
npm install
```

means installation worked.

Actually verify:

```text
node_modules exists
package manager exit code == 0
expected executable exists
```

For PostgreSQL:

```text
container running
port reachable
authentication succeeds
database exists
```

For web applications:

```text
port listening
HTTP request succeeds
expected response
```

This turns RunRepo from a command runner into a real environment orchestrator.

---

# 18. Process management

RunRepo should track processes it starts.

Example:

```text
RunRepo session

Frontend
PID 13452
Port 3000

Backend
PID 15521
Port 8000
```

Commands:

```bash
runrepo status
runrepo logs
runrepo stop
```

Eventually:

```bash
runrepo restart
```

---

# 19. Diagnostics

When something fails:

```text
npm run dev
```

returns:

```text
EADDRINUSE
```

RunRepo shouldn't just show that.

Its diagnostics engine should inspect:

```text
port
process
PID
network interface
firewall
existing project
```

Then report:

```text
Port 3000 is already occupied.

Process:
node.exe
PID:
18492

Command:
vite

Possible cause:
Another instance of this project is already running.

Recommended:
Terminate PID 18492.

[Kill process]
```

This is where your earlier `port 5050` problem becomes a feature.

---

# 20. AI layer

Only after the deterministic engine exists.

Use Gemini for:

### Repository understanding

Analyze:

```text
README
documentation
scripts
configuration
source structure
```

### Ambiguous setup instructions

For example:

```text
"Create the required database and configure it accordingly."
```

Gemini determines what that means based on the repository.

### Failure diagnosis

Feed Gemini structured information:

```json
{
  "command": "pnpm install",
  "exit_code": 1,
  "stderr": "...",
  "os": "Windows",
  "node_version": "24.18.0"
}
```

Ask for:

```text
Likely cause
Evidence
Suggested safe fixes
Confidence
```

Do **not** give Gemini unlimited shell access by default.

---

# 21. AI output must be structured

Never rely on:

```text
"Gemini says you should install X..."
```

Use JSON schema.

Example:

```json
{
  "problem": "pnpm unavailable",
  "cause": "Corepack is disabled",
  "confidence": 0.96,
  "actions": [
    {
      "command": "corepack enable",
      "risk": "low"
    }
  ]
}
```

Then RunRepo itself decides whether the command may be executed.

---

# 22. Security model

This is extremely important.

RunRepo will execute arbitrary repository commands.

That means the project is potentially dangerous.

The first version should clearly distinguish:

### Automatic

```text
git clone
mkdir
read files
parse configs
check versions
```

### Confirmation required

```text
npm install
pip install
docker compose up
run migration
start script
```

### Dangerous

```text
rm -rf
format
disk operations
registry modification
firewall modification
service deletion
```

Never execute destructive commands automatically.

Eventually add a sandbox mode.

---

# 23. CLI interface

Primary:

```bash
runrepo <repository>
```

Other commands:

```bash
runrepo analyze .
runrepo plan .
runrepo setup .
runrepo start .
runrepo status .
runrepo logs .
runrepo stop .
runrepo doctor .
runrepo clean .
```

Useful flags:

```bash
runrepo URL --non-interactive
runrepo URL --dry-run
runrepo URL --yes
runrepo URL --docker
runrepo URL --verbose
```

---

# 24. Dry-run mode

This is essential.

```bash
runrepo ./project --dry-run
```

Output:

```text
RunRepo plan

✓ Node 22 detected
✓ pnpm detected
→ Start PostgreSQL Docker container
→ Create .env
→ pnpm install
→ pnpm prisma generate
→ pnpm prisma migrate dev
→ pnpm dev

No actions performed.
```

This lets users trust the tool.

---

# 25. Project manifest

Eventually allow repositories to explicitly define RunRepo behavior.

Create:

```text
runrepo.yaml
```

Example:

```yaml
runtime:
  node: "22"

package_manager: pnpm

services:
  - postgres
  - redis

environment:
  generate:
    - JWT_SECRET

commands:
  install: pnpm install
  migrate: pnpm prisma migrate dev
  start: pnpm dev
```

This becomes the **best-practice format for projects that want to support RunRepo**.

That is potentially much bigger than the CLI itself.

---

# 26. Automatic mode vs manifest mode

RunRepo should support two workflows.

### Zero configuration

```bash
runrepo github.com/project/repo
```

Infer everything.

### Explicit

Repository contains:

```text
runrepo.yaml
```

RunRepo follows it exactly.

This gives developers control without sacrificing convenience.

---

# 27. Monorepo support

Eventually detect:

```text
apps/
packages/
services/
```

Examples:

```text
pnpm-workspace.yaml
turbo.json
nx.json
lerna.json
```

Understand:

```text
frontend
backend
shared
```

and determine startup commands.

Don't implement this in MVP, but design the architecture for it.

---

# 28. First milestone

Build only this:

```bash
runrepo ./local-repository
```

It should:

1. Detect Node/Python.
2. Detect package manager.
3. Detect project type.
4. Detect required versions.
5. Check installed environment.
6. Generate an execution plan.
7. Show the plan.
8. Ask for confirmation.
9. Install dependencies.
10. Run the project's development command.
11. Detect the resulting localhost URL.

That's your **MVP**.

No Gemini yet.

---

# 29. Second milestone

Add:

* `.env` detection
* Docker detection
* PostgreSQL
* Redis
* migrations
* service health checks
* process management
* logs
* `doctor`
* `status`
* `stop`

At this point RunRepo is already a useful product.

---

# 30. Third milestone

Add GitHub support:

```bash
runrepo https://github.com/user/repo
```

Automatically:

```text
clone
analyze
plan
setup
run
```

Also support:

```bash
runrepo owner/repo
```

Eventually:

```bash
runrepo PR_URL
```

which could clone the PR branch and run it.

That would be a particularly useful feature for open-source contributors.

---

# 31. Fourth milestone

Add Gemini.

AI is now used for:

* README interpretation
* ambiguous setup
* error diagnosis
* dependency conflict analysis
* deciding between multiple valid setup strategies

At this point AI enhances the product rather than being the product.

---

# 32. Fifth milestone

Add a local repository cache.

Example:

```text
~/.runrepo/
    cache/
    environments/
    logs/
    sessions/
```

Avoid repeatedly downloading or rebuilding environments.

---

# 33. Sixth milestone

Add reproducible environments.

Eventually RunRepo should be able to produce:

```text
runrepo.lock
```

containing:

```text
runtime versions
package manager
dependency versions
service versions
ports
environment configuration
```

Then:

```bash
runrepo reproduce
```

recreates the same environment.

This pushes the project beyond “setup helper” toward **development environment reproducibility**.

---

# 34. Long-term vision

The mature version becomes:

```text
                     Git Repository
                           │
                           ▼
                    ┌─────────────┐
                    │   RunRepo   │
                    │   Analyzer  │
                    └──────┬──────┘
                           │
                    Project Graph
                           │
                           ▼
                    ┌─────────────┐
                    │    Planner  │
                    └──────┬──────┘
                           │
                 ┌─────────┼─────────┐
                 ▼         ▼         ▼
              Runtime   Services   Config
                 │         │         │
                 └─────────┼─────────┘
                           ▼
                    ┌─────────────┐
                    │   Executor  │
                    └──────┬──────┘
                           ▼
                    Running Project
                           │
                           ▼
                    Verification
                           │
                    ┌──────┴──────┐
                    │             │
                   ✓               ✗
                              Diagnostics
                                   │
                                   ▼
                              Gemini
```

---

# 35. Killer features to eventually add

These are the features that could make RunRepo genuinely stand out.

### `runrepo repair`

Project doesn't start.

RunRepo diagnoses it and proposes a repair.

```bash
runrepo repair
```

### `runrepo doctor`

Checks the entire environment.

### `runrepo reproduce`

Recreates another developer's environment.

### `runrepo export`

Exports a reproducible configuration.

```bash
runrepo export > runrepo.yaml
```

### `runrepo share`

Generate a setup specification for another developer.

### `runrepo pr`

Run a GitHub pull request locally.

```bash
runrepo pr 123
```

### `runrepo benchmark`

Run the repository and measure:

* build time
* startup time
* memory
* CPU

### `runrepo clean`

Remove only resources RunRepo created.

---

# 36. The feature I think could make it genuinely special

## `runrepo pr`

Imagine reviewing a GitHub PR.

Instead of:

```text
Read code
↓
Guess whether it works
↓
Clone
↓
Install dependencies
↓
Configure environment
↓
Run
```

You do:

```bash
runrepo pr https://github.com/user/project/pull/184
```

RunRepo:

```text
PR #184

✓ Repository cloned
✓ Dependencies installed
✓ Environment configured
✓ PostgreSQL started
✓ Tests passed
✓ Application started

Running smoke tests...

GET /
      200 ✓

POST /api/login
      200 ✓

GET /dashboard
      200 ✓

PR successfully reproduced locally.
```

That's a **very compelling developer tool**.

---

# 37. Project roadmap

### Phase 1 — Foundation

```text
CLI
Git
filesystem
project detection
Node
Python
package managers
environment checks
```

### Phase 2 — Execution

```text
planner
executor
confirmation
logging
verification
process manager
```

### Phase 3 — Infrastructure

```text
Docker
PostgreSQL
Redis
.env
migrations
health checks
```

### Phase 4 — GitHub

```text
GitHub URLs
branches
PRs
repository cache
```

### Phase 5 — Diagnostics

```text
doctor
network diagnostics
port diagnostics
dependency failures
startup failures
```

### Phase 6 — Gemini

```text
README analysis
ambiguous instructions
failure diagnosis
repair suggestions
```

### Phase 7 — Reproducibility

```text
runrepo.yaml
runrepo.lock
export/import
reproduction
```

### Phase 8 — Advanced

```text
monorepos
PR execution
sandboxing
remote environments
cross-platform support
plugins
```

---

# 38. What NOT to build initially

Do not start with:

* GUI
* web dashboard
* authentication
* cloud infrastructure
* user accounts
* billing
* marketplace
* 20 programming languages
* Kubernetes
* macOS support
* AI autonomous agent
* huge plugin ecosystem

The first version should be a **CLI that works extremely well**.

---

# 39. First repository structure

Start with:

```text
runrepo/
├── pyproject.toml
├── README.md
├── LICENSE
│
├── src/
│   └── runrepo/
│       ├── __init__.py
│       ├── cli.py
│       │
│       ├── analyzer/
│       │   ├── __init__.py
│       │   ├── analyzer.py
│       │   ├── models.py
│       │   └── detectors/
│       │       ├── node.py
│       │       ├── python.py
│       │       ├── docker.py
│       │       └── database.py
│       │
│       ├── environment/
│       │   ├── checker.py
│       │   └── models.py
│       │
│       ├── planner/
│       │   ├── planner.py
│       │   └── models.py
│       │
│       ├── executor/
│       │   ├── executor.py
│       │   └── process.py
│       │
│       ├── diagnostics/
│       │   └── diagnostics.py
│       │
│       ├── services/
│       │   ├── docker.py
│       │   ├── postgres.py
│       │   └── redis.py
│       │
│       └── ai/
│           └── gemini.py
│
└── tests/
    ├── fixtures/
    ├── test_analyzer.py
    ├── test_environment.py
    └── test_planner.py
```

---

# 40. First coding task in the new chat

Do **not** ask the new chat to build the entire project in one prompt.

Start with the architecture and MVP.

Paste something like this into the new chat:

```text
I want to build a project called RunRepo.

RunRepo is a CLI developer tool whose purpose is:

"I give it an arbitrary Git repository and it makes that repository runnable on my machine with minimal manual setup."

This is NOT an AI wrapper. The deterministic automation/orchestration system is the core product. AI/Gemini is optional and will be added later for ambiguity and diagnostics.

Initial target:
- Windows 11 first
- Linux second
- Python implementation
- CLI only, no GUI
- Node.js + Python repositories initially
- npm/pnpm/yarn/pip/uv
- Docker/Docker Compose
- PostgreSQL and Redis
- .env detection
- dependency installation
- migrations
- process management
- health checks
- diagnostics

Core architecture:
CLI → Analyzer → Project Graph → Environment Checker → Planner → Executor → Verification → Diagnostics

Important design principles:
1. Deterministic detection before AI.
2. AI only for ambiguity and diagnosis.
3. Every action must be observable.
4. Dangerous operations require confirmation.
5. Dry-run must be supported.
6. Every execution step needs verification.
7. The system must be modular and testable.
8. The first version should work completely without Gemini.

MVP:
runrepo ./repository

It should:
1. Detect Node/Python.
2. Detect package manager.
3. Detect project type.
4. Detect required runtime versions.
5. Inspect the local environment.
6. Generate a setup plan.
7. Display the plan.
8. Ask for confirmation.
9. Install dependencies.
10. Run development commands.
11. Detect the resulting localhost service.

Recommended Python stack:
- Typer
- Rich
- Pydantic
- httpx
- psutil
- pathlib
- subprocess
- platformdirs

Initial project structure:

runrepo/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── runrepo/
│       ├── cli.py
│       ├── analyzer/
│       │   ├── analyzer.py
│       │   ├── models.py
│       │   └── detectors/
│       │       ├── node.py
│       │       ├── python.py
│       │       ├── docker.py
│       │       └── database.py
│       ├── environment/
│       │   ├── checker.py
│       │   └── models.py
│       ├── planner/
│       │   ├── planner.py
│       │   └── models.py
│       ├── executor/
│       │   ├── executor.py
│       │   └── process.py
│       ├── diagnostics/
│       │   └── diagnostics.py
│       ├── services/
│       │   ├── docker.py
│       │   ├── postgres.py
│       │   └── redis.py
│       └── ai/
│           └── gemini.py
└── tests/

Do not build the whole application immediately.

Start by designing the domain models and architecture, then implement the repository analyzer and Node/Python detectors first.

Explain the design decisions as we go and keep the architecture extensible for future features such as:

- runrepo https://github.com/...
- runrepo pr <PR>
- runrepo doctor
- runrepo repair
- runrepo reproduce
- runrepo.yaml
- runrepo.lock
- Gemini diagnostics
- monorepo support

The long-term goal is to make "run any open-source repository locally" dramatically easier and more reliable.
```