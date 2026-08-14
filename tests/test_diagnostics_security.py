"""Unit tests ensuring diagnostics never leak secrets in excerpts or suggestions."""

from runrepo.diagnostics.diagnostics import DiagnosticsEngine
from runrepo.executor.models import ExecutionResult, ExecutionStatus, StepExecutionResult


def test_sanitize_log_excerpt_redacts_keys_and_passwords():
    raw_log = """
    Starting service...
    POSTGRES_PASSWORD=super_secret_password_12345
    API_KEY=sk-proj-9876543210abcdef
    Connecting to database with JWT_SECRET=jwt_super_token
    Error: connection refused
    """

    sanitized = DiagnosticsEngine.sanitize_log_excerpt(raw_log)
    assert sanitized is not None
    assert "super_secret_password_12345" not in sanitized
    assert "9876543210abcdef" not in sanitized
    assert "jwt_super_token" not in sanitized
    assert "******" in sanitized


def test_diagnose_execution_stores_pre_redacted_excerpts():
    engine = DiagnosticsEngine()
    exec_result = ExecutionResult(
        plan_id="sec-plan",
        repository_path="/repo",
        status=ExecutionStatus.FAILED,
        total_duration_ms=20.0,
        steps=[
            StepExecutionResult(
                step_id="step-1",
                status=ExecutionStatus.FAILED,
                exit_code=1,
                stderr="Fatal error with DATABASE_PASSWORD=my_db_secret_key listen EADDRINUSE: address already in use :::5432",
            )
        ],
    )

    diags = engine.diagnose_execution(exec_result)
    assert len(diags) == 1
    assert "my_db_secret_key" not in (diags[0].stderr_excerpt or "")
    assert "******" in (diags[0].stderr_excerpt or "")
