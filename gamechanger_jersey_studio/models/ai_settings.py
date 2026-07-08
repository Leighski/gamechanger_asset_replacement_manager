"""AI provider configuration model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AIProviderConfig(BaseModel):
    enabled: bool = False
    api_key: str = ""
    model: str = ""
    base_url: str = ""


class AISettings(BaseModel):
    active_provider: str = "offline"
    openai: AIProviderConfig = Field(default_factory=AIProviderConfig)
    anthropic: AIProviderConfig = Field(default_factory=AIProviderConfig)
    gemini: AIProviderConfig = Field(default_factory=AIProviderConfig)
    ollama: AIProviderConfig = Field(default_factory=lambda: AIProviderConfig(base_url="http://localhost:11434"))

    def is_provider_configured(self, provider_id: str) -> bool:
        mapping = {
            "openai": self.openai,
            "anthropic": self.anthropic,
            "gemini": self.gemini,
            "ollama": self.ollama,
        }
        config = mapping.get(provider_id)
        if config is None:
            return False
        if provider_id == "ollama":
            return config.enabled and bool(config.base_url.strip())
        return config.enabled and bool(config.api_key.strip())
