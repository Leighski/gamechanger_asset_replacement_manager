"""Template card for Template Browser grid."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from models.psd_template import PSDTemplate, TemplateValidationReport
from ui.theme import Theme
from ui.typography import Typography


class TemplateCard(QFrame):
    activated = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._template_id = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD)
        layout.setSpacing(Theme.SPACING_SM)
        self._preview = QLabel()
        self._preview.setFixedHeight(140)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            f"background: {Theme.PANEL_ELEVATED}; border-radius: {Theme.RADIUS_MD}px;"
        )
        self._name = QLabel()
        self._name.setFont(Typography.subheading())
        self._meta = QLabel()
        self._meta.setFont(Typography.caption())
        self._meta.setProperty("muted", True)
        self._meta.setWordWrap(True)
        layout.addWidget(self._preview)
        layout.addWidget(self._name)
        layout.addWidget(self._meta)

    def set_template(
        self,
        template: PSDTemplate,
        preview_path: Path | None,
        validation: TemplateValidationReport | None,
    ) -> None:
        self._template_id = template.template_id
        self._name.setText(template.name)
        layer_count = validation.layer_count if validation else 0
        smart_count = validation.smart_object_count if validation else 0
        profiles = ", ".join(template.build_profile_compatibility[:2]) or "—"
        self._meta.setText(
            f"v{template.version} · {template.status.value}\n"
            f"{layer_count} layers · {smart_count} smart objects\n"
            f"{profiles}"
        )
        if preview_path and preview_path.is_file():
            pixmap = QPixmap(str(preview_path))
            self._preview.setPixmap(
                pixmap.scaled(180, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self._preview.clear()
            self._preview.setText("No preview")

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._template_id:
            self.activated.emit(self._template_id)
        super().mouseReleaseEvent(event)
