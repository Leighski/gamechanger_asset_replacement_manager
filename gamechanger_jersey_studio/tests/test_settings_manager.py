"""Settings manager tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from models.settings import AppSettings, RecentProjectEntry, WindowGeometry
from services.settings_manager import SettingsManager


@pytest.fixture
def settings_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


def test_default_settings_created(settings_path: Path) -> None:
    mgr = SettingsManager(path=settings_path)
    settings = mgr.load()
    assert settings.theme == "dark"
    assert settings.window.width == 1440
    assert settings_path.is_file()


def test_settings_round_trip(settings_path: Path) -> None:
    mgr = SettingsManager(path=settings_path)
    mgr.load()
    mgr.update(
        theme="dark",
        autosave_interval_minutes=10,
        window=WindowGeometry(width=1600, height=1000, x=50, y=60, maximised=True),
    )
    reloaded = SettingsManager(path=settings_path).load()
    assert reloaded.autosave_interval_minutes == 10
    assert reloaded.window.maximised is True
    assert reloaded.window.width == 1600


def test_invalid_settings_fallback(settings_path: Path) -> None:
    settings_path.write_text(json.dumps({"theme": 123}), encoding="utf-8")
    mgr = SettingsManager(path=settings_path)
    settings = mgr.load()
    assert isinstance(settings, AppSettings)
    assert settings.theme == "dark"


def test_settings_persist_recent_projects(settings_path: Path) -> None:
    mgr = SettingsManager(path=settings_path)
    mgr.load()
    data = mgr.settings.model_copy(
        update={
            "recent_projects": [
                RecentProjectEntry(path="/tmp/a", name="a", last_opened="now"),
            ]
        }
    )
    mgr._settings = data
    mgr.save()
    reloaded = SettingsManager(path=settings_path).load()
    assert len(reloaded.recent_projects) == 1
    assert reloaded.recent_projects[0].name == "a"
