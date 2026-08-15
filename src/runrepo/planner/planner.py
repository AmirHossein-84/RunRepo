"""Deterministic Execution Planner converting ProjectInfo and EnvironmentState into an ordered ExecutionPlan."""

from pathlib import Path
from typing import Any

from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.environment.venv import VirtualEnvStatus, inspect_virtual_env
from runrepo.models import FrameworkCategory, ProjectInfo, ProjectType, SubprojectInfo
from runrepo.planner.graph import PlanGraph
from runrepo.planner.models import (
    ActionType,
    ExecutionPlan,
    PlanStatus,
    PlanStep,
    RiskLevel,
    StepRollback,
    StepVerification,
)


class ExecutionPlanner:
    """Deterministic, explainable execution planner with strict non-execution boundary."""

    def plan(self, project_info: ProjectInfo, env_state: EnvironmentState, config: Any | None = None) -> ExecutionPlan:
        """Construct an ordered ExecutionPlan from repository and environment facts."""
        steps: list[PlanStep] = []
        warnings: list[str] = list(project_info.warnings) if hasattr(project_info, "warnings") and isinstance(project_info.warnings, list) else []
        blocking_reasons: list[str] = []
        input_reasons: list[str] = []

        env_checks_map: dict[str, EnvironmentCheck] = {c.name.lower(): c for c in env_state.checks}

        # ---------------------------------------------------------
        # 1. Runtime Verification Steps
        # ---------------------------------------------------------
        runtime_step_ids: dict[str, str] = {}
        all_runtimes = list(project_info.runtimes)
        for sp in project_info.subprojects:
            all_runtimes.extend(sp.runtimes)

        for rt in all_runtimes:
            rt_name = rt.name.lower()
            if rt_name in runtime_step_ids:
                continue
            step_id = f"verify-runtime:{rt_name}"

            check = env_checks_map.get(rt_name)
            is_satisfied = check is not None and check.status == EnvironmentStatus.OK
            is_blocked = not is_satisfied

            risk = RiskLevel.SAFE if is_satisfied else RiskLevel.BLOCKED
            ver_req_str = f" (requires {rt.version})" if rt.version else ""

            if is_satisfied:
                reason = f"Repository requires {rt_name}{ver_req_str}; host has {check.installed_version} installed"
            elif check and check.status == EnvironmentStatus.WRONG_VERSION:
                reason = f"Installed {rt_name} version ({check.installed_version}) does not satisfy required {rt.version}"
                blocking_reasons.append(
                    f"{rt_name.title()} version mismatch: required {rt.version}, but found {check.installed_version} installed."
                )
            else:
                reason = f"Required runtime '{rt_name}' is missing on system PATH"
                blocking_reasons.append(f"{rt_name.title()} runtime is required but not installed on host machine.")

            steps.append(
                PlanStep(
                    id=step_id,
                    description=f"Verify {rt_name.title()} runtime",
                    action_type=ActionType.VERIFY_RUNTIME,
                    risk=risk,
                    reason=reason,
                    is_satisfied=is_satisfied,
                    is_blocked=is_blocked,
                    verification=StepVerification(
                        strategy="exit_code",
                        description=f"{rt_name} --version returns valid output",
                    ),
                )
            )
            runtime_step_ids[rt_name] = step_id

        # ---------------------------------------------------------
        # 2. Package Manager Verification Steps
        # ---------------------------------------------------------
        pm_step_ids: dict[str, str] = {}
        all_pms = list(project_info.package_managers)
        for sp in project_info.subprojects:
            all_pms.extend(sp.package_managers)

        for pm in all_pms:
            pm_name = pm.name.lower()
            if pm_name in pm_step_ids:
                continue
            step_id = f"verify-pm:{pm_name}"

            check = env_checks_map.get(pm_name)
            is_satisfied = check is not None and check.status == EnvironmentStatus.OK
            is_blocked = not is_satisfied

            risk = RiskLevel.SAFE if is_satisfied else RiskLevel.BLOCKED

            depends_on: list[str] = []
            if pm_name in ("pnpm", "yarn", "npm", "bun") and "node" in runtime_step_ids:
                depends_on.append(runtime_step_ids["node"])
            elif pm_name in ("uv", "poetry", "pipenv", "pip") and "python" in runtime_step_ids:
                depends_on.append(runtime_step_ids["python"])

            if is_satisfied:
                reason = f"Project uses {pm_name}; host has {check.installed_version} available"
            else:
                reason = f"Required package manager '{pm_name}' is not installed or available on PATH"
                blocking_reasons.append(
                    f"Package manager '{pm_name}' is required by lockfile/manifest but missing on host."
                )

            steps.append(
                PlanStep(
                    id=step_id,
                    description=f"Verify {pm_name} package manager",
                    action_type=ActionType.VERIFY_PACKAGE_MANAGER,
                    depends_on=depends_on,
                    risk=risk,
                    reason=reason,
                    is_satisfied=is_satisfied,
                    is_blocked=is_blocked,
                    verification=StepVerification(
                        strategy="exit_code",
                        description=f"{pm_name} --version returns 0",
                    ),
                )
            )
            pm_step_ids[pm_name] = step_id

        # ---------------------------------------------------------
        # 3. Environment Variable Configuration Steps
        # ---------------------------------------------------------
        env_step_ids: list[str] = []
        if project_info.environment_variables:
            required_secrets = [
                ev for ev in project_info.environment_variables
                if ev.is_required and (ev.category.value in ("secret", "external_service") or not ev.default_value)
            ]
            local_defaults = [
                ev for ev in project_info.environment_variables
                if ev not in required_secrets
            ]

            if required_secrets:
                step_id = "configure-env:secrets"
                keys_str = ", ".join(ev.name for ev in required_secrets)
                input_reasons.append(
                    f"Required environment credentials/secrets needed: {keys_str}"
                )
                steps.append(
                    PlanStep(
                        id=step_id,
                        description="Provide required environment secrets",
                        action_type=ActionType.CONFIGURE_ENV,
                        risk=RiskLevel.REQUIRES_CONFIRMATION,
                        reason=f"Repository requires credentials without defaults ({keys_str})",
                        verification=StepVerification(
                            strategy="file_exists",
                            target=".env",
                            description="Verify required variables are set in .env",
                        ),
                    )
                )
                env_step_ids.append(step_id)

            if local_defaults and not required_secrets:
                step_id = "configure-env:template"
                steps.append(
                    PlanStep(
                        id=step_id,
                        description="Create .env from template configuration",
                        action_type=ActionType.CONFIGURE_ENV,
                        risk=RiskLevel.REQUIRES_CONFIRMATION,
                        reason="Prepare local environment variables from template (.env.example)",
                        verification=StepVerification(
                            strategy="file_exists",
                            target=".env",
                            description=".env file exists in project directory",
                        ),
                    )
                )
                env_step_ids.append(step_id)

        # ---------------------------------------------------------
        # 4. Infrastructure & Database Services
        # ---------------------------------------------------------
        service_step_ids: list[str] = []
        docker_check = env_checks_map.get("docker")
        compose_check = env_checks_map.get("docker-compose")
        docker_ok = docker_check is not None and docker_check.status == EnvironmentStatus.OK
        compose_ok = compose_check is not None and compose_check.status == EnvironmentStatus.OK

        # 4a. Docker Compose (Preferred if present)
        if project_info.docker.compose_files:
            step_id = "start-service:docker-compose"
            if not docker_ok or not compose_ok:
                detail = docker_check.details if docker_check else "Docker CLI or daemon is unavailable"
                blocking_reasons.append(f"Docker infrastructure services are required, but Docker is non-operational: {detail}")
                steps.append(
                    PlanStep(
                        id=step_id,
                        description="Start Docker Compose services",
                        action_type=ActionType.START_SERVICE,
                        command=["docker", "compose", "up", "-d"],
                        risk=RiskLevel.BLOCKED,
                        is_blocked=True,
                        reason=f"Docker Compose file '{project_info.docker.compose_files[0]}' detected, but Docker is unavailable",
                    )
                )
            else:
                steps.append(
                    PlanStep(
                        id=step_id,
                        description="Start Docker Compose infrastructure services",
                        action_type=ActionType.START_SERVICE,
                        command=["docker", "compose", "up", "-d"],
                        depends_on=env_step_ids,
                        risk=RiskLevel.REQUIRES_CONFIRMATION,
                        reason=f"Start database/cache containers defined in {project_info.docker.compose_files[0]}",
                        verification=StepVerification(
                            strategy="port_reachable",
                            description="Container ports become reachable",
                        ),
                        rollback=StepRollback(
                            strategy="stop_container",
                            description="docker compose down",
                        ),
                    )
                )
            service_step_ids.append(step_id)

        # 4b. Standalone Database / Cache Services (When no Compose file is present)
        else:
            db_names = {db.name.lower() for db in project_info.databases}
            svc_names = {svc.name.lower() for svc in project_info.services}

            # PostgreSQL
            if "postgresql" in db_names or "postgres" in db_names:
                step_id = "start-service:postgres"
                sanitized_name = "".join(c if c.isalnum() or c == "_" else "_" for c in project_info.name).strip("_").lower() or "app"
                container_name = f"runrepo-{sanitized_name}-postgres"
                if not docker_ok:
                    blocking_reasons.append("PostgreSQL database is required by repository, but Docker is not running")
                    steps.append(
                        PlanStep(
                            id=step_id,
                            description="Start PostgreSQL Docker container",
                            action_type=ActionType.START_SERVICE,
                            command=["docker", "run", "-d", "--name", container_name],
                            risk=RiskLevel.BLOCKED,
                            is_blocked=True,
                            reason="PostgreSQL required by schema/manifest, but Docker is unavailable",
                        )
                    )
                else:
                    from runrepo.services.ports import find_available_port
                    pg_port = find_available_port(5432)
                    db_name = f"{sanitized_name}_dev"

                    steps.append(
                        PlanStep(
                            id=step_id,
                            description=f"Start PostgreSQL database container (port {pg_port})",
                            action_type=ActionType.START_SERVICE,
                            command=[
                                "docker", "run", "-d",
                                "--name", container_name,
                                "-p", f"{pg_port}:5432",
                                "-e", f"POSTGRES_DB={db_name}",
                                "-e", "POSTGRES_USER=postgres",
                                "-e", "POSTGRES_PASSWORD=postgres",
                                "postgres:16-alpine",
                            ],
                            depends_on=env_step_ids,
                            risk=RiskLevel.REQUIRES_CONFIRMATION,
                            reason="PostgreSQL required by repository schema/configuration",
                            verification=StepVerification(
                                strategy="port_reachable",
                                target=str(pg_port),
                                description=f"PostgreSQL port {pg_port} reachable",
                            ),
                            rollback=StepRollback(
                                strategy="stop_container",
                                description=f"docker rm -f {container_name}",
                            ),
                        )
                    )
                service_step_ids.append(step_id)

            # Redis
            if "redis" in db_names or "redis" in svc_names:
                step_id = "start-service:redis"
                sanitized_name = "".join(c if c.isalnum() or c == "_" else "_" for c in project_info.name).strip("_").lower() or "app"
                container_name = f"runrepo-{sanitized_name}-redis"
                if not docker_ok:
                    blocking_reasons.append("Redis cache/queue is required by repository, but Docker is not running")
                    steps.append(
                        PlanStep(
                            id=step_id,
                            description="Start Redis Docker container",
                            action_type=ActionType.START_SERVICE,
                            command=["docker", "run", "-d", "--name", container_name],
                            risk=RiskLevel.BLOCKED,
                            is_blocked=True,
                            reason="Redis required by repository, but Docker is unavailable",
                        )
                    )
                else:
                    from runrepo.services.ports import find_available_port
                    redis_port = find_available_port(6379)
                    sanitized_name = "".join(c if c.isalnum() or c == "_" else "_" for c in project_info.name).lower()
                    container_name = f"runrepo-{sanitized_name}-redis"

                    steps.append(
                        PlanStep(
                            id=step_id,
                            description=f"Start Redis cache container (port {redis_port})",
                            action_type=ActionType.START_SERVICE,
                            command=[
                                "docker", "run", "-d",
                                "--name", container_name,
                                "-p", f"{redis_port}:6379",
                                "redis:7-alpine",
                            ],
                            depends_on=env_step_ids,
                            risk=RiskLevel.REQUIRES_CONFIRMATION,
                            reason="Redis required by repository",
                            verification=StepVerification(
                                strategy="port_reachable",
                                target=str(redis_port),
                                description=f"Redis port {redis_port} reachable",
                            ),
                            rollback=StepRollback(
                                strategy="stop_container",
                                description=f"docker rm -f {container_name}",
                            ),
                        )
                    )
                service_step_ids.append(step_id)

        # ---------------------------------------------------------
        # 5. Scoped Dependencies, Migrations & Startup
        # ---------------------------------------------------------
        root_deps_step_id: str | None = None
        if project_info.subprojects and project_info.package_managers:
            root_pm = project_info.package_managers[0].name.lower()
            root_install_cmd: list[str] | None = None
            if root_pm == "pnpm":
                root_install_cmd = ["pnpm", "install"]
            elif root_pm == "yarn":
                root_install_cmd = ["yarn", "install"]
            elif root_pm == "npm":
                root_install_cmd = ["npm", "install"]
            elif root_pm == "uv":
                root_install_cmd = ["uv", "sync"]
            elif root_pm == "poetry":
                root_install_cmd = ["poetry", "install"]
            elif root_pm == "pip":
                pip_check = env_checks_map.get("pip")
                use_uv_pip = (pip_check and "uv" in (pip_check.installed_version or "").lower()) or ("uv" in env_checks_map and env_checks_map["uv"].status.value == "OK")
                if use_uv_pip:
                    base_dir = Path(project_info.path)
                    py_req = next((rt.version for rt in project_info.runtimes if rt.name.lower() == "python"), None)
                    root_venv_info = inspect_virtual_env(base_dir, required_version=py_req)
                    if root_venv_info.status == VirtualEnvStatus.NOT_FOUND:
                        root_venv_step_id = "create-venv"
                        steps.append(
                            PlanStep(
                                id=root_venv_step_id,
                                description="Create root virtual environment",
                                action_type=ActionType.INSTALL_DEPENDENCIES,
                                command=["uv", "venv"],
                                cwd=None,
                                depends_on=list(root_prereqs),
                                risk=RiskLevel.SAFE,
                                reason="Create isolated Python virtual environment",
                                verification=StepVerification(
                                    strategy="exit_code",
                                    description="uv venv returns 0",
                                ),
                            )
                        )
                        root_prereqs.append(root_venv_step_id)
                    elif root_venv_info.status in (VirtualEnvStatus.BROKEN, VirtualEnvStatus.WRONG_VERSION):
                        root_replace_step_id = "replace-venv"
                        action_desc = (
                            f"Replace incompatible virtual environment ({root_venv_info.details})"
                            if root_venv_info.status == VirtualEnvStatus.WRONG_VERSION
                            else f"Replace broken virtual environment ({root_venv_info.details})"
                        )
                        steps.append(
                            PlanStep(
                                id=root_replace_step_id,
                                description="Replace root virtual environment",
                                action_type=ActionType.INSTALL_DEPENDENCIES,
                                command=["uv", "venv", "--clear"],
                                cwd=None,
                                depends_on=list(root_prereqs),
                                risk=RiskLevel.REQUIRES_CONFIRMATION,
                                reason=f"{action_desc} using uv venv --clear",
                                verification=StepVerification(
                                    strategy="exit_code",
                                    description="uv venv --clear returns 0",
                                ),
                            )
                        )
                        root_prereqs.append(root_replace_step_id)
                    if (base_dir / "requirements.txt").exists():
                        root_install_cmd = ["uv", "pip", "install", "-r", "requirements.txt"]
                    elif (base_dir / "pyproject.toml").exists() or (base_dir / "setup.py").exists():
                        root_install_cmd = ["uv", "pip", "install", "-e", "."]
                    else:
                        root_install_cmd = ["uv", "pip", "install", "-r", "requirements.txt"]
                else:
                    if (base_dir / "requirements.txt").exists():
                        root_install_cmd = ["pip", "install", "-r", "requirements.txt"]
                    elif (base_dir / "pyproject.toml").exists() or (base_dir / "setup.py").exists():
                        root_install_cmd = ["pip", "install", "-e", "."]
                    else:
                        root_install_cmd = ["pip", "install", "-r", "requirements.txt"]

            if root_install_cmd:
                root_deps_step_id = "install-deps"
                root_prereqs = []
                if root_pm in pm_step_ids:
                    root_prereqs.append(pm_step_ids[root_pm])
                for rt in project_info.runtimes:
                    if rt.name.lower() in runtime_step_ids and runtime_step_ids[rt.name.lower()] not in root_prereqs:
                        root_prereqs.append(runtime_step_ids[rt.name.lower()])

                steps.append(
                    PlanStep(
                        id=root_deps_step_id,
                        description="Install root project dependencies",
                        action_type=ActionType.INSTALL_DEPENDENCIES,
                        command=root_install_cmd,
                        cwd=None,
                        depends_on=root_prereqs,
                        risk=RiskLevel.REQUIRES_CONFIRMATION,
                        reason=f"Install workspace dependencies using {'uv pip' if use_uv_pip else root_pm}",
                        verification=StepVerification(
                            strategy="exit_code",
                            description=f"{' '.join(root_install_cmd)} returns 0",
                        ),
                    )
                )

        scopes: list[tuple[str, str | None, list, list, list, list]] = []
        if project_info.subprojects:
            for sp in project_info.subprojects:
                scopes.append((sp.name, sp.path, sp.runtimes, sp.package_managers, sp.frameworks, sp.scripts))
        else:
            scopes.append(("root", None, project_info.runtimes, project_info.package_managers, project_info.frameworks, project_info.scripts))

        for scope_name, scope_path, sc_rts, sc_pms, sc_fws, sc_scripts in scopes:
            scope_prefix = f":{scope_name}" if scope_name != "root" else ""

            # 5a. Dependency Installation
            install_cmd: list[str] | None = None
            install_pm_name: str | None = None
            deps_prereqs: list[str] = []

            if sc_pms:
                primary_pm = sc_pms[0].name.lower()
                install_pm_name = primary_pm
                if primary_pm == "pnpm":
                    install_cmd = ["pnpm", "install"]
                elif primary_pm == "yarn":
                    install_cmd = ["yarn", "install"]
                elif primary_pm == "npm":
                    install_cmd = ["npm", "install"]
                elif primary_pm == "uv":
                    install_cmd = ["uv", "sync"]
                elif primary_pm == "poetry":
                    install_cmd = ["poetry", "install"]
                elif primary_pm == "pip":
                    target_dir = Path(project_info.path) / (scope_path or "")
                    pip_check = env_checks_map.get("pip")
                    use_uv_pip = (pip_check and "uv" in (pip_check.installed_version or "").lower()) or ("uv" in env_checks_map and env_checks_map["uv"].status.value == "OK")
                    if use_uv_pip:
                        py_req = next((rt.version for rt in sc_rts if rt.name.lower() == "python"), None)
                        venv_info = inspect_virtual_env(target_dir, required_version=py_req)
                        if venv_info.status == VirtualEnvStatus.NOT_FOUND:
                            venv_step_id = f"create-venv{scope_prefix}"
                            steps.append(
                                PlanStep(
                                    id=venv_step_id,
                                    description=f"Create virtual environment for {scope_name}" if scope_name != "root" else "Create virtual environment",
                                    action_type=ActionType.INSTALL_DEPENDENCIES,
                                    command=["uv", "venv"],
                                    cwd=scope_path,
                                    depends_on=list(deps_prereqs),
                                    risk=RiskLevel.SAFE,
                                    reason="Create isolated Python virtual environment",
                                    verification=StepVerification(
                                        strategy="exit_code",
                                        description="uv venv returns 0",
                                    ),
                                )
                            )
                            deps_prereqs.append(venv_step_id)
                        elif venv_info.status in (VirtualEnvStatus.BROKEN, VirtualEnvStatus.WRONG_VERSION):
                            replace_step_id = f"replace-venv{scope_prefix}"
                            action_desc = (
                                f"Replace incompatible virtual environment ({venv_info.details})"
                                if venv_info.status == VirtualEnvStatus.WRONG_VERSION
                                else f"Replace broken virtual environment ({venv_info.details})"
                            )
                            steps.append(
                                PlanStep(
                                    id=replace_step_id,
                                    description=f"Replace virtual environment for {scope_name}" if scope_name != "root" else "Replace virtual environment",
                                    action_type=ActionType.INSTALL_DEPENDENCIES,
                                    command=["uv", "venv", "--clear"],
                                    cwd=scope_path,
                                    depends_on=list(deps_prereqs),
                                    risk=RiskLevel.REQUIRES_CONFIRMATION,
                                    reason=f"{action_desc} using uv venv --clear",
                                    verification=StepVerification(
                                        strategy="exit_code",
                                        description="uv venv --clear returns 0",
                                    ),
                                )
                            )
                            deps_prereqs.append(replace_step_id)

                        if (target_dir / "requirements.txt").exists():
                            install_cmd = ["uv", "pip", "install", "-r", "requirements.txt"]
                        elif (target_dir / "pyproject.toml").exists() or (target_dir / "setup.py").exists() or (target_dir / "setup.cfg").exists():
                            install_cmd = ["uv", "pip", "install", "-e", "."]
                        else:
                            install_cmd = ["uv", "pip", "install", "-r", "requirements.txt"]
                        install_pm_name = "uv pip"
                    else:
                        if (target_dir / "requirements.txt").exists():
                            install_cmd = ["pip", "install", "-r", "requirements.txt"]
                        elif (target_dir / "pyproject.toml").exists() or (target_dir / "setup.py").exists() or (target_dir / "setup.cfg").exists():
                            install_cmd = ["pip", "install", "-e", "."]
                        else:
                            install_cmd = ["pip", "install", "-r", "requirements.txt"]

                if primary_pm in pm_step_ids:
                    deps_prereqs.append(pm_step_ids[primary_pm])

            for rt in sc_rts:
                if rt.name.lower() in runtime_step_ids and runtime_step_ids[rt.name.lower()] not in deps_prereqs:
                    deps_prereqs.append(runtime_step_ids[rt.name.lower()])

            deps_step_id = f"install-deps{scope_prefix}"
            if install_cmd:
                deps_reason = f"Install packages using {install_pm_name or 'detected package manager'}"
                if sc_pms and sc_pms[0].name.lower() == "pip" and use_uv_pip:
                    target_dir = Path(project_info.path) / (scope_path or "")
                    py_req = next((rt.version for rt in sc_rts if rt.name.lower() == "python"), None)
                    v_info = inspect_virtual_env(target_dir, required_version=py_req)
                    if v_info.status == VirtualEnvStatus.VALID:
                        deps_reason = f"Install packages into existing virtual environment using uv pip (reusing valid environment: {v_info.details})"
                    elif v_info.status in (VirtualEnvStatus.BROKEN, VirtualEnvStatus.WRONG_VERSION):
                        deps_reason = "Install packages into replaced virtual environment using uv pip"

                steps.append(
                    PlanStep(
                        id=deps_step_id,
                        description=f"Install dependencies for {scope_name}" if scope_name != "root" else "Install project dependencies",
                        action_type=ActionType.INSTALL_DEPENDENCIES,
                        command=install_cmd,
                        cwd=scope_path,
                        depends_on=deps_prereqs,
                        risk=RiskLevel.REQUIRES_CONFIRMATION,
                        reason=deps_reason,
                        verification=StepVerification(
                            strategy="exit_code",
                            description=f"{' '.join(install_cmd)} returns 0",
                        ),
                        rollback=StepRollback(
                            strategy="remove_directory",
                            description=f"Remove installed packages directory in {scope_path or '.'}",
                        ),
                    )
                )

            # 5b. Prisma Client Generation
            has_prisma = any(db.orm == "prisma" for db in project_info.databases)
            prisma_step_id = None
            if has_prisma and any(rt.name == "node" for rt in sc_rts):
                prisma_step_id = f"generate-client:prisma{scope_prefix}"
                prereq_deps = [deps_step_id] if install_cmd else ([root_deps_step_id] if root_deps_step_id else [])
                steps.append(
                    PlanStep(
                        id=prisma_step_id,
                        description=f"Generate Prisma Client for {scope_name}",
                        action_type=ActionType.GENERATE_CLIENT,
                        command=["npx", "prisma", "generate"],
                        cwd=scope_path,
                        depends_on=prereq_deps,
                        risk=RiskLevel.REQUIRES_CONFIRMATION,
                        reason="Prisma schema requires client artifact generation",
                        verification=StepVerification(
                            strategy="exit_code",
                            description="npx prisma generate returns 0",
                        ),
                    )
                )

            # 5c. Database Migrations (e.g. Alembic)
            has_alembic = any(db.orm == "alembic" for db in project_info.databases)
            migration_step_id = None
            if has_alembic and any(rt.name == "python" for rt in sc_rts):
                migration_step_id = f"run-migration:alembic{scope_prefix}"
                prereq_deps = [deps_step_id] if install_cmd else ([root_deps_step_id] if root_deps_step_id else [])
                mig_prereqs = prereq_deps + service_step_ids
                steps.append(
                    PlanStep(
                        id=migration_step_id,
                        description=f"Run Alembic database migrations for {scope_name}",
                        action_type=ActionType.RUN_DATABASE_MIGRATION,
                        command=["alembic", "upgrade", "head"],
                        cwd=scope_path,
                        depends_on=mig_prereqs,
                        risk=RiskLevel.REQUIRES_CONFIRMATION,
                        reason="Apply pending database schema migrations",
                        verification=StepVerification(
                            strategy="exit_code",
                            description="alembic upgrade head returns 0",
                        ),
                    )
                )

            # 5d. Application Startup Command
            start_cmd_tokens: list[str] | None = None
            candidate_list: list[str] = []
            script_names = [s.name.lower() for s in sc_scripts]

            # Node.js startup resolution
            if any(rt.name == "node" for rt in sc_rts):
                pm_bin = install_pm_name or "npm"
                for cand in ("dev", "start", "serve"):
                    if cand in script_names:
                        candidate_list.append(f"{pm_bin} run {cand}" if pm_bin != "npm" or cand != "start" else "npm start")

                if "dev" in script_names:
                    start_cmd_tokens = [pm_bin, "run", "dev"] if pm_bin != "npm" else ["npm", "run", "dev"]
                elif "start" in script_names:
                    start_cmd_tokens = [pm_bin, "start"]
                elif "serve" in script_names:
                    start_cmd_tokens = [pm_bin, "run", "serve"]

            # Python startup resolution
            elif any(rt.name == "python" for rt in sc_rts):
                fw_names = [fw.name.lower() for fw in sc_fws]
                script_dict = {s.name.lower(): s.command for s in sc_scripts}

                for cand in ("dev", "start", "run", "serve"):
                    if cand in script_dict:
                        candidate_list.append(script_dict[cand])

                if "dev" in script_dict:
                    start_cmd_tokens = script_dict["dev"].split()
                elif "start" in script_dict:
                    start_cmd_tokens = script_dict["start"].split()
                elif "run" in script_dict:
                    start_cmd_tokens = script_dict["run"].split()
                elif "fastapi" in fw_names:
                    start_cmd_tokens = ["fastapi", "dev", "main.py"]
                    candidate_list.append("fastapi dev main.py")
                elif "django" in fw_names:
                    start_cmd_tokens = ["python", "manage.py", "runserver"]
                    candidate_list.append("python manage.py runserver")
                elif "flask" in fw_names:
                    start_cmd_tokens = ["flask", "run"]
                    candidate_list.append("flask run")
                elif "streamlit" in fw_names:
                    start_cmd_tokens = ["streamlit", "run", "app.py"]
                    candidate_list.append("streamlit run app.py")
                elif project_info.entrypoints:
                    ep = project_info.entrypoints[0]
                    start_cmd_tokens = ["python", ep]

                pip_check = env_checks_map.get("pip")
                use_uv_wrapper = (pip_check and "uv" in (pip_check.installed_version or "").lower()) or ("uv" in env_checks_map and env_checks_map["uv"].status.value == "OK") or any(pm.name.lower() == "uv" for pm in sc_pms)
                pip_check = env_checks_map.get("pip")
                use_uv_wrapper = (pip_check and "uv" in (pip_check.installed_version or "").lower()) or ("uv" in env_checks_map and env_checks_map["uv"].status.value == "OK") or any(pm.name.lower() == "uv" for pm in sc_pms)
                if start_cmd_tokens and use_uv_wrapper and start_cmd_tokens[0] not in ("uv", "poetry", "pipenv", "conda"):
                    start_cmd_tokens = ["uv", "run"] + start_cmd_tokens

            # Check for config startup command override
            if config and hasattr(config, "startup") and config.startup and config.startup.command:
                override_cmd = config.startup.command
                if isinstance(override_cmd, str):
                    start_cmd_tokens = override_cmd.split()
                else:
                    start_cmd_tokens = list(override_cmd)
                candidate_list = [" ".join(start_cmd_tokens)]

            if len(candidate_list) > 1:
                warnings.append(
                    f"Multiple startup commands detected in {scope_name} ({', '.join(candidate_list)}). Defaulting to '{' '.join(start_cmd_tokens or [])}' as primary."
                )
                input_reasons.append(
                    f"Multiple development commands available for {scope_name}: {', '.join(candidate_list)}"
                )

            start_step_id = f"start-app{scope_prefix}"
            prereq_deps = [deps_step_id] if install_cmd else ([root_deps_step_id] if root_deps_step_id else [])
            app_prereqs = prereq_deps + service_step_ids
            if prisma_step_id:
                app_prereqs.append(prisma_step_id)
            if migration_step_id:
                app_prereqs.append(migration_step_id)

            # Determine appropriate target URL and verification strategy based on framework / runtime
            fw_names_lower = [fw.name.lower() for fw in sc_fws]
            has_web_framework = any(
                fw.category in (FrameworkCategory.FULLSTACK, FrameworkCategory.WEB_BACKEND, FrameworkCategory.WEB_FRONTEND)
                for fw in sc_fws
            )
            has_node = any(rt.name == "node" for rt in sc_rts)
            has_go = any(rt.name == "go" for rt in sc_rts)
            is_web_project = (
                has_web_framework
                or project_info.project_type in (ProjectType.WEB_APPLICATION, ProjectType.API_SERVICE)
                or (has_node and any(s.name.lower() in ("dev", "start", "serve") for s in sc_scripts))
            )

            if "flask" in fw_names_lower:
                target_url = "http://127.0.0.1:5000"
                verify_strategy = "http_health_check"
            elif "fastapi" in fw_names_lower or "django" in fw_names_lower:
                target_url = "http://127.0.0.1:8000"
                verify_strategy = "http_health_check"
            elif "vite" in fw_names_lower:
                target_url = "http://127.0.0.1:5173"
                verify_strategy = "http_health_check"
            elif has_go:
                target_url = "http://127.0.0.1:8080"
                verify_strategy = "http_health_check"
            elif has_node and is_web_project:
                target_url = "http://127.0.0.1:3000"
                verify_strategy = "http_health_check"
            elif is_web_project:
                target_url = "http://127.0.0.1:8000"
                verify_strategy = "http_health_check"
            else:
                target_url = None
                verify_strategy = "process_liveness"

            if start_cmd_tokens:
                steps.append(
                    PlanStep(
                        id=start_step_id,
                        description=f"Start {scope_name} application" if scope_name != "root" else "Start application",
                        action_type=ActionType.START_APPLICATION,
                        command=start_cmd_tokens,
                        cwd=scope_path,
                        depends_on=app_prereqs,
                        risk=RiskLevel.REQUIRES_CONFIRMATION,
                        reason=f"Launch application via {' '.join(start_cmd_tokens)}",
                        candidate_commands=candidate_list,
                        verification=StepVerification(
                            strategy=verify_strategy,
                            target=target_url if verify_strategy == "http_health_check" else start_step_id,
                            description="Application HTTP port becomes responsive" if verify_strategy == "http_health_check" else "Application process started successfully",
                        ),
                        rollback=StepRollback(
                            strategy="stop_process",
                            description="Terminate application development process",
                        ),
                    )
                )

                # 5e. Application Verification Step
                verify_step_id = f"verify-app{scope_prefix}"
                steps.append(
                    PlanStep(
                        id=verify_step_id,
                        description=f"Verify {scope_name} operational health" if scope_name != "root" else "Verify application operational health",
                        action_type=ActionType.VERIFY_APPLICATION,
                        depends_on=[start_step_id],
                        risk=RiskLevel.SAFE,
                        reason="Confirm application is running and accessible",
                        verification=StepVerification(
                            strategy=verify_strategy,
                            target=target_url if verify_strategy == "http_health_check" else start_step_id,
                            description="HTTP health endpoint returns HTTP 200 OK" if verify_strategy == "http_health_check" else "Application background process remains active and healthy",
                        ),
                    )
                )

        # ---------------------------------------------------------
        # 6. Graph Compilation & Status Determination
        # ---------------------------------------------------------
        graph = PlanGraph()
        graph.add_steps(steps)
        ordered_steps = graph.topological_sort()

        # Severity precedence: BLOCKED > NEEDS_INPUT > NEEDS_CONFIRMATION > READY
        if blocking_reasons or any(s.is_blocked for s in ordered_steps):
            status = PlanStatus.BLOCKED
        elif input_reasons:
            status = PlanStatus.NEEDS_INPUT
        elif any(s.risk == RiskLevel.REQUIRES_CONFIRMATION for s in ordered_steps):
            status = PlanStatus.NEEDS_CONFIRMATION
        else:
            status = PlanStatus.READY

        return ExecutionPlan(
            repository_path=str(project_info.path),
            project_info=project_info,
            environment_state=env_state,
            status=status,
            steps=ordered_steps,
            warnings=warnings,
            blocking_reasons=blocking_reasons,
            input_reasons=input_reasons,
        )
