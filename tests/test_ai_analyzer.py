"""Unit tests for AIRepositoryAnalyzer resolving ambiguity while preserving deterministic precedence."""

from runrepo.ai.analyzer import AIRepositoryAnalyzer
from runrepo.ai.gemini import GeminiClient
from runrepo.models import (
    Confidence,
    DetectionEvidence,
    PackageManagerInfo,
    ProjectInfo,
    ProjectType,
)


def test_ai_analyzer_enriches_unknown_project(tmp_path):
    (tmp_path / "README.md").write_text(
        "# My Awesome FastAPI Service\nRun with `uvicorn app:main --reload` on port 8000.",
        encoding="utf-8",
    )

    mock_ai_json = """{
      "confidence": 0.85,
      "reasoning_summary": "FastAPI web application from README",
      "detected_project_type": "WEB_APPLICATION",
      "detected_framework": "FastAPI",
      "detected_package_manager": "uv",
      "suggested_startup_command": ["uvicorn", "app:main", "--reload"]
    }"""

    client = GeminiClient(api_key="mock_key", transport=lambda payload: mock_ai_json)
    ai_analyzer = AIRepositoryAnalyzer(client=client)

    initial_project = ProjectInfo(
        path=str(tmp_path),
        name="testapp",
        project_type=ProjectType.UNKNOWN,
    )

    enriched = ai_analyzer.analyze_ambiguity(tmp_path, initial_project)

    assert enriched.project_type == ProjectType.WEB_APPLICATION
    assert len(enriched.frameworks) == 1
    assert enriched.frameworks[0].name == "FastAPI"
    assert len(enriched.package_managers) == 1
    assert enriched.package_managers[0].name == "uv"
    assert len(enriched.scripts) == 1
    assert enriched.scripts[0].command == "uvicorn app:main --reload"


def test_ai_analyzer_preserves_deterministic_facts_on_conflict(tmp_path):
    (tmp_path / "README.md").write_text("# Project\nInstall with npm install", encoding="utf-8")

    # AI claims package manager is npm
    mock_ai_json = """{
      "confidence": 0.7,
      "reasoning_summary": "npm project",
      "detected_package_manager": "npm"
    }"""

    client = GeminiClient(api_key="mock_key", transport=lambda payload: mock_ai_json)
    ai_analyzer = AIRepositoryAnalyzer(client=client)

    # Deterministic facts proved pnpm from pnpm-lock.yaml
    initial_project = ProjectInfo(
        path=str(tmp_path),
        name="testapp",
        project_type=ProjectType.WEB_APPLICATION,
        package_managers=[PackageManagerInfo(name="pnpm", evidence=[DetectionEvidence(source="pnpm-lock.yaml", confidence=Confidence.HIGH)])],
    )

    enriched = ai_analyzer.analyze_ambiguity(tmp_path, initial_project)

    # Deterministic fact is strictly preserved
    assert len(enriched.package_managers) == 1
    assert enriched.package_managers[0].name == "pnpm"
    # Conflict is recorded in warnings
    assert any("pnpm" in w.message and "npm" in w.message for w in enriched.warnings)
