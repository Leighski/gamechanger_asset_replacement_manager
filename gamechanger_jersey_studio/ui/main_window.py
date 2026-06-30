"""Primary application window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QWidget,
)

from models.settings import WindowGeometry
from services.logging_manager import get_logger, log_unexpected_error, log_window_restored
from services.projects_manager import ProjectsManager
from services.settings_manager import SettingsManager
from services.version_manager import VersionManager
from ui.about_dialog import AboutDialog
from ui.animations import crossfade_stack, fade_in
from ui.dialogs.new_project_wizard import NewProjectWizard
from ui.theme import Theme
from ui.widgets.catalogue_browser import CatalogueBrowserPanel
from ui.widgets.reference_images_panel import ReferenceImagesPanel
from ui.widgets.design_specification_editor import DesignSpecificationEditor
from ui.widgets.vision_analysis_review import VisionAnalysisReviewPanel
from ui.widgets.preview_panel import PreviewPanel
from ui.widgets.project_dashboard import ProjectDashboard
from ui.widgets.project_tree import ProjectTree
from ui.widgets.sidebar import Sidebar
from ui.widgets.status_bar import ApplicationStatusBar
from ui.widgets.toolbar import ApplicationToolBar
from ui.widgets.welcome_screen import WelcomeScreen

logger = get_logger()


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings_manager: SettingsManager,
        projects_manager: ProjectsManager,
        version_manager: VersionManager,
    ) -> None:
        super().__init__()
        self._settings_manager = settings_manager
        self._projects = projects_manager
        self._version_manager = version_manager
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._on_autosave)
        self._preview_render_timer = QTimer(self)
        self._preview_render_timer.setSingleShot(True)
        self._preview_render_timer.setInterval(50)
        self._preview_render_timer.timeout.connect(self._refresh_live_preview)

        info = version_manager.info
        self.setWindowTitle(f"{info.application_name} — {info.branding_line}")
        self.setMinimumSize(1180, 720)
        self.setAcceptDrops(True)

        self._build_menu()
        self._build_toolbar()
        self._build_layout()
        self._status_bar = ApplicationStatusBar(version_manager, self)
        self.setStatusBar(self._status_bar)

        self._restore_window_state()
        self._configure_autosave_timer()
        self._sidebar.select("projects")
        self.refresh_project_ui()

    def _build_menu(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        self._action_new = QAction("&New Project…", self)
        self._action_new.setShortcut(QKeySequence.StandardKey.New)
        self._action_open = QAction("&Open Project…", self)
        self._action_open.setShortcut(QKeySequence.StandardKey.Open)
        self._action_save = QAction("&Save", self)
        self._action_save_as = QAction("Save &As…", self)
        self._action_close = QAction("&Close Project", self)
        self._action_duplicate = QAction("&Duplicate Project", self)
        self._action_archive = QAction("A&rchive Project", self)
        self._action_delete = QAction("&Delete Project File…", self)
        self._action_quit = QAction("&Quit", self)
        self._action_quit.setShortcut(QKeySequence.StandardKey.Quit)

        for action in (
            self._action_new,
            self._action_open,
            self._action_save,
            self._action_save_as,
            self._action_close,
            self._action_duplicate,
            self._action_archive,
            self._action_delete,
        ):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(self._action_quit)

        edit_menu = menu.addMenu("&Edit")
        self._action_undo = QAction("&Undo", self)
        self._action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._action_redo = QAction("&Redo", self)
        self._action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._action_cut = QAction("Cu&t", self)
        self._action_copy = QAction("&Copy", self)
        self._action_paste = QAction("&Paste", self)
        self._action_preferences = QAction("&Preferences…", self)
        for action in (
            self._action_undo,
            self._action_redo,
            self._action_cut,
            self._action_copy,
            self._action_paste,
            self._action_preferences,
        ):
            action.setEnabled(False)
            edit_menu.addAction(action)

        view_menu = menu.addMenu("&View")
        self._action_show_sidebar = QAction("Show &Sidebar", self)
        self._action_show_sidebar.setCheckable(True)
        self._action_show_sidebar.setChecked(True)
        self._action_show_preview = QAction("Show &Preview Panel", self)
        self._action_show_preview.setCheckable(True)
        self._action_show_preview.setChecked(True)
        self._action_show_status = QAction("Show &Status Bar", self)
        self._action_show_status.setCheckable(True)
        self._action_show_status.setChecked(True)
        view_menu.addAction(self._action_show_sidebar)
        view_menu.addAction(self._action_show_preview)
        view_menu.addAction(self._action_show_status)

        project_menu = menu.addMenu("&Project")
        self._action_project_info = QAction("Project &Information", self)
        self._action_project_settings = QAction("Project &Settings", self)
        self._action_export = QAction("&Export Package…", self)
        for action in (
            self._action_project_info,
            self._action_project_settings,
            self._action_export,
        ):
            action.setEnabled(False)
            project_menu.addAction(action)

        tools_menu = menu.addMenu("&Tools")
        self._action_validate = QAction("&Validate Project", self)
        self._action_reports = QAction("Generate &Reports", self)
        self._action_batch = QAction("&Batch Processing", self)
        for action in (self._action_validate, self._action_reports, self._action_batch):
            action.setEnabled(False)
            tools_menu.addAction(action)

        window_menu = menu.addMenu("&Window")
        self._action_minimize = QAction("&Minimize", self)
        minimize_key = "Meta+M" if sys.platform == "darwin" else "Ctrl+M"
        self._action_minimize.setShortcut(QKeySequence(minimize_key))
        self._action_zoom = QAction("&Zoom", self)
        self._action_zoom.setEnabled(False)
        window_menu.addAction(self._action_minimize)
        window_menu.addAction(self._action_zoom)

        help_menu = menu.addMenu("&Help")
        self._action_docs = QAction("&Documentation", self)
        self._action_release_notes = QAction("&Release Notes", self)
        self._action_about = QAction("&About Gamechanger Jersey Studio", self)
        help_menu.addAction(self._action_docs)
        help_menu.addAction(self._action_release_notes)
        help_menu.addSeparator()
        help_menu.addAction(self._action_about)

        self._action_new.triggered.connect(self._new_project)
        self._action_open.triggered.connect(self._open_project)
        self._action_save.setShortcut(QKeySequence.StandardKey.Save)
        self._action_save.triggered.connect(self._save_project)
        self._action_save_as.triggered.connect(self._save_project_as)
        self._action_close.triggered.connect(self._close_project)
        self._action_duplicate.triggered.connect(self._duplicate_project)
        self._action_archive.triggered.connect(self._archive_project)
        self._action_delete.triggered.connect(self._delete_project)
        self._action_quit.triggered.connect(self.close)
        self._action_minimize.triggered.connect(self.showMinimized)
        self._action_docs.triggered.connect(self._open_documentation)
        self._action_release_notes.triggered.connect(self._open_release_notes)
        self._action_about.triggered.connect(self._show_about)

    def _build_toolbar(self) -> None:
        self._toolbar = ApplicationToolBar(self)
        self.addToolBar(self._toolbar)
        self._toolbar.new_project.connect(self._new_project)
        self._toolbar.open_project.connect(self._open_project)
        self._toolbar.save_project.connect(self._save_project)
        self._toolbar.settings.connect(lambda: self._sidebar.select("settings"))
        self._toolbar.help_requested.connect(self._show_about)

    def _build_layout(self) -> None:
        central = QWidget(self)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = Sidebar(self)
        self._preview = PreviewPanel(self)
        self._preview.set_renderer_service(self._projects.live_renderer_service)
        self._tree = ProjectTree(self)
        self._dashboard = ProjectDashboard(self)
        self._design_editor = DesignSpecificationEditor(self)
        self._reference_panel = ReferenceImagesPanel(self)
        self._vision_review = VisionAnalysisReviewPanel(self)
        self._catalogue_browser = CatalogueBrowserPanel(self)
        self._welcome = WelcomeScreen(self)

        self._design_editor.set_service(self._projects.design_specification_service)
        self._reference_panel.set_service(self._projects.reference_image_service)
        self._catalogue_browser.set_manager(self._projects.catalogue_manager)
        self._vision_review.set_services(
            self._projects.vision_analysis_service,
            self._projects.reference_image_service,
            self._projects.interpretation_service,
            self._projects.design_specification_service,
        )
        self._dashboard.set_design_service(self._projects.design_specification_service)
        self._dashboard.set_reference_service(self._projects.reference_image_service)
        self._tree.set_design_service(self._projects.design_specification_service)
        self._tree.set_reference_service(self._projects.reference_image_service)

        self._workspace_stack = QStackedWidget()
        self._workspace_stack.addWidget(self._welcome)
        project_page = QWidget()
        project_layout = QHBoxLayout(project_page)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(0)
        centre_split = QSplitter(Qt.Orientation.Horizontal)
        centre_split.addWidget(self._tree)

        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self._dashboard)
        self._content_stack.addWidget(self._design_editor)
        self._content_stack.addWidget(self._reference_panel)
        self._content_stack.addWidget(self._vision_review)
        self._content_stack.addWidget(self._catalogue_browser)
        centre_split.addWidget(self._content_stack)
        centre_split.setStretchFactor(0, 1)
        centre_split.setStretchFactor(1, 3)
        centre_split.setHandleWidth(1)
        centre_split.setStyleSheet(f"QSplitter::handle {{ background: {Theme.BORDER}; }}")
        project_layout.addWidget(centre_split)
        self._workspace_stack.addWidget(project_page)

        self._main_split = QSplitter(Qt.Orientation.Horizontal)
        self._main_split.addWidget(self._workspace_stack)
        self._main_split.addWidget(self._preview)
        self._main_split.setStretchFactor(0, 4)
        self._main_split.setStretchFactor(1, 2)
        self._main_split.setHandleWidth(1)
        self._main_split.setStyleSheet(f"QSplitter::handle {{ background: {Theme.BORDER}; }}")

        root.addWidget(self._sidebar)
        root.addWidget(self._main_split, stretch=1)
        self.setCentralWidget(central)

        self._sidebar.page_selected.connect(self._on_nav_selected)
        self._welcome.new_project.connect(self._new_project)
        self._welcome.open_project.connect(self._open_project)
        self._welcome.documentation.connect(self._open_documentation)
        self._welcome.open_recent.connect(self._open_project_path)
        self._welcome.remove_recent.connect(self._remove_recent)
        self._welcome.duplicate_recent.connect(self._duplicate_project_path)
        self._welcome.archive_recent.connect(self._archive_project_path)

        self._design_editor.specification_changed.connect(self._on_design_spec_changed)
        self._reference_panel.images_changed.connect(self._on_reference_images_changed)
        self._reference_panel.analyse_requested.connect(self._on_analyse_requested)
        self._vision_review.analysis_changed.connect(self._on_vision_analysis_changed)
        self._tree.section_selected.connect(self._on_tree_section_selected)
        self._dashboard.references_clicked.connect(lambda: self._show_content_page(2))
        self._action_undo.triggered.connect(self._undo_design_spec)
        self._action_redo.triggered.connect(self._redo_design_spec)
        self._action_show_sidebar.toggled.connect(self._sidebar.setVisible)
        self._action_show_preview.toggled.connect(self._preview.setVisible)
        self._action_show_status.toggled.connect(self.statusBar().setVisible)

    def refresh_project_ui(self) -> None:
        session = self._projects.session
        document = session.document
        loaded = session.loaded

        if loaded and document is not None:
            crossfade_stack(self._workspace_stack, 1)
            self._tree.set_project(document)
            self._dashboard.set_project(document)
            self._design_editor.set_project(document)
            self._reference_panel.set_project(document)
            self._vision_review.set_project(document)
            self._preview.set_project(document)
            self._status_bar.set_project(
                document.manifest.project_name,
                document.manifest.status.value,
            )
            self._status_bar.set_autosave("Autosave: enabled")
        else:
            crossfade_stack(self._workspace_stack, 0)
            self._tree.set_project(None)
            self._dashboard.clear()
            self._design_editor.set_project(None)
            self._reference_panel.set_project(None)
            self._vision_review.set_project(None)
            self._preview.set_project(None)
            self._status_bar.set_project("", "")
            self._status_bar.set_autosave("Autosave: idle")
            self._welcome.set_recent_entries(self._projects.recent_projects.entries)

        self._toolbar.set_project_loaded(loaded)
        self._update_action_states()
        self._update_undo_redo_states()

    def _update_undo_redo_states(self) -> None:
        loaded = self._projects.session.loaded
        service = self._projects.design_specification_service
        self._action_undo.setEnabled(loaded and service.can_undo())
        self._action_redo.setEnabled(loaded and service.can_redo())

    def _update_action_states(self) -> None:
        loaded = self._projects.session.loaded
        self._action_save.setEnabled(loaded)
        self._action_save_as.setEnabled(loaded)
        self._action_close.setEnabled(loaded)
        self._action_duplicate.setEnabled(loaded)
        self._action_archive.setEnabled(loaded)
        self._action_delete.setEnabled(loaded)

    def _configure_autosave_timer(self) -> None:
        minutes = self._settings_manager.settings.autosave_interval_minutes
        self._autosave_timer.start(max(1, minutes) * 60 * 1000)

    def _on_autosave(self) -> None:
        if not self._projects.session.loaded:
            return
        try:
            path = self._projects.run_autosave()
            if path:
                self._status_bar.set_autosave("Autosave: saved")
        except Exception as exc:
            log_unexpected_error(exc, context="Autosave")
            self._status_bar.set_autosave("Autosave: error")

    def _on_nav_selected(self, key: str) -> None:
        labels = {
            "projects": "Projects",
            "design": "Design",
            "libraries": "Libraries",
            "preview": "Preview",
            "validation": "Validation",
            "reports": "Reports",
            "settings": "Settings",
        }
        self._status_bar.set_ready(f"{labels.get(key, key)} — Ready")
        if not self._projects.session.loaded:
            return
        if key == "design":
            self._show_content_page(1)
        elif key == "projects":
            self._show_content_page(0)
        elif key == "validation":
            self._show_content_page(3)
        elif key == "libraries":
            self._show_content_page(4)

    def _show_content_page(self, index: int) -> None:
        self._content_stack.setCurrentIndex(index)

    def _on_analyse_requested(self, image_id: str) -> None:
        self._sidebar.select("validation")
        self._show_content_page(3)
        self._vision_review.run_analysis(image_id)

    def _on_vision_analysis_changed(self) -> None:
        document = self._projects.session.document
        if document is None:
            return
        self._tree.set_project(document)
        self._dashboard.set_project(document)
        self._reference_panel.set_project(document)
        self._design_editor.set_project(document)

    def _on_tree_section_selected(self, section: str) -> None:
        if section == "references":
            self._show_content_page(2)

    def _on_reference_images_changed(self) -> None:
        document = self._projects.session.document
        if document is None:
            return
        self._tree.set_project(document)
        self._dashboard.set_project(document)

    def _on_design_spec_changed(self) -> None:
        document = self._projects.session.document
        if document is None:
            return
        self._tree.set_project(document)
        self._dashboard.set_project(document)
        self._update_undo_redo_states()
        self._schedule_preview_refresh()

    def _schedule_preview_refresh(self) -> None:
        self._preview_render_timer.start()

    def _refresh_live_preview(self) -> None:
        document = self._projects.session.document
        if document is None:
            return
        self._preview.set_project(document)

    def _undo_design_spec(self) -> None:
        document = self._projects.session.document
        if document is None:
            return
        service = self._projects.design_specification_service
        spec = service.undo(document, user=document.manifest.author or "Operator")
        if spec is None:
            return
        self._design_editor.set_project(document)
        self._on_design_spec_changed()

    def _redo_design_spec(self) -> None:
        document = self._projects.session.document
        if document is None:
            return
        service = self._projects.design_specification_service
        spec = service.redo(document, user=document.manifest.author or "Operator")
        if spec is None:
            return
        self._design_editor.set_project(document)
        self._on_design_spec_changed()

    def _open_documentation(self) -> None:
        docs = Path(__file__).resolve().parent.parent / "docs"
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs)))

    def _open_release_notes(self) -> None:
        notes = Path(__file__).resolve().parent.parent / "docs" / "RELEASE_NOTES.md"
        if notes.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(notes)))
        else:
            QMessageBox.information(
                self,
                "Release Notes",
                "Release notes will be available in docs/RELEASE_NOTES.md.",
            )

    def _new_project(self) -> None:
        wizard = NewProjectWizard(
            default_output_folder=str(self._projects.default_project_folder()),
            parent=self,
        )
        if wizard.exec() != NewProjectWizard.DialogCode.Accepted:
            return
        request = wizard.request()
        if request is None:
            return
        try:
            self._projects.new_project(request)
            self.refresh_project_ui()
            self._status_bar.set_ready("Project created")
        except Exception as exc:
            log_unexpected_error(exc, context="New project")
            QMessageBox.critical(self, "New Project", str(exc))

    def _open_project(self) -> None:
        start = str(self._projects.default_project_folder())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            start,
            "Gamechanger Jersey Studio (*.gjs)",
        )
        if path:
            self._open_project_path(path)

    def _open_project_path(self, path: str) -> None:
        try:
            if self._projects.session.loaded:
                self._projects.close_project(save_if_dirty=True)
            self._projects.open_project(path)
            self.refresh_project_ui()
            self._status_bar.set_ready("Project opened")
        except Exception as exc:
            log_unexpected_error(exc, context="Open project")
            QMessageBox.critical(self, "Open Project", str(exc))

    def _save_project(self) -> None:
        try:
            self._projects.save_project()
            self.refresh_project_ui()
            self._status_bar.set_autosave("Autosave: saved")
        except Exception as exc:
            log_unexpected_error(exc, context="Save project")
            QMessageBox.critical(self, "Save Project", str(exc))

    def _save_project_as(self) -> None:
        start = str(self._projects.default_project_folder())
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            start,
            "Gamechanger Jersey Studio (*.gjs)",
        )
        if not path:
            return
        try:
            self._projects.save_project_as(path)
            self.refresh_project_ui()
        except Exception as exc:
            log_unexpected_error(exc, context="Save project as")
            QMessageBox.critical(self, "Save Project As", str(exc))

    def _close_project(self) -> None:
        if not self._projects.session.loaded:
            return
        try:
            self._projects.close_project(save_if_dirty=True)
            self.refresh_project_ui()
            self._status_bar.set_ready("Project closed")
        except Exception as exc:
            log_unexpected_error(exc, context="Close project")
            QMessageBox.critical(self, "Close Project", str(exc))

    def _duplicate_project(self) -> None:
        try:
            self._projects.duplicate_project()
            self.refresh_project_ui()
        except Exception as exc:
            log_unexpected_error(exc, context="Duplicate project")
            QMessageBox.critical(self, "Duplicate Project", str(exc))

    def _duplicate_project_path(self, path: str) -> None:
        try:
            self._projects.duplicate_project(path)
            self.refresh_project_ui()
        except Exception as exc:
            log_unexpected_error(exc, context="Duplicate project")
            QMessageBox.critical(self, "Duplicate Project", str(exc))

    def _archive_project(self) -> None:
        try:
            self._projects.archive_project()
            self.refresh_project_ui()
        except Exception as exc:
            log_unexpected_error(exc, context="Archive project")
            QMessageBox.critical(self, "Archive Project", str(exc))

    def _archive_project_path(self, path: str) -> None:
        try:
            if self._projects.session.loaded:
                self._projects.close_project(save_if_dirty=True)
            self._projects.open_project(path)
            self._projects.archive_project()
            self.refresh_project_ui()
        except Exception as exc:
            log_unexpected_error(exc, context="Archive project")
            QMessageBox.critical(self, "Archive Project", str(exc))

    def _delete_project(self) -> None:
        document = self._projects.session.document
        if document is None or not document.file_path:
            return
        answer = QMessageBox.question(
            self,
            "Delete Project",
            f"Permanently delete project file?\n\n{document.file_path}",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._projects.delete_project_file(document.file_path)
            self.refresh_project_ui()
        except Exception as exc:
            log_unexpected_error(exc, context="Delete project")
            QMessageBox.critical(self, "Delete Project", str(exc))

    def _remove_recent(self, path: str) -> None:
        self._projects.recent_projects.remove(path)
        self.refresh_project_ui()

    def _show_about(self) -> None:
        AboutDialog(self._version_manager, self).exec()

    def _restore_window_state(self) -> None:
        geom = self._settings_manager.settings.window
        self.resize(geom.width, geom.height)
        self.move(geom.x, geom.y)
        if geom.maximised:
            self.showMaximized()
        log_window_restored(geom.width, geom.height, geom.x, geom.y, geom.maximised)

    def _capture_window_state(self) -> WindowGeometry:
        maximised = self.isMaximized()
        if maximised:
            normal = self.normalGeometry()
            return WindowGeometry(
                width=normal.width(),
                height=normal.height(),
                x=normal.x(),
                y=normal.y(),
                maximised=True,
            )
        return WindowGeometry(
            width=self.width(),
            height=self.height(),
            x=self.x(),
            y=self.y(),
            maximised=False,
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and self._projects.session.loaded:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if not self._projects.session.loaded:
            return
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            document = self._projects.session.document
            if document is not None:
                user = document.manifest.author or "Operator"
                self._projects.reference_image_service.import_files(document, paths, user=user)
                self._on_reference_images_changed()
                self._show_content_page(2)
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            if self._projects.session.loaded:
                self._projects.close_project(save_if_dirty=True)
            geom = self._capture_window_state()
            settings = self._settings_manager.settings.model_copy(update={"window": geom})
            self._settings_manager._settings = settings
            self._settings_manager.save()
        except Exception as exc:
            log_unexpected_error(exc, context="Application close")
            QMessageBox.warning(
                self,
                "Shutdown",
                "Some settings could not be saved, but the application will close.",
            )
        event.accept()
