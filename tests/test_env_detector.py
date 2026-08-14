"""Unit tests for environment variable detection and edge-case .env parsing."""

from runrepo.env.detector import EnvDetector
from runrepo.env.models import EnvClassification, EnvEntryType


def test_parse_env_quoted_values():
    content = """
    DOUBLE_QUOTED="hello world"
    SINGLE_QUOTED='single value'
    QUOTED_WITH_SPACES=" value with leading and trailing spaces "
    """
    env_file = EnvDetector.parse_env_content(content)
    assert env_file.get_value("DOUBLE_QUOTED") == "hello world"
    assert env_file.get_value("SINGLE_QUOTED") == "single value"
    assert env_file.get_value("QUOTED_WITH_SPACES") == " value with leading and trailing spaces "


def test_parse_env_spaces_around_equal():
    content = """
    KEY1 = value1
    KEY2   =    value2
    """
    env_file = EnvDetector.parse_env_content(content)
    assert env_file.get_value("KEY1") == "value1"
    assert env_file.get_value("KEY2") == "value2"


def test_parse_env_comments_and_inlines():
    content = """
    # Main Configuration
    PORT=3000 # Server listening port
    # Another comment
    HOST=localhost # Default host
    """
    env_file = EnvDetector.parse_env_content(content)
    assert env_file.get_value("PORT") == "3000"
    assert env_file.get_value("HOST") == "localhost"

    comments = [e.comment for e in env_file.entries if e.entry_type == EnvEntryType.COMMENT]
    assert "Main Configuration" in comments
    assert "Another comment" in comments


def test_parse_env_escaped_characters():
    content = r'MULTILINE_ESCAPE="line1\nline2\ttab"'
    env_file = EnvDetector.parse_env_content(content)
    val = env_file.get_value("MULTILINE_ESCAPE")
    assert val == "line1\nline2\ttab"


def test_parse_env_multiline_block():
    content = """
    CERTIFICATE="-----BEGIN CERTIFICATE-----
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA
    -----END CERTIFICATE-----"
    NEXT_KEY=value
    """
    env_file = EnvDetector.parse_env_content(content)
    cert = env_file.get_value("CERTIFICATE")
    assert "BEGIN CERTIFICATE" in cert
    assert "END CERTIFICATE" in cert
    assert env_file.get_value("NEXT_KEY") == "value"


def test_detect_project_requirements_docker_compose(tmp_path):
    compose_content = """
    services:
      web:
        image: node:20
        environment:
          - NODE_ENV=production
          - PORT=8080
      db:
        image: postgres:16
        environment:
          POSTGRES_DB: myapp
          POSTGRES_PASSWORD: secret
    """
    (tmp_path / "compose.yaml").write_text(compose_content, encoding="utf-8")

    reqs = EnvDetector.detect_project_requirements(tmp_path)
    names = {r.name for r in reqs}
    assert "NODE_ENV" in names
    assert "PORT" in names
    assert "POSTGRES_DB" in names
    assert "POSTGRES_PASSWORD" in names


def test_detect_source_code_references_node_and_python(tmp_path):
    # Node config file
    (tmp_path / "next.config.js").write_text(
        'module.exports = { env: { API_KEY: process.env.API_KEY, DB: process.env["DATABASE_URL"] } };',
        encoding="utf-8",
    )

    # Python settings file
    (tmp_path / "settings.py").write_text(
        'import os\nSECRET = os.getenv("APP_SECRET_KEY")\nPORT = int(os.environ.get("HTTP_PORT", "5000"))\n',
        encoding="utf-8",
    )

    reqs = EnvDetector.detect_project_requirements(tmp_path)
    names = {r.name for r in reqs}
    assert "API_KEY" in names
    assert "DATABASE_URL" in names
    assert "APP_SECRET_KEY" in names
    assert "HTTP_PORT" in names
