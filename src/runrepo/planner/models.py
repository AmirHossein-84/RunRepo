"""Domain models for RunRepo Execution Planning, Step Actions, and Risk Classification."""

from enum import StrEnum
from pydantic import BaseModel, Field

from runrepo.environment.models import EnvironmentState
from runrepo.models import ProjectInfo


class RiskLevel(StrEnum):
    """Safety and risk classification for plan steps."""

    SAFE = "SAFE"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    DANGEROUS = "DANGEROUS"
    BLOCKED = "BLOCKED"


class ActionType(StrEnum):
    """Categorized action types represented within an execution plan."""

    VERIFY_RUNTIME = "VERIFY_RUNTIME"
    VERIFY_PACKAGE_MANAGER = "VERIFY_PACKAGE_MANAGER"
    CONFIGURE_ENV = "CONFIGURE_ENV"
    START_SERVICE = "START_SERVICE"
    INSTALL_DEPENDENCIES = "INSTALL_DEPENDENCIES"
    GENERATE_CLIENT = "GENERATE_CLIENT"
    RUN_DATABASE_MIGRATION = "RUN_DATABASE_MIGRATION"
    START_APPLICATION = "START_APPLICATION"
    VERIFY_APPLICATION = "VERIFY_APPLICATION"


class PlanStatus(StrEnum):
    """Overall readiness and execution feasibility status of the plan."""

    READY = "READY"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    NEEDS_INPUT = "NEEDS_INPUT"
    BLOCKED = "BLOCKED"


class StepVerification(BaseModel):
    """Structured verification metadata describing how step success will be validated."""

    strategy: str = Field(description="Verification strategy: 'exit_code', 'file_exists', 'port_reachable', 'http_health_check'")
    target: str | None = Field(default=None, description="Target path, port, or URL to inspect")
    description: str = Field(description="Human-readable verification description")


class StepRollback(BaseModel):
    """Structured rollback metadata describing safe compensatory action if step fails."""

    strategy: str = Field(description="Rollback strategy: 'remove_directory', 'stop_container', 'none'")
    description: str = Field(description="Human-readable description of rollback behavior")


class PlanStep(BaseModel):
    """An individual, structured, explainable action step within an ExecutionPlan."""

    id: str = Field(description="Unique deterministic step identifier, e.g. 'verify-runtime:node', 'install-deps:root'")
    description: str = Field(description="Clear human-readable summary of the step")
    action_type: ActionType = Field(description="Categorized action type")
    command: list[str] | None = Field(
        default=None,
        description="Structured tokenized command arguments to execute (if applicable)",
    )
    cwd: str | None = Field(
        default=None,
        description="Relative working directory for subprojects or root",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of prerequisite steps that must complete before this step",
    )
    risk: RiskLevel = Field(
        default=RiskLevel.SAFE,
        description="Risk and safety level of the step",
    )
    reason: str = Field(
        description="Justification for why this step exists, referencing detected facts/evidence",
    )
    candidate_commands: list[str] = Field(
        default_factory=list,
        description="Alternative startup scripts/commands when multiple viable options exist",
    )
    verification: StepVerification | None = Field(
        default=None,
        description="Verification criteria to confirm step success",
    )
    rollback: StepRollback | None = Field(
        default=None,
        description="Rollback strategy if step execution fails",
    )
    is_satisfied: bool = Field(
        default=False,
        description="Whether this step is already satisfied by the host environment",
    )
    is_blocked: bool = Field(
        default=False,
        description="Whether this step is currently blocked by missing tools, bad versions, or unmet prerequisites",
    )


class ExecutionPlan(BaseModel):
    """Ordered, dependency-linked execution plan produced by the Planner."""

    repository_path: str = Field(description="Path to the target repository")
    project_info: ProjectInfo = Field(description="Repository facts from Milestone 1")
    environment_state: EnvironmentState = Field(description="Host environment facts from Milestone 2")
    status: PlanStatus = Field(description="Overall plan status: READY, NEEDS_CONFIRMATION, NEEDS_INPUT, BLOCKED")
    steps: list[PlanStep] = Field(
        default_factory=list,
        description="Topologically sorted list of plan steps",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Planning warnings and notes for the user",
    )
    blocking_reasons: list[str] = Field(
        default_factory=list,
        description="Explanations for why planning cannot proceed (if BLOCKED)",
    )
    input_reasons: list[str] = Field(
        default_factory=list,
        description="Required user inputs or selections (if NEEDS_INPUT)",
    )
