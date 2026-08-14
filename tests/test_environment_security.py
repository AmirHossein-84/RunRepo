"""Unit tests for environment security, secret redaction, and external key blocking."""

from runrepo.env.generator import EnvGenerator
from runrepo.env.models import EnvClassification, EnvRequirement
from runrepo.env.redactor import is_sensitive_key, redact_value


def test_is_sensitive_key():
    assert is_sensitive_key("JWT_SECRET") is True
    assert is_sensitive_key("POSTGRES_PASSWORD") is True
    assert is_sensitive_key("API_KEY") is True
    assert is_sensitive_key("AUTH_TOKEN") is True
    assert is_sensitive_key("PORT") is False
    assert is_sensitive_key("NODE_ENV") is False
    assert is_sensitive_key("HOST") is False


def test_redact_value():
    assert redact_value("PORT", "3000") == "3000"
    assert redact_value("SECRET_KEY", "12345") == "******"
    masked = redact_value("API_KEY", "sk-proj-1234567890abcdef")
    assert masked.startswith("sk-")
    assert "1234567890abcdef" not in masked
    assert "*" in masked


def test_external_credential_blocking():
    external_keys = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "STRIPE_SECRET_KEY",
        "SENDGRID_API_KEY",
    ]

    for k in external_keys:
        req = EnvRequirement(
            name=k,
            classification=EnvClassification.EXTERNAL_SERVICE,
            is_required=True,
        )
        val = EnvGenerator.generate_value(req)
        assert val is None, f"Generator must NEVER generate values for {k}"
