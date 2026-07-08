"""Recent projects manager tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from models.settings import AppSettings
from services.recent_projects_manager import RecentProjectsManager
from services.settings_manager import SettingsManager


@pytest.fixture
def settings_manager(tmp_path: Path) -> SettingsManager:
    mgr = SettingsManager(path=tmp_path / "settings.json")
    mgr.load()
    return mgr


def test_add_recent_project_stores_metadata(settings_manager: SettingsManager) -> None:
    recent = RecentProjectsManager(settings_manager)
    entries = recent.add(
        "/tmp/project_alpha",
        name="Alpha Kit",
        club="Alpha FC",
        season="2025/26",
    )
    assert len(entries) == 1
    assert entries[0].name == "Alpha Kit"
    assert entries[0].club == "Alpha FC"
    assert entries[0].season == "2025/26"


def test_recent_projects_order_and_limit(settings_manager: SettingsManager) -> None:
    recent = RecentProjectsManager(settings_manager)
    for i in range(15):
        recent.add(f"/tmp/project_{i}")
    assert len(recent.entries) == RecentProjectsManager.MAX_RECENT
    assert recent.entries[0].name == "project_14"


def test_remove_recent_project(settings_manager: SettingsManager) -> None:
    recent = RecentProjectsManager(settings_manager)
    recent.add("/tmp/one")
    recent.add("/tmp/two")
    updated = recent.remove("/tmp/one")
    assert len(updated) == 1
    assert updated[0].name == "two"


def test_clear_recent_projects(settings_manager: SettingsManager) -> None:
    recent = RecentProjectsManager(settings_manager)
    recent.add("/tmp/one")
    recent.clear()
    assert recent.entries == []
