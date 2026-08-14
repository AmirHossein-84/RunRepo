"""Unit tests for Diagnostics domain models and serialization."""

import json
from runrepo.diagnostics.models import (
    Diagnostic,
    DiagnosticCategory,
    DiagnosticSeverity,
    SuggestedAction,
)


def test_diagnostic_model_serialization():
    diag = Diagnostic(
        id="diag:test:1",
        severity=DiagnosticSeverity.ERROR,
        category=DiagnosticCategory.NETWORK,
        title="Port 5432 in use",
        explanation="Another process is holding port 5432.",
        affected_step_id="start-service:postgres",
        stdout_excerpt="stdout line",
        stderr_excerpt="stderr: EADDRINUSE",
        exit_code=1,
        suggested_actions=[
            SuggestedAction(
                title="Stop existing process",
                command="netstat -ano",
                description="Find process",
                is_safe_to_copy=True,
            )
        ],
        related_resources=["port:5432"],
    )

    data = json.loads(diag.model_dump_json())
    assert data["id"] == "diag:test:1"
    assert data["severity"] == "ERROR"
    assert data["category"] == "NETWORK"
    assert data["suggested_actions"][0]["command"] == "netstat -ano"
    assert data["related_resources"] == ["port:5432"]
    assert "timestamp" in data
