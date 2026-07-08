"""Reusable empty-state presentation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography


class EmptyState(QFrame):
    def __init__(
        self,
        *,
        icon_name: str = "folder",
        title: str,
        message: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 40, 32, 40)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        glyph = QLabel()
        glyph.setPixmap(icon(icon_name, color=Theme.TEXT_MUTED, size=32).pixmap(32, 32))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setFont(Typography.subheading())
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._message_label = QLabel(message)
        self._message_label.setWordWrap(True)
        self._message_label.setProperty("muted", True)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setMaximumWidth(420)

        layout.addWidget(glyph)
        layout.addWidget(title_label)
        layout.addWidget(self._message_label)

    def set_message(self, message: str) -> None:
        self._message_label.setText(message)
