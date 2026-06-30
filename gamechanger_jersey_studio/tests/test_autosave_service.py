"""Autosave and recovery tests."""

from __future__ import annotations

from pathlib import Path

from models.project import KitType, NewProjectRequest
from services.autosave_service import AutosaveService, SessionState
from services.project_format import read_project_package
from services.projects_manager import ProjectsManager
from services.recent_projects_manager import RecentProjectsManager
from services.settings_manager import SettingsManager
from services.workspace_service import WorkspaceService


def _manager(tmp_path: Path) -> ProjectsManager:
    settings = SettingsManager(path=tmp_path / "settings.json")
    settings.load()
    workspace = WorkspaceService(root=tmp_path / "workspace")
    autosave = AutosaveService(workspace)
    return ProjectsManager(
        RecentProjectsManager(settings),
        workspace=workspace,
        autosave=autosave,
        application_version="0.2.0",
    )


def test_autosave_writes_recovery_not_primary(tmp_path: Path) -> None:
    mgr = _manager(tmp_path)
    doc = mgr.new_project(
        NewProjectRequest(
            project_name="Autosave Test",
            club_name="Club",
            competition="League",
            season="2025/26",
            kit_type=KitType.HOME,
            output_folder=str(tmp_path / "out"),
            author="Tester",
        )
    )
    primary = Path(doc.file_path)
    primary_mtime = primary.stat().st_mtime
    recovery = mgr.run_autosave()
    assert recovery is not None
    assert recovery.is_file()
    assert recovery.name == "autosave.gjs"
    assert primary.stat().st_mtime == primary_mtime


def test_recovery_candidates_after_unclean_shutdown(tmp_path: Path) -> None:
    mgr = _manager(tmp_path)
    autosave = mgr.autosave_service
    mgr.new_project(
        NewProjectRequest(
            project_name="Recovery Test",
            club_name="Club",
            competition="League",
            season="2025/26",
            kit_type=KitType.HOME,
            output_folder=str(tmp_path / "out"),
            author="Tester",
        )
    )
    mgr.run_autosave()
    autosave._write_session(SessionState(project_path=str(mgr.document.file_path), clean_shutdown=False))  # type: ignore[union-attr]
    candidates = autosave.discover_recovery_candidates()
    assert len(candidates) == 1
    restored = mgr.restore_recovery(
        candidates[0].recovery_path,
        candidates[0].primary_path,
        candidates[0].project_name,
    )
    assert restored.manifest.project_name == "Recovery Test"
    assert any(e.event.value == "Recovery Restored" for e in restored.history.entries)


def test_clean_shutdown_clears_recovery_detection(tmp_path: Path) -> None:
    mgr = _manager(tmp_path)
    autosave = mgr.autosave_service
    autosave._write_session(SessionState(clean_shutdown=True))
    assert autosave.discover_recovery_candidates() == []
