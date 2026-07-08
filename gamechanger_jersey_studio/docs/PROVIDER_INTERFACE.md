# Provider Interface

## AIProvider contract

```python
class AIProvider(ABC):
    @property
    def provider_name(self) -> str: ...

    def is_configured(self) -> bool: ...

    def interpret(self, prompt: str) -> AIProviderResponse: ...
```

## Supported providers (abstraction ready)

| Provider | Config key | Status |
|----------|------------|--------|
| Offline (rules) | `offline` | Implemented — default |
| OpenAI | `openai` | Stub — falls back to rules |
| Anthropic | `anthropic` | Stub — falls back to rules |
| Google Gemini | `gemini` | Stub — falls back to rules |
| Ollama (local) | `ollama` | Stub — falls back to rules |

## Configuration

Settings file: `config/ai_settings.json` (see `config/ai_settings.example.json`).

```json
{
  "active_provider": "offline",
  "openai": { "enabled": false, "api_key": "", "model": "gpt-4o" }
}
```

The application does not depend on a single vendor. Future builds will implement live API calls per provider without changing the Interpretation Engine interface.

## Response format

Providers return `AIProviderResponse` with a list of suggestion dictionaries:

```json
{
  "target_field": "collar_style",
  "current_value": "",
  "proposed_value": "v-neck",
  "confidence": 88.5,
  "reasoning": "Measured neck opening ratio...",
  "source_measurements": ["neck_opening_width_ratio"]
}
```
