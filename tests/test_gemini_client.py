"""Unit tests for GeminiClient availability, error handling, and prompt sanitization."""

import pytest
from runrepo.ai.gemini import GeminiClient


def test_gemini_client_availability(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("RUNREPO_NO_AI", raising=False)

    client = GeminiClient()
    assert client.is_available() is False

    monkeypatch.setenv("GEMINI_API_KEY", "test_key_123")
    client_with_key = GeminiClient()
    assert client_with_key.is_available() is True

    # When RUNREPO_NO_AI is set, client is disabled
    monkeypatch.setenv("RUNREPO_NO_AI", "1")
    assert client_with_key.is_available() is False


def test_gemini_client_prompt_sanitization():
    raw_prompt = """
    Analyze error log:
    DATABASE_PASSWORD=super_secret_db_pass
    Bearer ya29.a0AfH6SMD_secret_token_12345
    sk-proj-abcdef1234567890abcdef
    Error: Failed to connect
    """

    sanitized = GeminiClient.sanitize_prompt(raw_prompt)
    assert "super_secret_db_pass" not in sanitized
    assert "secret_token_12345" not in sanitized
    assert "abcdef1234567890abcdef" not in sanitized
    assert "******" in sanitized


def test_gemini_client_mock_transport():
    mock_response = '{"confidence": 0.9, "reasoning_summary": "Test OK"}'

    def mock_transport(payload):
        assert "contents" in payload
        return mock_response

    client = GeminiClient(api_key="mock_key", transport=mock_transport)
    assert client.is_available() is True

    output = client.generate("test prompt")
    assert output == mock_response


def test_gemini_client_unavailable_raises_runtime_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = GeminiClient()
    with pytest.raises(RuntimeError, match="Gemini AI is not available"):
        client.generate("prompt")
