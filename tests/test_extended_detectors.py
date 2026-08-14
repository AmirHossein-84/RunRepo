"""Unit tests for Bun, Deno, Go, Rust, and Conda detectors."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detectors.bun import BunDetector
from runrepo.analyzer.detectors.conda import CondaDetector
from runrepo.analyzer.detectors.deno import DenoDetector
from runrepo.analyzer.detectors.go import GoDetector
from runrepo.analyzer.detectors.rust import RustDetector


def test_bun_detector(tmp_path):
    (tmp_path / "bun.lockb").write_bytes(b"")
    ctx = ScanContext(tmp_path)
    res = BunDetector().detect(ctx)

    assert any(r.name == "bun" for r in res.runtimes)
    assert any(pm.name == "bun" for pm in res.package_managers)


def test_deno_detector(tmp_path):
    (tmp_path / "deno.json").write_text('{"tasks": {"dev": "deno run main.ts"}}', encoding="utf-8")
    ctx = ScanContext(tmp_path)
    res = DenoDetector().detect(ctx)

    assert any(r.name == "deno" for r in res.runtimes)
    assert any(s.name == "dev" for s in res.scripts)


def test_go_detector(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/myapp\n\ngo 1.22\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    ctx = ScanContext(tmp_path)
    res = GoDetector().detect(ctx)

    assert any(r.name == "go" for r in res.runtimes)
    assert any(s.name == "dev" for s in res.scripts)


def test_rust_detector(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "app"\nversion = "0.1.0"\n', encoding="utf-8")
    ctx = ScanContext(tmp_path)
    res = RustDetector().detect(ctx)

    assert any(r.name == "rust" for r in res.runtimes)
    assert any(pm.name == "cargo" for pm in res.package_managers)
    assert any(s.name == "dev" for s in res.scripts)


def test_conda_detector(tmp_path):
    (tmp_path / "environment.yml").write_text("name: myenv\ndependencies:\n  - python=3.11\n", encoding="utf-8")
    ctx = ScanContext(tmp_path)
    res = CondaDetector().detect(ctx)

    assert any(r.name == "python" for r in res.runtimes)
    assert any(pm.name == "conda" for pm in res.package_managers)
