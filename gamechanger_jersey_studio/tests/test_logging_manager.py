"""Logging manager tests."""

from __future__ import annotations

from pathlib import Path

from services.logging_manager import (
    configure_logging,
    flush_logging,
    log_application_closed,
    log_application_started,
    log_settings_loaded,
    log_settings_saved,
    log_window_restored,
)


def test_configure_logging_writes_file(tmp_path: Path) -> None:
    log_file = tmp_path / "application.log"
    configure_logging(log_file)
    log_application_started("Gamechanger Jersey Studio Version 0.1.0 (Build 001)")
    log_settings_loaded(tmp_path / "settings.json")
    log_settings_saved(tmp_path / "settings.json")
    log_window_restored(1440, 900, 100, 100, False)
    log_application_closed()
    flush_logging()
    text = log_file.read_text(encoding="utf-8")
    assert "Application Started" in text
    assert "Settings Loaded" in text
    assert "Settings Saved" in text
    assert "Window Restored" in text
    assert "Application Closed" in text


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    log_file = tmp_path / "application.log"
    configure_logging(log_file)
    configure_logging(log_file)
    log_application_started("test")
    assert log_file.exists()
