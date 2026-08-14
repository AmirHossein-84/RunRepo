"""Handler for infrastructure and background service steps (Docker Compose, PostgreSQL, Redis)."""

from datetime import datetime, timezone
from pathlib import Path
from runrepo.executor.handlers.base import BaseStepHandler
from runrepo.executor.models import ExecutionStatus, StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep
from runrepo.services.compose import ComposeManager
from runrepo.services.docker import DockerManager
from runrepo.services.models import OwnedResource, ResourceType, ServiceType
from runrepo.services.registry import InfrastructureRegistry


class ServiceStepHandler(BaseStepHandler):
    """Handles START_SERVICE steps (Docker Compose, standalone PostgreSQL, and Redis)."""

    def __init__(self, registry: InfrastructureRegistry | None = None) -> None:
        self.registry = registry or InfrastructureRegistry()

    def can_handle(self, step: PlanStep) -> bool:
        return step.action_type == ActionType.START_SERVICE

    def execute(
        self,
        step: PlanStep,
        repo_path: Path,
        executor: ProcessExecutor,
        process_manager: ProcessManager,
        dry_run: bool = False,
    ) -> StepExecutionResult:
        started_at = datetime.now(timezone.utc)
        working_dir = (repo_path / step.cwd).resolve() if step.cwd else repo_path.resolve()

        if dry_run:
            cmd_str = " ".join(step.command) if step.command else "start services"
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.SUCCESS,
                command=step.command,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=started_at,
                duration_ms=0.0,
                stdout=f"[dry-run] Would execute: {cmd_str} in {working_dir}",
                exit_code=0,
                verification_passed=True,
            )

        if not step.command:
            return StepExecutionResult(
                step_id=step.id,
                status=ExecutionStatus.FAILED,
                command=None,
                cwd=step.cwd,
                started_at=started_at,
                finished_at=started_at,
                duration_ms=0.0,
                stderr="No command specified for start service step",
                exit_code=1,
                verification_passed=False,
            )

        # 1. Docker Compose Action
        if "compose" in step.id or (len(step.command) >= 2 and step.command[0] == "docker" and step.command[1] == "compose"):
            res = ComposeManager.up(cwd=working_dir, executor=executor, project_path=str(repo_path), registry=self.registry)
        else:
            # 2. Standalone Docker Run Action (Postgres / Redis / Custom)
            res = executor.execute(step.command, cwd=working_dir)
            if res.exit_code == 0:
                # Extract container name from command if present (--name <name>)
                container_name = None
                if "--name" in step.command:
                    idx = step.command.index("--name")
                    if idx + 1 < len(step.command):
                        container_name = step.command[idx + 1]

                svc_type = ServiceType.CUSTOM
                if "postgres" in step.id:
                    svc_type = ServiceType.POSTGRES
                elif "redis" in step.id:
                    svc_type = ServiceType.REDIS

                if container_name:
                    container_id = res.stdout.strip() or container_name
                    self.registry.register_resource(
                        OwnedResource(
                            resource_type=ResourceType.CONTAINER,
                            id=container_id,
                            name=container_name,
                            service_type=svc_type,
                            project_path=str(repo_path),
                            labels={"runrepo.managed": "true", f"runrepo.service": svc_type.value.lower()},
                        )
                    )
            else:
                # Rollback partially created container on failure
                if "--name" in step.command:
                    idx = step.command.index("--name")
                    if idx + 1 < len(step.command):
                        container_name = step.command[idx + 1]
                        DockerManager.remove_container(container_name, executor, force=True)

        finished_at = datetime.now(timezone.utc)
        status = ExecutionStatus.SUCCESS if res.exit_code == 0 else ExecutionStatus.FAILED

        return StepExecutionResult(
            step_id=step.id,
            status=status,
            command=step.command,
            cwd=step.cwd,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=res.duration_ms,
            stdout=res.stdout,
            stderr=res.stderr,
            exit_code=res.exit_code,
            verification_passed=res.exit_code == 0,
            rollback_available=step.rollback is not None,
        )
