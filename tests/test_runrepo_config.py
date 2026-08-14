"""Unit tests for ConfigLoader loading and validating runrepo.yaml."""

import pytest
from runrepo.reproducibility.config import ConfigLoader


def test_load_valid_runrepo_yaml(tmp_path):
    yaml_content = """
    version: 1
    name: sample-project
    package_manager: pnpm
    runtimes:
      node: ">=20.0.0"
    docker: true
    services:
      postgres:
        image: postgres:16-alpine
        port: 5432
    startup:
      command: "pnpm dev"
    """
    (tmp_path / "runrepo.yaml").write_text(yaml_content, encoding="utf-8")

    config = ConfigLoader.load(tmp_path)
    assert config is not None
    assert config.name == "sample-project"
    assert config.package_manager == "pnpm"
    assert config.runtimes["node"] == ">=20.0.0"
    assert "postgres" in config.services
    assert config.services["postgres"].port == 5432
    assert config.startup.command == "pnpm dev"


def test_load_missing_config_returns_none(tmp_path):
    assert ConfigLoader.load(tmp_path) is None


def test_load_malformed_yaml_raises_value_error(tmp_path):
    (tmp_path / "runrepo.yaml").write_text("invalid: yaml: [unbalanced", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        ConfigLoader.load(tmp_path)


def test_load_invalid_schema_raises_value_error(tmp_path):
    (tmp_path / "runrepo.yaml").write_text("version: 'not-an-integer'", encoding="utf-8")
    with pytest.raises(ValueError, match="Configuration schema error"):
        ConfigLoader.load(tmp_path)
