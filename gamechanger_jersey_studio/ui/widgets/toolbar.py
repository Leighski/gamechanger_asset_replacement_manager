"""Application toolbar."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QToolBar, QWidget

from ui.icons import icon, icon_size
from ui.theme import Theme


class ApplicationToolBar(QToolBar):
    new_project = Signal()
    open_project = Signal()
    save_project = Signal()
    settings = Signal()
    help_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Main Toolbar", parent)
        self.setMovable(False)
        self.setIconSize(icon_size(18))
        self.setStyleSheet(f"QToolBar {{ spacing: 8px; }}")

        self._action_new = self.addAction(icon("new", color=Theme.TEXT), "New Project")
        self._action_open = self.addAction(icon("open", color=Theme.TEXT), "Open")
        self._action_save = self.addAction(icon("save", color=Theme.TEXT), "Save")
        self.addSeparator()
        self._action_settings = self.addAction(icon("settings", color=Theme.TEXT), "Settings")
        self._action_help = self.addAction(icon("help", color=Theme.TEXT), "Help")

        self._action_new.triggered.connect(self.new_project.emit)
        self._action_open.triggered.connect(self.open_project.emit)
        self._action_save.triggered.connect(self.save_project.emit)
        self._action_settings.triggered.connect(self.settings.emit)
        self._action_help.triggered.connect(self.help_requested.emit)

    def set_project_loaded(self, loaded: bool) -> None:
        self._action_save.setEnabled(loaded)
