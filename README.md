<div align="center">

# ⚡ RunRepo

**Deterministic Repository Analyzer & Local Environment Orchestrator**

*“I found an open-source GitHub project. I want to run it. Make the environment work.”*

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Package Manager](https://img.shields.io/badge/managed%20by-uv-purple.svg?style=flat-square)](https://github.com/astral-sh/uv)
[![Test Suite](https://img.shields.io/badge/tests-273%20passed-success.svg?style=flat-square&logo=pytest&logoColor=white)](https://github.com/AmirHossein-84/RunRepo)
[![Platform](https://img.shields.io/badge/platform-Windows%2011%20%7C%20Linux%20%7C%20macOS-informational.svg?style=flat-square)](https://github.com/AmirHossein-84/RunRepo)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)

[English](#-english-documentation) • [فارسی (Persian)](#-راهنمای-فارسی-persian-documentation)

---

</div>

## 📑 Table of Contents

- [Overview & Philosophy](#-overview--philosophy)
- [System Architecture](#-system-architecture)
- [Key Capabilities](#-key-capabilities)
- [Getting Started & Installation](#-getting-started--installation)
- [CLI Command Reference](#-cli-command-reference)
- [Reproducibility (`runrepo.yaml` & `runrepo.lock`)](#-reproducibility-runrepoyaml--runrepolock)
- [Safety & Sandboxing Model](#-safety--sandboxing-model)
- [Diagnostics & Port Conflict Resolution](#-diagnostics--port-conflict-resolution)
- [Optional Gemini AI Integration](#-optional-gemini-ai-integration)
- [Testing & Quality Assurance](#-testing--quality-assurance)
- [راهنمای فارسی (Persian Documentation)](#-راهنمای-فارسی-persian-documentation)

---

## 🌟 Overview & Philosophy

Running an unfamiliar open-source repository typically means cloning the code, deciphering incomplete README instructions, troubleshooting mismatching runtime versions, starting databases, setting up environment variables, and diagnosing broken ports.

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

1. **Deterministic First**: Programmatic detection via lockfiles, manifests, AST, and standard tools before any heuristics.
2. **Strict Phase Separation**: Analyzer (read-only facts) → Environment Checker (read-only host facts) → Planner (action DAG) → Executor (controlled side-effects) → Verifier (outcome assertion) → Diagnostics (failure explanation).
3. **Safe by Default**: Dangerous operations require interactive confirmation; destructive operations are blocked; dry-run mode (`--dry-run`) performs zero side-effects.
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
| **Package Managers** | Dependency graphs, monorepo workspaces, package scripts | **npm, pnpm, yarn, bun, uv, poetry, pipenv, pip, conda, cargo** |
| **Monorepo & Workspaces** | Workspace layout detection, subproject DAG resolution, targeted execution | **pnpm workspaces, Turborepo, Nx, Lerna, Yarn, UV workspaces** |
| **Infrastructure Services** | Automated Docker container provisioning, healthchecks, atomic rollbacks | **PostgreSQL, Redis, MySQL, MongoDB, RabbitMQ, MinIO (S3)** |
| **Environment Configuration** | Structured `.env` generation, secret categorization, placeholder warnings | **`.env.example`, `.env.template`, `.env.sample`, docker-compose envs** |
| **Sandboxed Execution** | Working directory boundaries, sanitized pass-through environment allowlists | **`SandboxedProcessExecutor`, `SandboxPolicy`, strict timeouts** |
| **Diagnostics & Observability** | Network socket probing, process ownership identification, PID triage | **Windows `netstat -ano`, Posix `lsof`, port conflict matching** |
| **Reproducibility** | Declarative manifest overrides and deterministic sorted lockfiles | **`runrepo.yaml` (v1) and `runrepo.lock` (v1, zero secrets)** |
| **AI Ambiguity Resolution** | Structured JSON schema validation, destructive command filtering | **Google Gemini 2.5 Flash / Pro (zero external SDKs, REST)** |

---

## 🚀 Getting Started & Installation

### Prerequisites

- **Python**: `>= 3.11`
- **uv**: *(Recommended)* Modern ultra-fast Python package manager
- **Docker**: *(Optional)* Required for auto-provisioning databases and services

---

### Quick 1-Line Automated Installation

**Linux / WSL 2 / macOS:**
```bash
git clone https://github.com/AmirHossein-84/RunRepo.git && cd RunRepo && chmod +x install.sh && ./install.sh
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/AmirHossein-84/RunRepo.git; cd RunRepo; .\install.ps1
```
*(The automated installer checks for `uv`, automatically installs it if missing, and provisions `runrepo` globally.)*

---

### Manual Installation

#### 🐧 Linux & WSL 2 (Step-by-Step)
```bash
# 1. Install uv in your Linux/WSL terminal (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# 2. Clone and install RunRepo globally as an editable CLI tool
git clone https://github.com/AmirHossein-84/RunRepo.git
cd RunRepo
uv tool install -e .

# 3. Verify installation
runrepo doctor
```

#### 🪟 Windows (Step-by-Step)
```powershell
# 1. Install uv (if not already installed)
irm https://astral.sh/uv/install.ps1 | iex

# 2. Clone and install RunRepo globally
git clone https://github.com/AmirHossein-84/RunRepo.git
cd RunRepo
uv tool install -e .

# 3. Verify installation
runrepo doctor
```

#### 🛠️ Local Development Mode (For Contributors)
Run directly within the virtual environment:

```bash
# Sync virtual environment and all dev dependencies with uv
uv sync --extra dev

# Run commands with `uv run`
uv run runrepo setup .
```

> [!TIP]
> **Isolated Cache Directory**: Remote repositories cloned from GitHub are **never** installed inside your RunRepo source directory. They are cleanly cached in your OS user data storage:
> - **Windows**: `%LOCALAPPDATA%\runrepo\repositories\`
> - **Linux / macOS / WSL 2**: `~/.local/share/runrepo/repositories/`
>
> You can inspect cached repositories anytime with `runrepo cache list` and clean them with `runrepo cache clean`.

### Quick Run

```bash
# Analyze, plan, and setup a local project:
runrepo setup .

# Or analyze any remote GitHub repository safely with dry-run:
runrepo setup https://github.com/facebook/react --dry-run
```

---

## 💻 CLI Command Reference

### Primary Commands

| Command | Description | Example |
| :--- | :--- | :--- |
| `runrepo setup [path]` | Full end-to-end orchestration (analyze → check → plan → execute) | `runrepo setup . --yes` |
| `runrepo plan [path]` | Generate and display the ordered execution DAG | `runrepo plan . --json` |
| `runrepo analyze [path]`| Deep inspection of codebase facts, frameworks, and scripts | `runrepo analyze . --evidence` |
| `runrepo doctor [path]` | Check host system against repository requirements | `runrepo doctor .` |
| `runrepo tree [path]` | Display monorepo workspace hierarchy and runnable applications | `runrepo tree .` |
| `runrepo clone <target>`| Safely acquire and cache a remote GitHub repository | `runrepo clone owner/repo` |

### Service & Process Management

| Command | Description | Example |
| :--- | :--- | :--- |
| `runrepo status` | List active background applications and listening ports | `runrepo status` |
| `runrepo logs [pid]` | Stream or inspect real-time logs from background processes | `runrepo logs 18492` |
| `runrepo stop [--all]` | Terminate managed background applications and service containers | `runrepo stop --all` |
| `runrepo clean` | Safely remove RunRepo-owned containers, volumes, and temporary state | `runrepo clean --yes` |

### Cache & Reproducibility

| Command | Description | Example |
| :--- | :--- | :--- |
| `runrepo config [path]` | Inspect active `runrepo.yaml` configuration overrides | `runrepo config .` |
| `runrepo lock [path]` | Generate or refresh a deterministic `runrepo.lock` file | `runrepo lock . --refresh` |
| `runrepo cache [list]` | List cached repositories, sizes, and validation health | `runrepo cache list` |
| `runrepo cache clean` | Safely purge stale cached repositories with confirmation | `runrepo cache clean --days 14` |

---

## 🔒 Reproducibility (`runrepo.yaml` & `runrepo.lock`)

RunRepo offers full environment reproducibility across machines:

### 1. User Manifest (`runrepo.yaml`)

Define explicit overrides without bypassing safety constraints:

```yaml
version: 1
name: my-fullstack-app

runtimes:
  node: ">=20.10.0"
  python: ">=3.11"

package_manager: pnpm

docker: true

services:
  postgres:
    image: postgres:16-alpine
    port: 5432
    database_name: app_development
  redis:
    port: 6379

startup:
  command: "pnpm run dev"
```

### 2. Lockfile (`runrepo.lock`)

Deterministic JSON lockfile generated via `runrepo lock`:

```json
{
  "lock_version": 1,
  "repository": {
    "name": "my-fullstack-app",
    "commit_hash": "a1b2c3d4",
    "ref": "main"
  },
  "platform": {
    "os": "windows",
    "arch": "x86_64"
  },
  "resolved_runtimes": {
    "node": "22.14.0",
    "python": "3.12.2"
  },
  "resolved_package_manager": "pnpm",
  "resolved_services": [
    { "name": "postgres", "image": "postgres:16-alpine", "port": 5432 },
    { "name": "redis", "image": "redis:7-alpine", "port": 6379 }
  ],
  "plan_steps": [
    "verify-node",
    "service-postgres",
    "service-redis",
    "configure-env",
    "install-deps",
    "start-app"
  ]
}
```

> [!NOTE]
> **Strict Zero-Secret Policy**: `runrepo.lock` never stores sensitive secret values. Only variable names and categorization metadata are recorded.

---

## 🛡 Safety & Sandboxing Model

Every execution step is classified into one of four safety tiers:

| Risk Level | Behavior | Example Actions |
| :--- | :--- | :--- |
| `SAFE` | Executed automatically in standard and automated modes | Checking tool versions, reading manifests |
| `REQUIRES_CONFIRMATION` | Prompts user interactively (or bypassed with `--yes`) | `pnpm install`, `docker compose up`, starting server |
| `DANGEROUS` | Explicit interactive prompt required | Modifying critical host files, deleting state |
| `BLOCKED` | **Execution strictly refused** | Running commands with missing runtimes or destructive commands |

### Process Confinement (`SandboxedProcessExecutor`)

- Restricts subprocess `cwd` strictly inside the repository boundary.
- Strips unauthorized host environment variables, passing only sanitized variables (`PATH`, `TEMP`, `USERPROFILE`, etc.).
- Enforces hard execution timeouts to prevent hanging background scripts.

---

## 🩺 Diagnostics & Port Conflict Resolution

When a service or application fails, RunRepo's rule-based diagnostic engine identifies the root cause and inspects process ownership:

```text
[!] Diagnostic: Network Port Conflict (5432)
Severity:     ERROR
Explanation:  A service failed to bind to port 5432 because another active process is using it.
              Occupied by PID 18492 (postgres.exe).

Suggested Actions:
  1. Terminate conflicting process (PID 18492) or configure another port in runrepo.yaml.
  2. Stop RunRepo-managed background services:
     $ runrepo stop --all
```

---

## 🤖 Optional Gemini AI Integration

When deterministic rules encounter unfamiliar setups or unknown errors, the optional AI layer (`src/runrepo/ai/`) resolves ambiguity:

- **Strict Validation**: All AI responses must conform to strict Pydantic schemas (`AIActionSuggestion`).
- **Destructive Command Guard**: Automatically filters out destructive patterns (`rm -rf`, `format`, `del /f`).
- **Privacy First**: Secrets and `.env` files are scrubbed before prompt construction.
- **Offline First**: Easily disabled globally via the `--no-ai` flag or `RUNREPO_NO_AI=1`.

---

## 🧪 Testing & Quality Assurance

RunRepo maintains **100% deterministic testing** with zero live Docker, GitHub, or database requirements:

```bash
# Run the complete test suite (273 tests)
uv run pytest -v

# Run with test coverage
uv run pytest --cov=runrepo --cov-report=term-missing
```

```text
============================ 273 passed in 16.61s =============================
```

---

<div dir="rtl">

## 🇮🇷 راهنمای فارسی (Persian Documentation)

### معرفی پروژه RunRepo

ابزار **RunRepo** یک ارکستریتور و ابزار خط فرمان (CLI) مدرن و هوشمند است که یک مخزن گیت (Git Repository) دلخواه را تحلیل کرده و بدون نیاز به کانفیگ دستی و خسته‌کننده، آن را بر روی سیستم شما آماده اجرا می‌کند.

> **هدف اصلی پروژه:** *"من یک پروژه متن‌باز پیدا کرده‌ام. می‌خواهم آن را اجرا کنم. محیط را به طور خودکار آماده کن."*

---

### ویژگی‌های کلیدی

- ⚡ **تحلیل کاملاً قطعی (Deterministic-First):** شناسایی زبان‌ها، پکیج منیجرها و وابستگی‌ها بدون وابستگی به هوش مصنوعی.
- 📦 **پشتیبانی از Monorepo:** مدیریت ساختارهای پیچیده مبتنی بر pnpm workspaces، Turborepo، Nx و Lerna.
- 🐳 **سرویس‌های داکر خودکار:** راه‌اندازی، بررسی سلامت و بازگردانی خودکار پایگاه‌های داده (PostgreSQL, MySQL, MongoDB, Redis, RabbitMQ, MinIO).
- 🔒 **سندباکس و امنیت بالا:** تفکیک متغیرهای محیطی حساس، محدود کردن دسترسی فرآیندها و مسدودسازی دستورات مخرب.
- 📋 **تکرارپذیری با Lockfile:** ذخیره تصمیمات در `runrepo.lock` بدون نشت کلیدها و پسوردهای حساس.
- 🩺 **سیستم عیب‌یابی پیشرفته:** تشخیص خطاهای پورت و شبکه همراه با استخراج PID و نام برنامه اشغال‌کننده پورت در ویندوز و لینوکس.
- 🤖 **هوش مصنوعی اختیاری:** استفاده از مدل‌های Gemini برای تفسیر فایل‌های README مبهم و تحلیل ارورهای ناشناخته.

---

### نحوه نصب و راه‌اندازی

#### ⚡ روش نصب خودکار و تک‌خطی (پیشنهادی)

**لینوکس، مک و WSL 2:**
```bash
git clone https://github.com/AmirHossein-84/RunRepo.git && cd RunRepo && chmod +x install.sh && ./install.sh
```

**ویندوز (PowerShell):**
```powershell
git clone https://github.com/AmirHossein-84/RunRepo.git; cd RunRepo; .\install.ps1
```
*(اسکریپت نصب خودکار، وجود `uv` را بررسی کرده و در صورت نیاز آن را نصب و سپس `runrepo` را به صورت سراسری مستقر می‌کند.)*

---

#### 🐧 نصب دستی در لینوکس و WSL 2 (گام‌به‌گام)
```bash
# ۱. نصب uv در ترمینال لینوکس یا WSL
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# ۲. کلون و نصب سراسری RunRepo
git clone https://github.com/AmirHossein-84/RunRepo.git
cd RunRepo
uv tool install -e .

# ۳. بررسی وضعیت نصب
runrepo doctor
```

#### 🪟 نصب دستی در ویندوز (گام‌به‌گام)
```powershell
# ۱. نصب uv
irm https://astral.sh/uv/install.ps1 | iex

# ۲. کلون و نصب سراسری RunRepo
git clone https://github.com/AmirHossein-84/RunRepo.git
cd RunRepo
uv tool install -e .

# ۳. بررسی وضعیت نصب
runrepo doctor
```

#### 🛠️ روش توسعه محلی (برای توسعه‌دهندگان)
اجرای مستقیم در محیط مجازی پروژه:

```bash
# نصب و همگام‌سازی تمام وابستگی‌ها
uv sync --extra dev

# اجرای دستورات با پیشوند uv run
uv run runrepo setup .
```

> **نکته امنیتی و ایزولاسیون حافظه:** پروژه‌های کلون‌شده از گیت‌هاب **هرگز** در داخل پوشه خود RunRepo دانلود نمی‌شوند؛ بلکه در دایرکتوری امن کاربر ذخیره می‌گردند:
> - **ویندوز:** `%LOCALAPPDATA%\runrepo\repositories\`
> - **لینوکس، مک و WSL 2:** `~/.local/share/runrepo/repositories/`
>
> برای مشاهده و پاکسازی کش مخازن می‌توانید از `runrepo cache list` و `runrepo cache clean` استفاده کنید.

---

### دستورات پرکاربرد خط فرمان

```bash
# ۱. تحلیل و راه‌اندازی کامل پروژه در دایرکتوری جاری
uv run runrepo setup .

# ۲. اجرای آزمایشی (بدون هیچ‌گونه تغییر در سیستم)
uv run runrepo setup . --dry-run

# ۳. بررسی وضعیت پیش‌نیازهای سیستم
uv run runrepo doctor .

# ۴. نمایش درخت مونو‌ریپو و برنامه‌های قابل اجرا
uv run runrepo tree .

# ۵. تولید فایل تکرارپذیری runrepo.lock
uv run runrepo lock .

# ۶. مشاهده لاگ‌ها و متوقف‌سازی سرویس‌های در حال اجرا
uv run runrepo status
uv run runrepo stop --all
```

---

### تست‌ها و اعتبارسنجی

پروژه دارای **۲۷۳ تست جامع** واحد (Unit) و یکپارچه‌سازی (Integration) است:

```bash
uv run pytest -v
```

</div>

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
