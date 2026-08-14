"""Execution domain models capturing execution status, step results, and overall run outcomes."""

from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, Field


class ExecutionStatus(StrEnum):
    """Lifecycle and terminal status for steps and full execution runs."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class StepExecutionResult(BaseModel):
    """Detailed outcome and telemetry of a single executed plan step."""

    step_id: str = Field(description="Unique ID matching the executed PlanStep")
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING, description="Outcome status of the step")
    command: list[str] | None = Field(default=None, description="Command tokens executed")
    cwd: str | None = Field(default=None, description="Working directory relative to repository root")

    started_at: datetime | None = Field(default=None, description="Timestamp when execution began")
    finished_at: datetime | None = Field(default=None, description="Timestamp when execution completed")
    duration_ms: float = Field(default=0.0, description="Duration of step execution in milliseconds")

    stdout: str = Field(default="", description="Captured standard output")
    stderr: str = Field(default="", description="Captured standard error")
    exit_code: int | None = Field(default=None, description="Process return code")

    error: str | None = Field(default=None, description="Error message or exception description")
    verification_passed: bool = Field(default=True, description="Whether post-execution verification succeeded")
    verification_details: str | None = Field(default=None, description="Verification diagnostic message")
    rollback_available: bool = Field(default=False, description="Whether a rollback strategy is defined")


class ExecutionResult(BaseModel):
    """Complete summary and record of an entire execution plan run."""

    plan_id: str = Field(default="", description="Identifier or hash of the executed plan")
    repository_path: str = Field(description="Target repository directory path")
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING, description="Overall execution outcome")

    steps: list[StepExecutionResult] = Field(
        default_factory=list,
        description="Chronological step execution records",
    )

    successful_steps: list[str] = Field(default_factory=list, description="IDs of steps that succeeded")
    failed_steps: list[str] = Field(default_factory=list, description="IDs of steps that failed")
    skipped_steps: list[str] = Field(default_factory=list, description="IDs of downstream skipped steps")

    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Run start time",
    )
    finished_at: datetime | None = Field(default=None, description="Run finish time")
    summary: str = Field(default="", description="Human-readable execution outcome summary")
