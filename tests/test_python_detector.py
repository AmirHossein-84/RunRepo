"""Unit tests for PythonDetector."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detectors.python import PythonDetector
from runrepo.models import FrameworkCategory


def test_python_detector_requirements_txt(create_fixture_repo):
    repo = create_fixture_repo(
        {
            ".python-version": "3.11.4\n",
            "requirements.txt": "fastapi>=0.110.0\nuvicorn[standard]==0.28.0\npytest>=8.0\n",
            "main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
        }
    )

    detector = PythonDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    assert "Python" in result.languages
    assert len(result.runtimes) == 1
    assert result.runtimes[0].name == "python"
    assert result.runtimes[0].version == "3.11.4"

    assert len(result.package_managers) == 1
    assert result.package_managers[0].name == "pip"

    fw_names = {f.name: f.category for f in result.frameworks}
    assert "FastAPI" in fw_names
    assert fw_names["FastAPI"] == FrameworkCategory.WEB_BACKEND

    assert "main.py" in result.entrypoints


def test_python_detector_uv_and_pyproject(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "pyproject.toml": """
[project]
name = "my-service"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "django>=5.0",
    "psycopg2-binary>=2.9",
]

[project.scripts]
serve = "my_service.cli:main"
""",
            "uv.lock": "version = 1\n",
            "manage.py": "# Django manage\n",
        }
    )

    detector = PythonDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    assert len(result.runtimes) == 1
    assert result.runtimes[0].version == ">=3.12"

    assert len(result.package_managers) == 1
    assert result.package_managers[0].name == "uv"
    assert result.package_managers[0].lockfile == "uv.lock"

    fw_names = {f.name for f in result.frameworks}
    assert "Django" in fw_names

    scripts_map = {s.name: s.command for s in result.scripts}
    assert "serve" in scripts_map
    assert scripts_map["serve"] == "my_service.cli:main"


def test_python_detector_poetry(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "pyproject.toml": """
[tool.poetry]
name = "poetry-app"
version = "0.1.0"

[tool.poetry.dependencies]
python = "^3.10"
flask = "^3.0.0"
""",
            "poetry.lock": "[[package]]\nname = 'flask'\n",
            "app.py": "from flask import Flask\n",
        }
    )

    detector = PythonDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    assert len(result.package_managers) == 1
    assert result.package_managers[0].name == "poetry"
    assert result.package_managers[0].lockfile == "poetry.lock"

    fw_names = {f.name for f in result.frameworks}
    assert "Flask" in fw_names
    assert "app.py" in result.entrypoints
