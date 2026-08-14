"""Unit tests ensuring AI privacy, secret scrubbing, and zero direct execution capability."""

from runrepo.ai.gemini import GeminiClient
from runrepo.ai.validator import AIResponseValidator


def test_gemini_client_never_sends_raw_secrets():
    raw_prompt = "Failed starting with OPENAI_API_KEY=sk-proj-12345678901234567890 and DB_PASSWORD=my_super_secret_password"
    sanitized = GeminiClient.sanitize_prompt(raw_prompt)

    assert "sk-proj-12345678901234567890" not in sanitized
    assert "my_super_secret_password" not in sanitized
    assert "******" in sanitized


def test_validator_rejects_synthesized_credentials():
    command_with_secret = ["uvicorn", "main:app", "--api-key=sk-1234567890abcdef1234567890"]
    is_safe, reason = AIResponseValidator.is_command_safe(command_with_secret)

    assert is_safe is False
    assert "credentials" in reason.lower() or "secret" in reason.lower()
