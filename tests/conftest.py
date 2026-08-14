"""Pytest fixtures and temporary repository builders for RunRepo test suite."""

from pathlib import Path
import pytest


@pytest.fixture
def create_fixture_repo(tmp_path: Path):
    """Helper factory to create realistic repository folder structures on demand."""

    def _builder(files_and_contents: dict[str, str]) -> Path:
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir(parents=True, exist_ok=True)
        for rel_path, content in files_and_contents.items():
            full_path = repo_dir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
        return repo_dir

    return _builder
