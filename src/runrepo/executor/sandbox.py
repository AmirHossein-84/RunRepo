"""Sandboxing and isolated process execution policy and executor."""

import os
from pathlib import Path
from typing import Sequence
from pydantic import BaseModel, Field
from runrepo.executor.process import ProcessExecutionResult, ProcessExecutor, SystemProcessExecutor


class SandboxPolicy(BaseModel):
    """Execution sandbox boundaries for isolating subprocesses and protecting host systems."""

    allowed_working_dir: Path | None = Field(
        default=None,
        description="Path that subprocess working directory must reside within",
    )
    timeout_seconds: float = Field(
        default=120.0,
        description="Maximum execution time before forced termination",
    )
    isolate_environment: bool = Field(
        default=True,
        description="Whether to strip host environment and only provide a clean safe subset",
    )
    allowed_env_vars: list[str] = Field(
        default_factory=lambda: [
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "HOME",
            "USERPROFILE",
            "LANG",
            "LC_ALL",
            "TERM",
            "NODE_ENV",
            "PYTHONPATH",
            "VIRTUAL_ENV",
        ],
        description="Host environment variable names permitted to pass through to subprocesses",
    )
    custom_env: dict[str, str] = Field(
        default_factory=dict,
        description="Explicit project environment variables injected into the sandbox",
    )


class SandboxedProcessExecutor(ProcessExecutor):
    """Executes subprocesses under strict isolation and timeout boundaries."""

    def __init__(
        self,
        policy: SandboxPolicy | None = None,
        underlying_executor: ProcessExecutor | None = None,
    ) -> None:
        self.policy = policy or SandboxPolicy()
        self.underlying = underlying_executor or SystemProcessExecutor()

    def execute(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout_s: float | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessExecutionResult:
        """Execute a command within sanitized environment and directory boundaries."""
        resolved_cwd = Path(cwd).resolve() if cwd else Path.cwd().resolve()

        # Enforce working directory restriction if configured
        if self.policy.allowed_working_dir:
            allowed_root = self.policy.allowed_working_dir.resolve()
            if resolved_cwd != allowed_root and allowed_root not in resolved_cwd.parents:
                return ProcessExecutionResult(
                    exit_code=1,
                    stdout="",
                    stderr=f"Sandbox Violation: Working directory '{resolved_cwd}' outside allowed sandbox '{allowed_root}'.",
                    duration_ms=0.0,
                )

        # Build sanitized environment
        sanitized_env: dict[str, str] = {}
        if self.policy.isolate_environment:
            for key in self.policy.allowed_env_vars:
                if key in os.environ:
                    sanitized_env[key] = os.environ[key]
        else:
            sanitized_env.update(os.environ)

        # Merge custom sandbox env
        sanitized_env.update(self.policy.custom_env)

        # Merge caller env if provided
        if env:
            sanitized_env.update(env)

        effective_timeout = timeout_s or self.policy.timeout_seconds
        return self.underlying.execute(
            command=command,
            cwd=resolved_cwd,
            timeout_s=effective_timeout,
            env=sanitized_env,
        )

    def start_background(
        self,
        command: list[str],
        cwd: Path | None = None,
        log_file: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> int:
        """Run a background process with sanitized environment."""
        resolved_cwd = Path(cwd).resolve() if cwd else Path.cwd().resolve()

        sanitized_env: dict[str, str] = {}
        if self.policy.isolate_environment:
            for key in self.policy.allowed_env_vars:
                if key in os.environ:
                    sanitized_env[key] = os.environ[key]
        else:
            sanitized_env.update(os.environ)

        sanitized_env.update(self.policy.custom_env)
        if env:
            sanitized_env.update(env)

        return self.underlying.start_background(
            command=command,
            cwd=resolved_cwd,
            log_file=log_file,
            env=sanitized_env,
        )
