"""Large metric cards for upload preview."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from gui.theme import Theme


class StatCard(QFrame):
    def __init__(
        self,
        label: str,
        value: str = "—",
        *,
        accent: str = Theme.ACCENT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "stat-card")
        self.setMinimumWidth(180)
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        self._value = QLabel(value)
        self._value.setStyleSheet(
            f"font-size: {Theme.FONT_SIZE_HERO}px; font-weight: 700; color: {accent};"
        )
        self._label = QLabel(label)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            f"font-size: {Theme.FONT_SIZE}px; font-weight: 500; color: {Theme.TEXT_SECONDARY};"
        )
        layout.addWidget(self._value)
        layout.addWidget(self._label)
        layout.addStretch()

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def set_accent(self, color: str) -> None:
        self._value.setStyleSheet(
            f"font-size: {Theme.FONT_SIZE_HERO}px; font-weight: 700; color: {color};"
        )
