"""Unit tests for repository domain models and serialization."""

import json
from pathlib import Path
from runrepo.repository.models import (
    CloneStatus,
    RepositoryResult,
    RepositorySource,
    RepositoryTarget,
)


def test_repository_target_model():
    target = RepositoryTarget(
        source=RepositorySource.GITHUB_HTTPS,
        raw_input="https://github.com/fastapi/fastapi",
        owner="fastapi",
        name="fastapi",
        branch="master",
        clone_url="https://github.com/fastapi/fastapi.git",
        local_path=Path("/tmp/cache/fastapi_fastapi"),
        status=CloneStatus.CLONED,
    )

    data = json.loads(target.model_dump_json())
    assert data["source"] == "GITHUB_HTTPS"
    assert data["owner"] == "fastapi"
    assert data["name"] == "fastapi"
    assert data["branch"] == "master"
    assert data["status"] == "CLONED"


def test_repository_result_model():
    target = RepositoryTarget(
        source=RepositorySource.LOCAL,
        raw_input="/path/to/repo",
        name="repo",
        local_path=Path("/path/to/repo"),
        status=CloneStatus.NOT_CLONED,
    )
    result = RepositoryResult(
        success=True,
        target=target,
        local_path=Path("/path/to/repo"),
        duration_ms=45.2,
    )

    data = json.loads(result.model_dump_json())
    assert data["success"] is True
    assert data["target"]["source"] == "LOCAL"
    assert "timestamp" in data
