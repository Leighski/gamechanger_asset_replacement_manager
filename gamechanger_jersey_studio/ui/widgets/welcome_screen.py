"""Welcome screen when no project is loaded."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.version import APP_NAME, BUILD_LABEL, VERSION_LABEL
from models.settings import RecentProjectEntry
from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography
from ui.widgets.recent_projects_panel import RecentProjectsPanel


class WelcomeScreen(QFrame):
    new_project = Signal()
    open_project = Signal()
    documentation = Signal()
    open_recent = Signal(str)
    remove_recent = Signal(str)
    duplicate_recent = Signal(str)
    archive_recent = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        root.setSpacing(Theme.SPACING_LG)

        hero = QVBoxLayout()
        hero.setSpacing(Theme.SPACING_SM)

        brand_row = QHBoxLayout()
        brand_icon = QLabel()
        brand_icon.setPixmap(icon("design", color=Theme.ACCENT, size=36).pixmap(36, 36))
        title = QLabel(APP_NAME)
        title.setProperty("hero", True)
        title.setFont(Typography.display())
        brand_row.addWidget(brand_icon)
        brand_row.addWidget(title)
        brand_row.addStretch(1)

        subtitle = QLabel("Professional jersey design workspace")
        subtitle.setProperty("muted", True)
        subtitle.setFont(Typography.subheading())

        version_line = QLabel(f"{VERSION_LABEL}  ·  {BUILD_LABEL}")
        version_line.setProperty("muted", True)
        version_line.setFont(Typography.caption())

        hero.addLayout(brand_row)
        hero.addWidget(subtitle)
        hero.addWidget(version_line)

        actions = QHBoxLayout()
        actions.setSpacing(Theme.SPACING_MD)
        self._btn_new = QPushButton("  Create New Project")
        self._btn_new.setProperty("primary", True)
        self._btn_new.setIcon(icon("new", color="#FFFFFF"))
        self._btn_open = QPushButton("  Open Existing Project")
        self._btn_open.setIcon(icon("open", color=Theme.TEXT))
        self._btn_docs = QPushButton("  Documentation")
        self._btn_docs.setIcon(icon("doc", color=Theme.TEXT))
        actions.addWidget(self._btn_new)
        actions.addWidget(self._btn_open)
        actions.addWidget(self._btn_docs)
        actions.addStretch(1)

        self._recent = RecentProjectsPanel(self)
        self._recent.setObjectName("panel")

        root.addLayout(hero)
        root.addLayout(actions)
        root.addWidget(self._recent, stretch=1)

        self._btn_new.clicked.connect(self.new_project.emit)
        self._btn_open.clicked.connect(self.open_project.emit)
        self._btn_docs.clicked.connect(self.documentation.emit)
        self._recent.open_requested.connect(self.open_recent.emit)
        self._recent.remove_requested.connect(self.remove_recent.emit)
        self._recent.duplicate_requested.connect(self.duplicate_recent.emit)
        self._recent.archive_requested.connect(self.archive_recent.emit)

    def set_recent_entries(self, entries: list[RecentProjectEntry]) -> None:
        self._recent.set_entries(entries)
