"""Deterministic Execution Planner converting ProjectInfo and EnvironmentState into an ordered ExecutionPlan."""

from pathlib import Path

from runrepo.environment.models import EnvironmentCheck, EnvironmentState, EnvironmentStatus
from runrepo.models import ProjectInfo, SubprojectInfo
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

    def plan(self, project_info: ProjectInfo, env_state: EnvironmentState) -> ExecutionPlan:
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
            step_id = f"verify-runtime:{rt_name}"
            if step_id in runtime_step_ids:
                continue

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
            step_id = f"verify-pm:{pm_name}"
            if step_id in pm_step_ids:
                continue

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
        needs_docker = (
            project_info.docker.has_dockerfile
            or bool(project_info.docker.compose_files)
            or bool(project_info.databases)
            or bool(project_info.services)
        )

        if needs_docker and project_info.docker.compose_files:
            docker_check = env_checks_map.get("docker")
            compose_check = env_checks_map.get("docker-compose")

            docker_ok = docker_check is not None and docker_check.status == EnvironmentStatus.OK
            compose_ok = compose_check is not None and compose_check.status == EnvironmentStatus.OK

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

        # ---------------------------------------------------------
        # 5. Scoped Dependencies, Migrations & Startup
        # ---------------------------------------------------------
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
                    install_cmd = ["pip", "install", "-r", "requirements.txt"]

                if primary_pm in pm_step_ids:
                    deps_prereqs.append(pm_step_ids[primary_pm])

            for rt in sc_rts:
                if rt.name.lower() in runtime_step_ids and runtime_step_ids[rt.name.lower()] not in deps_prereqs:
                    deps_prereqs.append(runtime_step_ids[rt.name.lower()])

            deps_step_id = f"install-deps{scope_prefix}"
            if install_cmd:
                steps.append(
                    PlanStep(
                        id=deps_step_id,
                        description=f"Install dependencies for {scope_name}" if scope_name != "root" else "Install project dependencies",
                        action_type=ActionType.INSTALL_DEPENDENCIES,
                        command=install_cmd,
                        cwd=scope_path,
                        depends_on=deps_prereqs,
                        risk=RiskLevel.REQUIRES_CONFIRMATION,
                        reason=f"Install packages using {install_pm_name or 'detected package manager'}",
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
                steps.append(
                    PlanStep(
                        id=prisma_step_id,
                        description=f"Generate Prisma Client for {scope_name}",
                        action_type=ActionType.GENERATE_CLIENT,
                        command=["npx", "prisma", "generate"],
                        cwd=scope_path,
                        depends_on=[deps_step_id] if install_cmd else [],
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
                mig_prereqs = ([deps_step_id] if install_cmd else []) + service_step_ids
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
                # Check candidate scripts
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
                    candidate_list.append(f"python {ep}")

            if len(candidate_list) > 1:
                warnings.append(
                    f"Multiple startup commands detected in {scope_name} ({', '.join(candidate_list)}). Defaulting to '{' '.join(start_cmd_tokens or [])}' as primary."
                )
                input_reasons.append(
                    f"Multiple development commands available for {scope_name}: {', '.join(candidate_list)}"
                )

            start_step_id = f"start-app{scope_prefix}"
            app_prereqs = ([deps_step_id] if install_cmd else []) + service_step_ids
            if prisma_step_id:
                app_prereqs.append(prisma_step_id)
            if migration_step_id:
                app_prereqs.append(migration_step_id)

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
                            strategy="http_health_check",
                            target="http://localhost:3000" if any(rt.name == "node" for rt in sc_rts) else "http://localhost:8000",
                            description="Application HTTP port becomes responsive",
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
                            strategy="http_health_check",
                            description="HTTP health endpoint returns HTTP 200 OK",
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
