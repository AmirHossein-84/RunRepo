"""Unit tests for environment domain models and EnvFile AST parsing."""

from runrepo.env.models import (
    EnvClassification,
    EnvEntry,
    EnvEntryType,
    EnvFile,
    EnvRequirement,
)


def test_env_requirement_serialization():
    req = EnvRequirement(
        name="DATABASE_URL",
        classification=EnvClassification.AUTO_GENERATABLE,
        is_required=True,
        default_value="postgresql://localhost:5432/app",
        is_secret=True,
        source=".env.example",
    )

    data = req.model_dump()
    assert data["name"] == "DATABASE_URL"
    assert data["classification"] == "auto_generatable"
    assert data["is_secret"] is True


def test_env_file_ast_operations():
    env_file = EnvFile(
        entries=[
            EnvEntry(entry_type=EnvEntryType.COMMENT, raw_line="# App Config", comment="App Config"),
            EnvEntry(entry_type=EnvEntryType.KEY_VALUE, raw_line="PORT=3000", key="PORT", value="3000"),
            EnvEntry(entry_type=EnvEntryType.BLANK, raw_line=""),
        ]
    )

    assert env_file.has_key("PORT") is True
    assert env_file.has_key("HOST") is False
    assert env_file.get_value("PORT") == "3000"

    # Update existing key
    env_file.set_value("PORT", "8080")
    assert env_file.get_value("PORT") == "8080"

    # Add new key
    env_file.set_value("HOST", "0.0.0.0")
    assert env_file.has_key("HOST") is True
    assert env_file.get_value("HOST") == "0.0.0.0"

    # Verify serialization string
    out = env_file.to_string()
    assert "# App Config\n" in out
    assert "PORT=8080\n" in out
    assert "HOST=0.0.0.0\n" in out
