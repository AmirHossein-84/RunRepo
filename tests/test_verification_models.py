"""Unit tests for verification domain models and serialization."""

import json
from runrepo.verification.models import (
    VerificationResult,
    VerificationStatus,
    VerificationType,
)


def test_verification_result_model():
    result = VerificationResult(
        step_id="install-deps",
        verification_type=VerificationType.DEPENDENCY_CHECK,
        status=VerificationStatus.PASSED,
        target="node_modules",
        message="node_modules present and populated",
        details={"package_count": 142},
        duration_ms=12.5,
        diagnostic_data={"has_package_json": True},
    )

    assert result.step_id == "install-deps"
    assert result.status == VerificationStatus.PASSED
    assert result.verification_type == VerificationType.DEPENDENCY_CHECK
    assert result.details["package_count"] == 142


def test_verification_result_serialization():
    result = VerificationResult(
        step_id="verify-app",
        verification_type=VerificationType.HTTP_CHECK,
        status=VerificationStatus.FAILED,
        target="http://127.0.0.1:3000",
        message="HTTP health check returned status 500",
        duration_ms=45.0,
        failure_reason="Internal Server Error",
        diagnostic_data={"status_code": 500},
    )

    json_str = result.model_dump_json()
    data = json.loads(json_str)

    assert data["status"] == "FAILED"
    assert data["verification_type"] == "HTTP_CHECK"
    assert data["failure_reason"] == "Internal Server Error"
    assert data["diagnostic_data"]["status_code"] == 500
