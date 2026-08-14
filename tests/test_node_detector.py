"""Unit tests for NodeDetector."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detectors.node import NodeDetector
from runrepo.models import Confidence, FrameworkCategory


def test_node_detector_npm_with_nvmrc(create_fixture_repo):
    repo = create_fixture_repo(
        {
            ".nvmrc": "22.14.0\n",
            "package.json": '{"name": "demo-app", "scripts": {"dev": "node server.js"}, "dependencies": {"express": "^4.18.2"}}',
            "package-lock.json": '{"name": "demo-app", "lockfileVersion": 3}',
            "server.js": 'console.log("hello");',
        }
    )

    detector = NodeDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    assert "JavaScript" in result.languages
    assert len(result.runtimes) == 1
    assert result.runtimes[0].name == "node"
    assert result.runtimes[0].version == "22.14.0"
    assert any(e.source == ".nvmrc" for e in result.runtimes[0].evidence)

    assert len(result.package_managers) == 1
    assert result.package_managers[0].name == "npm"
    assert result.package_managers[0].lockfile == "package-lock.json"

    assert len(result.frameworks) == 1
    assert result.frameworks[0].name == "Express"
    assert result.frameworks[0].category == FrameworkCategory.WEB_BACKEND

    assert len(result.scripts) == 1
    assert result.scripts[0].name == "dev"
    assert result.scripts[0].command == "node server.js"


def test_node_detector_pnpm_nextjs(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "package.json": '{"name": "next-app", "packageManager": "pnpm@9.1.0", "scripts": {"build": "next build"}, "dependencies": {"next": "14.2.0", "react": "18.3.0"}}',
            "pnpm-lock.yaml": "lockfileVersion: '9.0'\n",
            "tsconfig.json": '{"compilerOptions": {}}',
            "pages/index.tsx": "export default function Home() { return <div>Home</div>; }",
        }
    )

    detector = NodeDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    assert "JavaScript" in result.languages
    assert "TypeScript" in result.languages
    assert len(result.package_managers) == 1
    assert result.package_managers[0].name == "pnpm"
    assert result.package_managers[0].version == "9.1.0"
    assert result.package_managers[0].lockfile == "pnpm-lock.yaml"

    fw_names = {f.name for f in result.frameworks}
    assert "Next.js" in fw_names


def test_node_detector_monorepo(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n",
            "apps/web/package.json": '{"name": "web-app", "dependencies": {"next": "14.2.0"}}',
            "apps/docs/package.json": '{"name": "docs-app", "dependencies": {"astro": "4.0.0"}}',
        }
    )

    detector = NodeDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    assert result.is_monorepo is True
    assert len(result.subprojects) == 2
    sub_paths = {sp.path for sp in result.subprojects}
    assert "apps/web" in sub_paths
    assert "apps/docs" in sub_paths
