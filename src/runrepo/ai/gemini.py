"""Gemini API client using Python's standard library urllib with zero external dependencies."""

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Callable


class GeminiClient:
    """Zero-dependency Gemini REST client with early secret scrubbing and robust error handling."""

    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_s: float = 30.0,
        transport: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", self.DEFAULT_MODEL)
        self.timeout_s = timeout_s
        self.transport = transport

    def is_available(self) -> bool:
        """Check if Gemini AI integration is enabled and configured."""
        if os.getenv("RUNREPO_NO_AI", "").strip().lower() in ("1", "true", "yes"):
            return False
        return bool(self.api_key and self.api_key.strip())

    @classmethod
    def sanitize_prompt(cls, text: str) -> str:
        """Strip embedded credentials and tokens from prompt text before sending to AI."""
        # Redact common key=value credentials
        cleaned = re.sub(
            r'([A-Za-z_0-9]*(?:SECRET|PASSWORD|PASSWD|KEY|TOKEN|AUTH)[A-Za-z_0-9]*\s*=\s*)([^\s,\n\r]+)',
            lambda m: f"{m.group(1)}******",
            text,
            flags=re.IGNORECASE,
        )
        # Redact bearer/sk tokens
        cleaned = re.sub(
            r'(Bearer\s+|sk-[A-Za-z0-9_-]+|ghp_[A-Za-z0-9_]+)([A-Za-z0-9_.-]+)',
            lambda m: f"{m.group(1)[:4]}******",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned

    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        """Send sanitized prompt to Gemini and return raw text response."""
        if not self.is_available():
            raise RuntimeError("Gemini AI is not available (GEMINI_API_KEY is not set or RUNREPO_NO_AI is enabled).")

        sanitized_prompt = self.sanitize_prompt(prompt)

        # Build payload
        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": sanitized_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
        }

        if system_instruction:
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }

        # Mock transport for offline unit testing
        if self.transport is not None:
            return self.transport(payload)

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as response:
                resp_bytes = response.read()
                resp_json = json.loads(resp_bytes.decode("utf-8", errors="replace"))
                return self._extract_text_from_response(resp_json)

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            if e.code == 429:
                raise RuntimeError(f"Gemini API rate limit exceeded (429): {err_body}")
            elif e.code in (401, 403):
                raise RuntimeError(f"Gemini API authentication failed ({e.code}): Check GEMINI_API_KEY.")
            else:
                raise RuntimeError(f"Gemini API returned error {e.code}: {err_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error communicating with Gemini API: {e.reason}")
        except TimeoutError:
            raise RuntimeError(f"Gemini API request timed out after {self.timeout_s}s.")

    @classmethod
    def _extract_text_from_response(cls, resp_data: dict[str, Any]) -> str:
        """Extract content text from Gemini response structure."""
        candidates = resp_data.get("candidates", [])
        if not candidates:
            raise ValueError(f"Gemini response contained no candidates: {resp_data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise ValueError(f"Gemini candidate contained no parts: {candidates[0]}")

        return parts[0].get("text", "")
