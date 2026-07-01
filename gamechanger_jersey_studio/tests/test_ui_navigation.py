"""Regression tests for menu actions and navigation pathways."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QDialog, QFileDialog

pytestmark = pytest.mark.skipif(
    os.environ.get("GJS_SKIP_QT_TESTS") == "1",
    reason="Qt GUI tests disabled",
)


@pytest.fixture
def main_window(qapp, tmp_path: Path):  # noqa: ARG001
    from services.projects_manager import ProjectsManager
    from services.recent_projects_manager import RecentProjectsManager
    from services.settings_manager import SettingsManager
    from services.version_manager import VersionManager
    from ui.main_window import MainWindow

    settings_path = tmp_path / "settings.json"
    settings = SettingsManager(settings_path)
    settings.load()
    recent = RecentProjectsManager(settings)
    projects = ProjectsManager(recent, settings_manager=settings, application_version="1.0.0-rc.1")
    window = MainWindow(settings, projects, VersionManager())
    yield window
    window.close()


def test_file_new_project_opens_wizard(main_window) -> None:
    with patch("ui.main_window.NewProjectWizard") as mock_cls:
        wizard = MagicMock()
        wizard.exec.return_value = QDialog.DialogCode.Rejected
        mock_cls.return_value = wizard
        main_window._new_project()
        mock_cls.assert_called_once()
        wizard.exec.assert_called_once()


def test_file_new_project_creates_project(main_window, tmp_path: Path) -> None:
    from models.project import KitType, NewProjectRequest

    request = NewProjectRequest(
        project_name="Nav Test",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        build_profile="Gamechanger Broadcast",
        output_folder=str(tmp_path),
        author="Tester",
    )
    with patch("ui.main_window.NewProjectWizard") as mock_cls:
        wizard = MagicMock()
        wizard.exec.return_value = QDialog.DialogCode.Accepted
        wizard.request.return_value = request
        mock_cls.return_value = wizard
        main_window._new_project()
    assert main_window._projects.session.loaded


def test_file_open_project_dialog(main_window) -> None:
    with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")):
        main_window._open_project()


def test_file_save_without_project(main_window) -> None:
    with patch("ui.main_window.QMessageBox.critical"):
        main_window._save_project()


def test_file_save_as_cancelled(main_window) -> None:
    with patch.object(QFileDialog, "getSaveFileName", return_value=("", "")):
        main_window._save_project_as()


def test_nav_libraries(main_window, tmp_path: Path) -> None:
    from models.project import KitType, NewProjectRequest

    request = NewProjectRequest(
        project_name="Nav Lib",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        build_profile="Gamechanger Broadcast",
        output_folder=str(tmp_path),
        author="Tester",
    )
    main_window._projects.new_project(request)
    main_window.refresh_project_ui()
    main_window._on_nav_selected("libraries")
    assert main_window._content_stack.currentIndex() == 4


def test_nav_learning(main_window) -> None:
    main_window._on_nav_selected("learning")
    assert main_window._content_stack.currentIndex() == 6


def test_nav_production(main_window) -> None:
    main_window._on_nav_selected("production")
    assert main_window._content_stack.currentIndex() == 5


def test_nav_settings(main_window) -> None:
    main_window._on_nav_selected("settings")
    assert main_window._production._tabs.currentIndex() == 3


def test_help_about_dialog(main_window) -> None:
    with patch("ui.main_window.AboutDialog") as mock_cls:
        dialog = MagicMock()
        mock_cls.return_value = dialog
        main_window._show_about()
        dialog.exec.assert_called_once()


def test_tools_validate_project_navigates(main_window) -> None:
    main_window._validate_project()
    assert main_window._content_stack.currentIndex() == 3


def test_tools_production_reports(main_window) -> None:
    main_window._open_production_reports()
    assert main_window._content_stack.currentIndex() == 5


def test_menu_action_validation_passes(main_window) -> None:
    assert main_window._action_new.isEnabled()
    assert main_window._action_open.isEnabled()
    assert main_window._action_about.isEnabled()


def test_action_validation_disables_missing_callback() -> None:
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QWidget

    from ui.action_validation import validate_action_callbacks

    owner = QWidget()
    action = QAction("Broken", owner)
    action.setEnabled(True)
    errors = validate_action_callbacks(owner, [(action, "_nonexistent_method")])
    assert len(errors) == 1
    assert not action.isEnabled()


def test_new_project_wizard_importable() -> None:
    from ui.dialogs.new_project_wizard import NewProjectWizard

    assert NewProjectWizard is not None
