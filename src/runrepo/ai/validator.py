"""Strict validator and safety barrier for AI responses and command suggestions."""

import json
import re
from typing import Any
from runrepo.ai.models import AIActionSuggestion, AIAnalysisResult, AIDiagnosticResult

FORBIDDEN_COMMAND_PATTERNS = [
    r"\brm\s+-[rf]*[rf]\b",
    r"\bdel\s+/[sfq]*[sfq]\b",
    r"\bformat\s+[a-zA-Z]:",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bdrop\s+(?:database|table|schema)\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"curl\s+[^|]+\|\s*(?:bash|sh|zsh|powershell|pwsh)",
    r"wget\s+[^|]+\|\s*(?:bash|sh|zsh|powershell|pwsh)",
    r"\beval\s*\(",
    r"\bpowershell\s+.*-enc(?:odedcommand)?\b",
]


class AIResponseValidator:
    """Validates, parses, and enforces safety boundaries on raw AI text responses."""

    @classmethod
    def extract_json_text(cls, raw_text: str) -> str:
        """Strip markdown fences and extract raw JSON content."""
        clean = raw_text.strip()
        # Strip ```json ... ``` or ``` ... ```
        if clean.startswith("```"):
            lines = clean.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            clean = "\n".join(lines).strip()
        return clean

    @classmethod
    def is_command_safe(cls, command: list[str] | None) -> tuple[bool, str]:
        """Check command tokens against forbidden/destructive patterns."""
        if not command:
            return True, ""

        cmd_line = " ".join(command).lower()
        for pattern in FORBIDDEN_COMMAND_PATTERNS:
            if re.search(pattern, cmd_line, re.IGNORECASE):
                return False, f"Command contains forbidden destructive pattern: '{pattern}'"

        # Check for potential fake or hardcoded credentials
        if re.search(r"(?:--)?(?:api[-_]key|secret|password|token)\s*=\s*['\"]?[A-Za-z0-9_-]{16,}", cmd_line, re.IGNORECASE):
            return False, "Command contains hardcoded credentials or synthesized secrets"

        return True, ""

    @classmethod
    def validate_action(cls, action: AIActionSuggestion) -> AIActionSuggestion:
        """Validate and clamp safety parameters on an action suggestion."""
        is_safe, reason = cls.is_command_safe(action.command)
        if not is_safe:
            action.is_safe = False
            action.command = []
            action.description = f"[REJECTED DANGEROUS SUGGESTION]: {reason}"

        # AI cannot downgrade risk to SAFE if a command is specified
        if action.command and action.risk_level == "SAFE":
            action.risk_level = "REQUIRES_CONFIRMATION"

        return action

    @classmethod
    def parse_analysis_result(cls, raw_text: str) -> AIAnalysisResult:
        """Parse raw AI text into validated AIAnalysisResult."""
        json_str = cls.extract_json_text(raw_text)
        try:
            data = json.loads(json_str)
        except Exception as e:
            raise ValueError(f"AI response is not valid JSON: {e}\nRaw output: {raw_text[:200]}")

        if not isinstance(data, dict):
            raise ValueError("AI response must be a JSON dictionary object.")

        result = AIAnalysisResult.model_validate(data)

        # Validate each suggested action
        validated_actions = [cls.validate_action(a) for a in result.suggested_actions]
        result.suggested_actions = validated_actions

        return result

    @classmethod
    def parse_diagnostic_result(cls, raw_text: str) -> AIDiagnosticResult:
        """Parse raw AI text into validated AIDiagnosticResult."""
        json_str = cls.extract_json_text(raw_text)
        try:
            data = json.loads(json_str)
        except Exception as e:
            raise ValueError(f"AI diagnostic response is not valid JSON: {e}\nRaw output: {raw_text[:200]}")

        if not isinstance(data, dict):
            raise ValueError("AI diagnostic response must be a JSON dictionary object.")

        result = AIDiagnosticResult.model_validate(data)

        # Validate each suggested fix
        validated_fixes = [cls.validate_action(f) for f in result.suggested_fixes]
        result.suggested_fixes = validated_fixes

        return result
