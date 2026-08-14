"""Environment verifier confirming required configuration is available across supported sources."""

import os
from pathlib import Path
from runrepo.env.detector import EnvDetector
from runrepo.env.models import EnvEntryType
from runrepo.executor.models import StepExecutionResult
from runrepo.executor.process import ProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.planner.models import ActionType, PlanStep
from runrepo.verification.models import VerificationResult, VerificationStatus, VerificationType
from runrepo.verification.verifiers.base import BaseVerifier


class EnvVerifier(BaseVerifier):
    """Confirms required environment variables are available via .env, process environment, or Compose."""

    def can_verify(self, step: PlanStep) -> bool:
        """Responsible for environment verification strategies or CONFIGURE_ENV without explicit file_exists."""
        if step.verification and step.verification.strategy in ("env_available", "env_exists"):
            return True
        if step.action_type == ActionType.CONFIGURE_ENV and (not step.verification or step.verification.strategy not in ("file_exists", "exit_code")):
            return True
        return False

    def verify(
        self,
        step: PlanStep,
        step_result: StepExecutionResult,
        repo_path: Path | None = None,
        executor: ProcessExecutor | None = None,
        process_manager: ProcessManager | None = None,
        dry_run: bool = False,
    ) -> VerificationResult:
        """Verify that required environment variables are accessible."""
        if dry_run:
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.ENVIRONMENT_CHECK,
                status=VerificationStatus.PASSED,
                passed=True,
                message="[dry-run] Environment verification assumed passed",
            )

        target_dir = repo_path.resolve() if repo_path else Path.cwd().resolve()
        if step.cwd:
            target_dir = (target_dir / step.cwd).resolve()

        env_file_path = target_dir / ".env"
        available_vars: set[str] = set()

        # 1. Variables from .env
        if env_file_path.exists() and env_file_path.is_file():
            env_file = EnvDetector.parse_env_file(env_file_path)
            for entry in env_file.entries:
                if entry.entry_type == EnvEntryType.KEY_VALUE and entry.key and entry.value:
                    available_vars.add(entry.key)

        # 2. Variables from host process environment
        available_vars.update(os.environ.keys())

        # 3. Detect expected requirements
        reqs = EnvDetector.detect_project_requirements(target_dir)
        missing: list[str] = []

        for req in reqs:
            if req.is_required and req.name not in available_vars and not req.default_value:
                missing.append(req.name)

        if missing:
            return VerificationResult(
                step_id=step.id,
                verification_type=VerificationType.ENVIRONMENT_CHECK,
                status=VerificationStatus.FAILED,
                passed=False,
                message=f"Missing required environment variables: {', '.join(missing)}",
                details={
                    "working_dir": str(target_dir),
                    "missing_variables": missing,
                    "available_count": len(available_vars),
                },
            )

        return VerificationResult(
            step_id=step.id,
            verification_type=VerificationType.ENVIRONMENT_CHECK,
            status=VerificationStatus.PASSED,
            passed=True,
            message=f"Environment configuration verified ({len(available_vars)} variable(s) available)",
            details={
                "working_dir": str(target_dir),
                "available_count": len(available_vars),
            },
        )
