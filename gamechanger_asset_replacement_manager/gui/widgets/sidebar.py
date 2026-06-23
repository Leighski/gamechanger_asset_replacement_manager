"""Workflow sidebar navigation — extensible for future modules."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from gui.theme import Theme


class NavItem:
    def __init__(self, key: str, label: str, enabled: bool = True) -> None:
        self.key = key
        self.label = label
        self.enabled = enabled


WORKFLOW_ITEMS = [
    NavItem("source", "Source Files"),
    NavItem("catalogue", "Catalogue"),
    NavItem("validation", "Validation"),
    NavItem("preview", "Upload Preview"),
    NavItem("upload", "Upload"),
    NavItem("reports", "Reports"),
]

FUTURE_ITEMS = [
    NavItem("iconik", "Iconik Verification", enabled=False),
    NavItem("fileset", "FileSet Repair", enabled=False),
    NavItem("rename", "Asset Renaming", enabled=False),
    NavItem("metadata", "Metadata Validation", enabled=False),
    NavItem("cfx", "CFX Management", enabled=False),
]


class Sidebar(QFrame):
    page_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {Theme.SIDEBAR};
                border-right: 1px solid {Theme.BORDER};
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(4)

        from PySide6.QtWidgets import QLabel

        wf = QLabel("WORKFLOW")
        wf.setStyleSheet(
            f"color: {Theme.TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        layout.addWidget(wf)
        layout.addSpacing(8)

        self._buttons: dict[str, QPushButton] = {}
        for item in WORKFLOW_ITEMS:
            btn = self._make_nav_button(item)
            layout.addWidget(btn)
            self._buttons[item.key] = btn

        layout.addSpacing(20)
        layout.addWidget(QLabel("FUTURE"))
        layout.addSpacing(8)
        for item in FUTURE_ITEMS:
            btn = self._make_nav_button(item)
            layout.addWidget(btn)

        layout.addStretch()

        self._settings_btn = QPushButton("⚙  Preferences")
        self._settings_btn.setProperty("class", "ghost")
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._settings_btn)

        self._active_key = "source"
        self._set_active("source")

    def _make_nav_button(self, item: NavItem) -> QPushButton:
        btn = QPushButton(item.label)
        btn.setEnabled(item.enabled)
        btn.setCursor(Qt.CursorShape.PointingHandCursor if item.enabled else Qt.CursorShape.ArrowCursor)
        btn.setStyleSheet(self._btn_style(False, item.enabled))
        if item.enabled:
            btn.clicked.connect(lambda checked=False, k=item.key: self._on_click(k))
        else:
            btn.setText(f"{item.label}  · Soon")
        return btn

    def _on_click(self, key: str) -> None:
        self._set_active(key)
        self.page_changed.emit(key)

    def _set_active(self, key: str) -> None:
        self._active_key = key
        for k, btn in self._buttons.items():
            btn.setStyleSheet(self._btn_style(k == key, True))

    @staticmethod
    def _btn_style(active: bool, enabled: bool) -> str:
        if not enabled:
            return f"""
                QPushButton {{
                    text-align: left;
                    padding: 12px 14px;
                    border: none;
                    border-radius: 6px;
                    color: {Theme.TEXT_MUTED};
                    background: transparent;
                }}
            """
        bg = Theme.SIDEBAR_ACTIVE if active else "transparent"
        color = "#FFFFFF" if active else Theme.TEXT_SECONDARY
        weight = "600" if active else "500"
        border = f"border-left: 3px solid {Theme.ACCENT};" if active else "border-left: 3px solid transparent;"
        return f"""
            QPushButton {{
                text-align: left;
                padding: 12px 14px;
                border: none;
                border-radius: 4px;
                color: {color};
                background-color: {bg};
                font-weight: {weight};
                {border}
            }}
            QPushButton:hover {{
                background-color: {Theme.PANEL_ELEVATED};
                color: {Theme.TEXT};
            }}
        """

    def settings_button(self) -> QPushButton:
        return self._settings_btn

    def go_to(self, key: str) -> None:
        if key in self._buttons:
            self._set_active(key)
            self.page_changed.emit(key)
