"""Recent projects list management."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from models.settings import AppSettings, RecentProjectEntry
from services.settings_manager import SettingsManager


class RecentProjectsManager:
    """Maintain a bounded list of recently opened projects."""

    MAX_RECENT = 12

    def __init__(self, settings_manager: SettingsManager) -> None:
        self._settings_manager = settings_manager

    @property
    def settings_manager(self) -> SettingsManager:
        return self._settings_manager

    @property
    def entries(self) -> list[RecentProjectEntry]:
        return list(self._settings_manager.settings.recent_projects)

    def add(
        self,
        project_path: str | Path,
        *,
        name: str = "",
        club: str = "",
        season: str = "",
    ) -> list[RecentProjectEntry]:
        path = Path(project_path).expanduser().resolve()
        path_str = str(path)
        display_name = name or path.stem or path_str
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

        existing = [e for e in self._settings_manager.settings.recent_projects if e.path != path_str]
        updated = [
            RecentProjectEntry(
                path=path_str,
                name=display_name,
                club=club,
                season=season,
                last_opened=stamp,
            )
        ] + existing
        updated = updated[: self.MAX_RECENT]

        settings = self._settings_manager.settings.model_copy(update={"recent_projects": updated})
        self._settings_manager._settings = settings
        self._settings_manager.save()
        return updated

    def remove(self, project_path: str | Path) -> list[RecentProjectEntry]:
        path_str = str(Path(project_path).expanduser().resolve())
        updated = [e for e in self._settings_manager.settings.recent_projects if e.path != path_str]
        settings = self._settings_manager.settings.model_copy(update={"recent_projects": updated})
        self._settings_manager._settings = settings
        self._settings_manager.save()
        return updated

    def clear(self) -> None:
        settings = self._settings_manager.settings.model_copy(update={"recent_projects": []})
        self._settings_manager._settings = settings
        self._settings_manager.save()

    @staticmethod
    def from_settings(settings: AppSettings) -> list[RecentProjectEntry]:
        return list(settings.recent_projects)
