"""Persistent application settings."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from core.paths import CONFIG_DIR, SETTINGS_EXAMPLE_PATH, SETTINGS_PATH
from models.settings import AppSettings
from services.logging_manager import get_logger, log_settings_loaded, log_settings_saved

logger = get_logger()


class SettingsManager:
    """Load, persist, and expose application settings."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or SETTINGS_PATH
        self._settings = AppSettings()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def settings(self) -> AppSettings:
        return self._settings

    def load(self) -> AppSettings:
        if not self._path.is_file():
            self._ensure_example_exists()
            self._settings = AppSettings()
            self.save()
            log_settings_loaded(self._path)
            return self._settings

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._settings = AppSettings.model_validate(raw)
            log_settings_loaded(self._path)
            return self._settings
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            logger.error("Failed to load settings from {}: {}", self._path, exc)
            self._settings = AppSettings()
            return self._settings

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = self._settings.model_dump(mode="json")
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        log_settings_saved(self._path)

    def update(self, **kwargs: object) -> AppSettings:
        data = self._settings.model_dump()
        data.update(kwargs)
        self._settings = AppSettings.model_validate(data)
        self.save()
        return self._settings

    def _ensure_example_exists(self) -> None:
        if SETTINGS_EXAMPLE_PATH.is_file():
            return
        example = AppSettings().model_dump(mode="json")
        SETTINGS_EXAMPLE_PATH.write_text(json.dumps(example, indent=2), encoding="utf-8")
