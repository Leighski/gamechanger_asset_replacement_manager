"""Application controller — startup, shutdown, and lifecycle."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from services.logging_manager import (
    configure_logging,
    install_exception_hooks,
    log_application_closed,
    log_application_started,
    log_unexpected_error,
)
from services.projects_manager import ProjectsManager
from services.recent_projects_manager import RecentProjectsManager
from services.settings_manager import SettingsManager
from services.version_manager import VersionManager
from ui.animations import fade_in
from ui.main_window import MainWindow
from ui.splash_screen import SplashScreen
from ui.theme import Theme


class ApplicationController:
    """Coordinates application startup and shutdown."""

    SPLASH_DURATION_MS = 2000

    def __init__(self, argv: list[str] | None = None) -> None:
        self._argv = argv if argv is not None else sys.argv
        self._app: QApplication | None = None
        self._main_window: MainWindow | None = None
        self._splash: SplashScreen | None = None

        self.settings_manager = SettingsManager()
        self.version_manager = VersionManager()
        self.recent_projects_manager = RecentProjectsManager(self.settings_manager)
        self.projects_manager = ProjectsManager(
            self.recent_projects_manager,
            settings_manager=self.settings_manager,
            application_version=self.version_manager.info.version,
        )

    def run(self) -> int:
        configure_logging()
        install_exception_hooks()
        log_application_started(self.version_manager.summary_line())

        try:
            self._app = QApplication(self._argv)
            self._app.setApplicationName(self.version_manager.info.application_name)
            self._app.setApplicationVersion(self.version_manager.info.version)
            Theme.apply(self._app)

            self.settings_manager.load()

            self._splash = SplashScreen()
            self._splash.finished.connect(self._show_main_window)
            self._splash.start(self.SPLASH_DURATION_MS)

            return self._app.exec()
        except Exception as exc:
            log_unexpected_error(exc, context="Application startup")
            self._show_fatal_error(str(exc))
            return 1
        finally:
            log_application_closed()

    def _show_main_window(self) -> None:
        if self._app is None:
            return
        try:
            self._main_window = MainWindow(
                self.settings_manager,
                self.projects_manager,
                self.version_manager,
            )
            self._main_window.show()
            fade_in(self._main_window, duration_ms=240)
            self._check_recovery()
        except Exception as exc:
            log_unexpected_error(exc, context="Showing main window")
            self._show_fatal_error(str(exc))

    def _check_recovery(self) -> None:
        if self._main_window is None:
            return
        candidates = self.projects_manager.autosave_service.discover_recovery_candidates()
        if not candidates:
            return
        from ui.dialogs.recovery_dialog import RecoveryDialog

        dialog = RecoveryDialog(candidates, self._main_window)
        if dialog.exec() != RecoveryDialog.DialogCode.Accepted:
            for candidate in candidates:
                self.projects_manager.workspace_service.clear_recovery(candidate.project_id)
            return
        selected = dialog.selected()
        if selected is None:
            return
        try:
            self.projects_manager.restore_recovery(
                selected.recovery_path,
                selected.primary_path,
                selected.project_name,
            )
            self._main_window.refresh_project_ui()
        except Exception as exc:
            log_unexpected_error(exc, context="Recovery restore")
            QMessageBox.warning(
                self._main_window,
                "Recovery",
                f"Could not restore recovery copy.\n\n{exc}",
            )

    def _show_fatal_error(self, message: str) -> None:
        if QApplication.instance() is None:
            QApplication([])
        QMessageBox.critical(
            None,
            "Gamechanger Jersey Studio",
            f"An unexpected error occurred.\n\n{message}\n\nSee logs/application.log for details.",
        )
