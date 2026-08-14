"""Unit tests for executor domain models and JSON serialization."""

import json
from datetime import datetime, timezone
from runrepo.executor.models import ExecutionResult, ExecutionStatus, StepExecutionResult


def test_step_execution_result_model():
    now = datetime.now(timezone.utc)
    step_res = StepExecutionResult(
        step_id="install-deps",
        status=ExecutionStatus.SUCCESS,
        command=["pnpm", "install"],
        cwd="frontend",
        started_at=now,
        finished_at=now,
        duration_ms=123.45,
        stdout="Packages installed",
        stderr="",
        exit_code=0,
        verification_passed=True,
        verification_details="Exit code 0",
        rollback_available=True,
    )

    assert step_res.step_id == "install-deps"
    assert step_res.status == ExecutionStatus.SUCCESS
    assert step_res.exit_code == 0
    assert step_res.duration_ms == 123.45


def test_execution_result_serialization():
    now = datetime.now(timezone.utc)
    step_res = StepExecutionResult(
        step_id="verify-runtime:node",
        status=ExecutionStatus.SUCCESS,
        started_at=now,
        finished_at=now,
        duration_ms=5.0,
        exit_code=0,
    )

    result = ExecutionResult(
        plan_id="plan_12345",
        repository_path="/repo",
        status=ExecutionStatus.SUCCESS,
        steps=[step_res],
        successful_steps=["verify-runtime:node"],
        failed_steps=[],
        skipped_steps=[],
        started_at=now,
        finished_at=now,
        summary="Successfully executed 1 step(s)",
    )

    json_str = result.model_dump_json()
    data = json.loads(json_str)

    assert data["status"] == "SUCCESS"
    assert data["plan_id"] == "plan_12345"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["step_id"] == "verify-runtime:node"
