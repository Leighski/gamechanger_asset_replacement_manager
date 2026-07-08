"""Top dashboard header with live operational status."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app import APP_NAME, APP_VERSION
from gui.theme import Theme


class DashboardHeader(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {Theme.PANEL};
                border-bottom: 1px solid {Theme.BORDER};
            }}
            """
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(24)

        left = QVBoxLayout()
        left.setSpacing(4)
        self._title = QLabel(APP_NAME)
        self._title.setStyleSheet(
            f"font-size: {Theme.FONT_SIZE_TITLE}px; font-weight: 700; color: {Theme.TEXT};"
        )
        self._version = QLabel(f"v{APP_VERSION}")
        self._version.setProperty("class", "muted")
        left.addWidget(self._title)
        left.addWidget(self._version)
        root.addLayout(left, stretch=2)

        self._aws = self._metric("AWS", "—")
        self._catalogue = self._metric("Catalogue", "—")
        self._files = self._metric("Files", "0")
        self._status = self._metric("Status", "IDLE")

        for box in (self._aws, self._catalogue, self._files, self._status):
            root.addWidget(box, stretch=1)

    def _metric(self, label: str, value: str) -> QWidget:
        wrap = QVBoxLayout()
        wrap.setSpacing(2)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {Theme.TEXT_MUTED}; letter-spacing: 1px;"
        )
        val = QLabel(value)
        val.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {Theme.TEXT};")
        wrap.addWidget(lbl)
        wrap.addWidget(val)
        container = QWidget()
        container.setLayout(wrap)
        container._value_label = val  # type: ignore[attr-defined]
        return container

    def _set_metric(self, container: QWidget, text: str, color: str | None = None) -> None:
        lbl: QLabel = container._value_label  # type: ignore[attr-defined]
        lbl.setText(text)
        if color:
            lbl.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {color};")

    def update_status(
        self,
        *,
        aws_profile: str,
        catalogue: str,
        files_count: int,
        ready_state: str,
        ready_color: str | None = None,
    ) -> None:
        self._set_metric(self._aws, aws_profile)
        self._set_metric(self._catalogue, catalogue)
        self._set_metric(self._files, str(files_count))
        color = ready_color or Theme.TEXT
        if ready_state.upper() == "READY":
            color = Theme.SUCCESS
        elif ready_state.upper() in ("ERROR", "FAILED"):
            color = Theme.ERROR
        elif ready_state.upper() in ("WARNING", "VALIDATING", "UPLOADING", "SCANNING"):
            color = Theme.WARNING
        self._set_metric(self._status, ready_state.upper(), color)
