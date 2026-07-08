"""Left navigation panel with icons and keyboard shortcuts."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QVBoxLayout

from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography


NAV_ITEMS = (
    ("projects", "Projects", "projects", "Ctrl+1"),
    ("design", "Design", "design", "Ctrl+2"),
    ("libraries", "Libraries", "libraries", "Ctrl+3"),
    ("preview", "Preview", "preview", "Ctrl+4"),
    ("validation", "Validation", "validation", "Ctrl+5"),
    ("production", "Production", "activity", "Ctrl+6"),
    ("learning", "Learning", "doc", "Ctrl+7"),
    ("settings", "Settings", "settings", "Ctrl+8"),
)


class Sidebar(QFrame):
    page_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(232)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 22, 14, 22)
        layout.setSpacing(6)

        heading = QLabel("WORKSPACE")
        heading.setFont(Typography.caption())
        heading.setStyleSheet(
            f"color: {Theme.TEXT_MUTED}; font-weight: 700; letter-spacing: 1.2px;"
        )
        layout.addWidget(heading)
        layout.addSpacing(10)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        for index, (key, label, icon_name, shortcut) in enumerate(NAV_ITEMS, start=1):
            btn = QPushButton(f"  {label}")
            btn.setProperty("nav", True)
            btn.setProperty("icon_name", icon_name)
            btn.setCheckable(True)
            btn.setIcon(icon(icon_name, color=Theme.TEXT_MUTED))
            btn.setIconSize(icon(icon_name).pixmap(18, 18).size())
            btn.toggled.connect(lambda checked, b=btn: self._update_nav_icon(b, checked))
            btn.clicked.connect(lambda checked=False, k=key: self._on_click(k))
            btn.setToolTip(f"{label} ({shortcut})")
            self._group.addButton(btn)
            self._buttons[key] = btn
            layout.addWidget(btn)

            sc = QShortcut(QKeySequence(shortcut), self)
            sc.activated.connect(lambda k=key: self.select(k))

        self._buttons["projects"].setChecked(True)
        layout.addStretch(1)

        hint = QLabel("Ctrl+1–8 navigate")
        hint.setProperty("muted", True)
        hint.setFont(Typography.caption())
        layout.addWidget(hint)

    def _update_nav_icon(self, button: QPushButton, checked: bool) -> None:
        icon_name = button.property("icon_name") or "projects"
        color = Theme.ACCENT if checked else Theme.TEXT_MUTED
        button.setIcon(icon(icon_name, color=color))

    def _on_click(self, key: str) -> None:
        self.page_selected.emit(key)

    def select(self, key: str) -> None:
        btn = self._buttons.get(key)
        if btn is not None:
            btn.setChecked(True)
            self._update_nav_icon(btn, True)
            self.page_selected.emit(key)
