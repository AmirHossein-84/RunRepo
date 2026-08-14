"""Unit tests for MonorepoDetector and MonorepoResolver."""

import json
from runrepo.monorepo.detector import MonorepoDetector
from runrepo.monorepo.models import WorkspaceType
from runrepo.monorepo.resolver import MonorepoResolver


def test_detect_pnpm_workspace(tmp_path):
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'apps/*'\n  - 'packages/*'", encoding="utf-8")
    
    app_dir = tmp_path / "apps" / "web"
    app_dir.mkdir(parents=True)
    (app_dir / "package.json").write_text(
        json.dumps({
            "name": "@myorg/web",
            "scripts": {"dev": "next dev", "build": "next build"},
            "dependencies": {"next": "^14.0.0", "react": "^18.2.0"},
        }),
        encoding="utf-8",
    )

    pkg_dir = tmp_path / "packages" / "ui"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text(
        json.dumps({
            "name": "@myorg/ui",
            "dependencies": {"react": "^18.2.0"},
        }),
        encoding="utf-8",
    )

    detector = MonorepoDetector()
    info = detector.detect(tmp_path)

    assert info.is_monorepo is True
    assert info.workspace_type == WorkspaceType.PNPM
    assert len(info.packages) == 2
    assert len(info.runnable_apps) == 1
    assert info.runnable_apps[0].name == "@myorg/web"

    # Test Resolver
    subprojects = MonorepoResolver.resolve_subprojects(info, root_pm="pnpm")
    assert len(subprojects) == 2
    web_sub = next(s for s in subprojects if s.name == "@myorg/web")
    assert web_sub.path == "apps/web"
    assert any(sc.name == "dev" for sc in web_sub.scripts)


def test_detect_turborepo_workspace(tmp_path):
    (tmp_path / "turbo.json").write_text('{"$schema": "https://turbo.build/schema.json"}', encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name": "root", "workspaces": ["apps/*"]}', encoding="utf-8")
    
    app_dir = tmp_path / "apps" / "api"
    app_dir.mkdir(parents=True)
    (app_dir / "package.json").write_text(
        json.dumps({"name": "api", "scripts": {"dev": "express main.js"}}),
        encoding="utf-8",
    )

    detector = MonorepoDetector()
    info = detector.detect(tmp_path)

    assert info.is_monorepo is True
    assert info.workspace_type == WorkspaceType.TURBOREPO
    assert len(info.packages) == 1


def test_single_repo_is_not_monorepo(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "standalone-app"}', encoding="utf-8")

    detector = MonorepoDetector()
    info = detector.detect(tmp_path)

    assert info.is_monorepo is False
    assert info.workspace_type == WorkspaceType.SINGLE_PROJECT
