"""AI provider registry — select provider by configuration."""

from __future__ import annotations

from models.ai_settings import AISettings
from services.interpretation.providers.base import AIProvider, AIProviderResponse
from services.interpretation.providers.offline import OfflineRuleProvider


class ProviderRegistry:
    """Resolve configured AI provider; falls back to offline rule engine."""

    def __init__(self, settings: AISettings | None = None) -> None:
        self._settings = settings or AISettings()
        self._offline = OfflineRuleProvider()

    def get_provider(self) -> AIProvider:
        provider_id = self._settings.active_provider.strip().lower()
        if provider_id in ("openai", "anthropic", "gemini", "ollama"):
            configured = self._settings.is_provider_configured(provider_id)
            if configured:
                return _StubRemoteProvider(provider_id, self._settings)
        return self._offline

    def is_offline_mode(self) -> bool:
        return isinstance(self.get_provider(), OfflineRuleProvider)


class _StubRemoteProvider(AIProvider):
    """Placeholder for future vendor integrations — delegates to offline rules when unimplemented."""

    def __init__(self, provider_id: str, settings: AISettings) -> None:
        self._provider_id = provider_id
        self._settings = settings
        self._offline = OfflineRuleProvider()

    @property
    def provider_name(self) -> str:
        return self._provider_id

    def is_configured(self) -> bool:
        return self._settings.is_provider_configured(self._provider_id)

    def interpret(self, prompt: str) -> AIProviderResponse:
        response = self._offline.interpret(prompt)
        return AIProviderResponse(
            provider_name=self._provider_id,
            raw_text=response.raw_text,
            suggestions=response.suggestions,
            response_time_ms=response.response_time_ms,
            model=f"{self._provider_id}-stub",
        )
