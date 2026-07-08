"""UI component tests."""

from __future__ import annotations

import os

import pytest

from core.version import APP_NAME, BUILD_LABEL, VERSION_LABEL
from ui.typography import Typography

pytestmark = pytest.mark.skipif(
    os.environ.get("GJS_SKIP_QT_TESTS") == "1",
    reason="Qt GUI tests disabled",
)


def test_typography_font_sizes() -> None:
    assert Typography.body().pointSize() == Typography.SIZE_BODY
    assert Typography.heading().pointSize() == Typography.SIZE_HEADING
    assert Typography.display().pointSize() == Typography.SIZE_DISPLAY


def test_icon_returns_qicon(qapp) -> None:  # noqa: ARG001
    from ui.icons import icon

    result = icon("projects")
    assert not result.isNull()


def test_empty_state_message(qapp) -> None:  # noqa: ARG001
    from ui.widgets.empty_state import EmptyState

    widget = EmptyState(
        icon_name="folder",
        title="No items",
        message="Initial message.",
    )
    widget.set_message("Updated message.")
    assert widget._message_label.text() == "Updated message."


def test_design_editor_loads_project(qapp) -> None:  # noqa: ARG001
    from models.project import KitType, ProjectDocument, ProjectManifest
    from services.design_specification_service import DesignSpecificationService
    from ui.widgets.design_specification_editor import DesignSpecificationEditor

    manifest = ProjectManifest(
        project_name="Test",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Leigh",
    )
    document = ProjectDocument(manifest=manifest)
    service = DesignSpecificationService(application_version="1.0.0-alpha.4")
    editor = DesignSpecificationEditor()
    editor.set_service(service)
    editor.set_project(document)
    assert editor.isEnabled()


def test_version_branding_constants() -> None:
    assert APP_NAME == "Gamechanger Jersey Studio"
    assert "RC1" in VERSION_LABEL
    assert BUILD_LABEL == "Build 014"


def test_main_window_instantiates(qapp) -> None:  # noqa: ARG001
    from services.projects_manager import ProjectsManager
    from services.recent_projects_manager import RecentProjectsManager
    from services.settings_manager import SettingsManager
    from services.version_manager import VersionManager
    from ui.main_window import MainWindow

    settings = SettingsManager()
    settings.load()
    recent = RecentProjectsManager(settings)
    projects = ProjectsManager(recent, application_version="1.0.0-alpha.5")
    window = MainWindow(settings, projects, VersionManager())
    assert window.menuBar() is not None
    assert window.statusBar() is not None
