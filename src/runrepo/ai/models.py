"""Domain models for structured AI analysis, validation, and safe action recommendations."""

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AIActionSuggestion(BaseModel):
    """Structured action suggested by AI, subject to strict RunRepo safety validation."""

    description: str = Field(description="Human-readable explanation of why this action is suggested")
    action_type: str = Field(
        default="EXECUTE_COMMAND",
        description="RunRepo ActionType string representing the action",
    )
    command: list[str] = Field(
        default_factory=list,
        description="Command arguments list (never executed directly by AI)",
    )
    risk_level: str = Field(
        default="REQUIRES_CONFIRMATION",
        description="Risk level string (AI cannot lower this below REQUIRES_CONFIRMATION)",
    )
    justification: str = Field(
        default="",
        description="Evidence or reasoning from repository analysis or logs",
    )
    is_safe: bool = Field(
        default=True,
        description="Whether the suggestion passes deterministic safety checks",
    )


class AIAnalysisResult(BaseModel):
    """Structured response from AI repository/README analysis."""

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.5,
        description="Confidence score (0.0 to 1.0) for the analysis",
    )
    reasoning_summary: str = Field(
        default="",
        description="Summary of AI analysis and reasoning steps",
    )
    detected_project_type: str | None = Field(
        default=None,
        description="Guessed project type (e.g. WEB_APPLICATION, CLI_TOOL, API_SERVICE)",
    )
    detected_framework: str | None = Field(
        default=None,
        description="Guessed framework (e.g. Next.js, FastAPI, Flask, Express, Django)",
    )
    detected_package_manager: str | None = Field(
        default=None,
        description="Guessed package manager (e.g. npm, pnpm, yarn, uv, poetry, pip)",
    )
    detected_services: list[str] = Field(
        default_factory=list,
        description="Services mentioned in README/docs (e.g. postgres, redis)",
    )
    detected_environment_variables: list[str] = Field(
        default_factory=list,
        description="Environment variables mentioned in documentation",
    )
    suggested_startup_command: list[str] = Field(
        default_factory=list,
        description="Suggested development startup command list",
    )
    suggested_actions: list[AIActionSuggestion] = Field(
        default_factory=list,
        description="Ordered sequence of setup and run suggestions",
    )
    unresolved_questions: list[str] = Field(
        default_factory=list,
        description="Ambiguities or missing details that require human clarification",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp",
    )


class AIDiagnosticResult(BaseModel):
    """Structured response from AI failure diagnosis."""

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.5,
        description="Confidence score for the failure diagnosis",
    )
    likely_root_cause: str = Field(
        default="",
        description="Clear explanation of the suspected root cause",
    )
    explanation: str = Field(
        default="",
        description="In-depth explanation connecting logs, environment, and failure mode",
    )
    suggested_fixes: list[AIActionSuggestion] = Field(
        default_factory=list,
        description="List of safe, copyable remediation steps for the developer",
    )
    prevention_advice: str = Field(
        default="",
        description="Guidance on avoiding this issue in future runs",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp",
    )
