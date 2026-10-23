from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GuardrailResult(BaseModel):
    allowed: bool
    rule: str = "allow"
    detail: str = "Input passed deterministic security checks."
    matched_patterns: list[str] = Field(default_factory=list)


class GuardrailViolation(ValueError):
    def __init__(self, result: GuardrailResult) -> None:
        super().__init__(result.detail)
        self.result = result


class GuardrailService:
    """Deterministic prompt-injection, abuse, secret, and shape safeguards."""

    MAX_TEXT_LENGTH = 50_000
    MAX_TOOL_BYTES = 250_000
    _RULES = {
        "prompt_injection": (
            re.compile(r"\bignore\s+(all\s+)?(previous|prior|system|developer)\s+instructions?\b", re.I),
            re.compile(r"\b(reveal|print|show|leak)\s+(the\s+)?(system|developer)\s+prompt\b", re.I),
            re.compile(r"\b(jailbreak|override\s+(the\s+)?safeguards?|bypass\s+(the\s+)?guardrails?)\b", re.I),
        ),
        "abusive_or_threatening": (
            re.compile(r"\b(kill|murder|attack|hurt)\b.{0,30}\b(you|them|people|person)\b", re.I),
        ),
        "secret_exposure": (
            re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
            re.compile(r"\bsk-(?:proj-)?[0-9A-Za-z_-]{20,}\b"),
        ),
    }

    @classmethod
    def inspect_text(cls, value: str) -> GuardrailResult:
        if len(value) > cls.MAX_TEXT_LENGTH:
            return GuardrailResult(
                allowed=False,
                rule="input_size",
                detail=f"Input exceeds the {cls.MAX_TEXT_LENGTH}-character safety limit.",
            )
        for rule, patterns in cls._RULES.items():
            matches = [pattern.pattern for pattern in patterns if pattern.search(value)]
            if matches:
                return GuardrailResult(
                    allowed=False,
                    rule=rule,
                    detail=f"Input blocked by the {rule} guardrail.",
                    matched_patterns=matches,
                )
        return GuardrailResult(allowed=True)

    @classmethod
    def require_safe_text(cls, value: str) -> GuardrailResult:
        result = cls.inspect_text(value)
        if not result.allowed:
            raise GuardrailViolation(result)
        return result

    @classmethod
    def require_valid_tool_payload(cls, value: Any) -> None:
        try:
            encoded = json.dumps(value, sort_keys=True, default=cls._json_default)
        except (TypeError, ValueError) as exc:
            raise GuardrailViolation(
                GuardrailResult(
                    allowed=False,
                    rule="tool_output_type",
                    detail="Tool output is not JSON serializable.",
                )
            ) from exc
        if len(encoded.encode("utf-8")) > cls.MAX_TOOL_BYTES:
            raise GuardrailViolation(
                GuardrailResult(
                    allowed=False,
                    rule="tool_output_size",
                    detail=f"Tool output exceeds {cls.MAX_TOOL_BYTES} bytes.",
                )
            )
        cls.require_safe_text(encoded)

    @staticmethod
    def _json_default(value: Any) -> Any:
        """Normalize supported typed tool values while rejecting arbitrary objects."""
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        raise TypeError(f"Unsupported tool payload type: {type(value).__name__}")
