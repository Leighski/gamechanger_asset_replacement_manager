"""Project creation, save/load, and lifecycle tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from models.project import KitType, NewProjectRequest, ProjectStatus
from services.project_format import ProjectFormatError, read_project_package
from services.projects_manager import ProjectsManager
from services.recent_projects_manager import RecentProjectsManager
from services.settings_manager import SettingsManager
from services.workspace_service import WorkspaceService


@pytest.fixture
def projects_manager(tmp_path: Path) -> ProjectsManager:
    settings = SettingsManager(path=tmp_path / "settings.json")
    settings.load()
    recent = RecentProjectsManager(settings)
    workspace = WorkspaceService(root=tmp_path / "workspace")
    return ProjectsManager(recent, workspace=workspace, application_version="0.2.0")


def _request(output_folder: Path, name: str = "Test FC Home 2026") -> NewProjectRequest:
    return NewProjectRequest(
        project_name=name,
        club_name="Test FC",
        competition="Premier League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(output_folder),
        author="Leigh",
    )


def test_new_project_creates_gjs_package(projects_manager: ProjectsManager, tmp_path: Path) -> None:
    doc = projects_manager.new_project(_request(tmp_path / "out"))
    path = Path(doc.file_path)
    assert path.is_file()
    assert path.suffix == ".gjs"
    assert projects_manager.session.loaded
    assert doc.manifest.project_name == "Test FC Home 2026"
    assert doc.history.entries[0].event.value == "Project Created"


def test_save_and_reload_project(projects_manager: ProjectsManager, tmp_path: Path) -> None:
    projects_manager.new_project(_request(tmp_path / "out"))
    projects_manager.save_project()
    path = projects_manager.session.file_path
    projects_manager.close_project()
    projects_manager.open_project(path)
    assert projects_manager.document is not None
    assert projects_manager.document.manifest.club_name == "Test FC"


def test_save_as_writes_new_file(projects_manager: ProjectsManager, tmp_path: Path) -> None:
    projects_manager.new_project(_request(tmp_path / "out"))
    new_path = tmp_path / "out" / "Renamed.gjs"
    projects_manager.save_project_as(new_path)
    assert new_path.is_file()


def test_duplicate_project(projects_manager: ProjectsManager, tmp_path: Path) -> None:
    projects_manager.new_project(_request(tmp_path / "out"))
    copy = projects_manager.duplicate_project()
    assert copy.manifest.project_name.endswith("(Copy)")
    assert Path(copy.file_path).is_file()


def test_archive_project(projects_manager: ProjectsManager, tmp_path: Path) -> None:
    projects_manager.new_project(_request(tmp_path / "out"))
    projects_manager.archive_project()
    assert projects_manager.document is not None
    assert projects_manager.document.manifest.status == ProjectStatus.ARCHIVED


def test_delete_project_file(projects_manager: ProjectsManager, tmp_path: Path) -> None:
    doc = projects_manager.new_project(_request(tmp_path / "out"))
    path = Path(doc.file_path)
    projects_manager.delete_project_file(path)
    assert not path.is_file()
    assert not projects_manager.session.loaded


def test_open_invalid_file_raises(tmp_path: Path, projects_manager: ProjectsManager) -> None:
    bad = tmp_path / "bad.gjs"
    bad.write_text("not a zip", encoding="utf-8")
    with pytest.raises(ProjectFormatError):
        projects_manager.open_project(bad)


def test_read_project_package_round_trip(projects_manager: ProjectsManager, tmp_path: Path) -> None:
    projects_manager.new_project(_request(tmp_path / "out"))
    path = Path(projects_manager.document.file_path)  # type: ignore[union-attr]
    loaded, _ = read_project_package(path)
    assert loaded.manifest.project_name == "Test FC Home 2026"
