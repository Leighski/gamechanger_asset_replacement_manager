"""Offline rule-based provider — manual interpretation mode without external AI."""

from __future__ import annotations

import json
import time
from typing import Any

from services.interpretation.providers.base import AIProvider, AIProviderResponse


class OfflineRuleProvider(AIProvider):
    """Deterministic interpretation from measurement rules — no network required."""

    @property
    def provider_name(self) -> str:
        return "offline"

    def is_configured(self) -> bool:
        return True

    def interpret(self, prompt: str) -> AIProviderResponse:
        started = time.perf_counter()
        payload = json.loads(prompt)
        suggestions = payload.get("rule_suggestions", [])
        elapsed = (time.perf_counter() - started) * 1000.0
        return AIProviderResponse(
            provider_name=self.provider_name,
            raw_text=json.dumps({"suggestions": suggestions}, indent=2),
            suggestions=suggestions,
            response_time_ms=round(elapsed, 2),
            model="rule-engine",
        )
