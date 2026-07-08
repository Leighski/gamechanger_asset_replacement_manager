"""AI provider abstraction — vendor-independent interpretation interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AIProviderResponse:
    """Structured response from any AI provider."""

    provider_name: str
    raw_text: str
    suggestions: list[dict[str, Any]]
    response_time_ms: float
    model: str = ""


class AIProvider(ABC):
    """Abstract AI provider — implementations: OpenAI, Anthropic, Gemini, Ollama, Offline."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def interpret(self, prompt: str) -> AIProviderResponse:
        raise NotImplementedError
