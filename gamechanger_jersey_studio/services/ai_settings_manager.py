"""Load and save AI provider settings."""

from __future__ import annotations

import json
from pathlib import Path

from core.paths import CONFIG_DIR
from models.ai_settings import AISettings

AI_SETTINGS_PATH = CONFIG_DIR / "ai_settings.json"
AI_SETTINGS_EXAMPLE = CONFIG_DIR / "ai_settings.example.json"


class AISettingsManager:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or AI_SETTINGS_PATH
        self._settings = AISettings()

    @property
    def settings(self) -> AISettings:
        return self._settings

    def load(self) -> AISettings:
        if self._path.is_file():
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._settings = AISettings.model_validate(raw)
        return self._settings

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            self._settings.model_dump_json(indent=2),
            encoding="utf-8",
        )
