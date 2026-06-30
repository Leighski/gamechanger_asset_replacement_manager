"""Component card for the catalogue browser grid."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from models.component_catalogue import CatalogueComponent, ComponentStatus
from ui.theme import Theme
from ui.typography import Typography


class ComponentCard(QFrame):
    activated = Signal(str, str)  # component_id, category

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._component: CatalogueComponent | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD)
        layout.setSpacing(Theme.SPACING_SM)

        self._thumb = QLabel()
        self._thumb.setFixedHeight(120)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(f"background: {Theme.PANEL_ELEVATED}; border-radius: {Theme.RADIUS_SM}px;")

        self._name = QLabel("—")
        self._name.setFont(Typography.subheading())
        self._name.setWordWrap(True)

        self._meta = QLabel()
        self._meta.setFont(Typography.caption())
        self._meta.setProperty("muted", True)
        self._meta.setWordWrap(True)

        self._status = QLabel()
        self._status.setFont(Typography.caption())

        layout.addWidget(self._thumb)
        layout.addWidget(self._name)
        layout.addWidget(self._meta)
        layout.addWidget(self._status)

    def set_component(self, component: CatalogueComponent, preview_path: Path | None = None) -> None:
        self._component = component
        self._name.setText(component.name)
        self._meta.setText(f"{component.id} · v{component.version}")
        if component.tags:
            self._meta.setText(f"{self._meta.text()}\n{', '.join(component.tags)}")
        colour = {
            ComponentStatus.CERTIFIED: Theme.SUCCESS,
            ComponentStatus.APPROVED: Theme.ACCENT,
            ComponentStatus.REVIEW: Theme.WARNING,
            ComponentStatus.DRAFT: Theme.TEXT_MUTED,
            ComponentStatus.DEPRECATED: "#E74C3C",
        }.get(component.status, Theme.TEXT_MUTED)
        self._status.setText(component.status.value)
        self._status.setStyleSheet(f"color: {colour};")
        if preview_path and preview_path.is_file():
            pixmap = QPixmap(str(preview_path))
            self._thumb.setPixmap(
                pixmap.scaled(180, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self._thumb.setText("No preview")

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self._component is not None:
            self.activated.emit(self._component.id, self._component.category.value)
        super().mouseDoubleClickEvent(event)
