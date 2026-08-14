"""Unit tests for AI domain models and Pydantic serialization."""

import json
from runrepo.ai.models import (
    AIActionSuggestion,
    AIAnalysisResult,
    AIDiagnosticResult,
)


def test_ai_action_suggestion_model():
    action = AIActionSuggestion(
        description="Install dependencies using uv sync",
        action_type="INSTALL_DEPENDENCIES",
        command=["uv", "sync"],
        risk_level="REQUIRES_CONFIRMATION",
        justification="README specifies uv package manager",
        is_safe=True,
    )

    data = json.loads(action.model_dump_json())
    assert data["description"] == "Install dependencies using uv sync"
    assert data["command"] == ["uv", "sync"]
    assert data["risk_level"] == "REQUIRES_CONFIRMATION"
    assert data["is_safe"] is True


def test_ai_analysis_result_model():
    res = AIAnalysisResult(
        confidence=0.85,
        reasoning_summary="Identified FastAPI project from main.py and pyproject.toml",
        detected_project_type="WEB_APPLICATION",
        detected_framework="FastAPI",
        detected_package_manager="uv",
        detected_services=["postgres"],
        detected_environment_variables=["PORT", "DATABASE_URL"],
        suggested_startup_command=["uvicorn", "main:app", "--reload"],
        unresolved_questions=["Is database migration required?"],
    )

    data = json.loads(res.model_dump_json())
    assert data["confidence"] == 0.85
    assert data["detected_framework"] == "FastAPI"
    assert data["detected_services"] == ["postgres"]
    assert "timestamp" in data


def test_ai_diagnostic_result_model():
    diag = AIDiagnosticResult(
        confidence=0.9,
        likely_root_cause="Missing PostgreSQL libpq binaries",
        explanation="psycopg2 failed to compile because libpq-dev is missing on host.",
        suggested_fixes=[
            AIActionSuggestion(
                description="Install psycopg2-binary instead of psycopg2",
                command=["uv", "pip", "install", "psycopg2-binary"],
            )
        ],
        prevention_advice="Prefer psycopg2-binary for local dev environments.",
    )

    data = json.loads(diag.model_dump_json())
    assert data["confidence"] == 0.9
    assert data["likely_root_cause"] == "Missing PostgreSQL libpq binaries"
    assert len(data["suggested_fixes"]) == 1
