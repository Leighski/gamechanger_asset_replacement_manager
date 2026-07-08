"""Reference image card for the gallery grid."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QVBoxLayout

from models.reference_image import ReferenceImageRecord
from ui.theme import Theme
from ui.typography import Typography


class ReferenceImageCard(QFrame):
    """Card displaying a single reference image thumbnail and metadata."""

    activated = Signal(str)
    delete_requested = Signal(str)
    duplicate_requested = Signal(str)
    rename_requested = Signal(str)
    retag_requested = Signal(str)
    replace_requested = Signal(str)
    reveal_requested = Signal(str)
    analyse_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self._record: ReferenceImageRecord | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD)
        layout.setSpacing(Theme.SPACING_SM)

        self._thumb = QLabel()
        self._thumb.setFixedHeight(140)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(f"background: {Theme.PANEL_ELEVATED}; border-radius: {Theme.RADIUS_SM}px;")

        self._filename = QLabel("—")
        self._filename.setFont(Typography.subheading())
        self._filename.setWordWrap(True)

        self._meta = QLabel()
        self._meta.setFont(Typography.caption())
        self._meta.setProperty("muted", True)
        self._meta.setWordWrap(True)

        self._tags = QLabel()
        self._tags.setFont(Typography.caption())
        self._tags.setWordWrap(True)

        status_row = QHBoxLayout()
        self._validation = QLabel()
        self._validation.setFont(Typography.caption())
        self._analysis = QLabel("Analysis: Not started")
        self._analysis.setFont(Typography.caption())
        self._analysis.setProperty("muted", True)
        status_row.addWidget(self._validation)
        status_row.addStretch(1)
        status_row.addWidget(self._analysis)

        layout.addWidget(self._thumb)
        layout.addWidget(self._filename)
        layout.addWidget(self._meta)
        layout.addWidget(self._tags)
        layout.addLayout(status_row)

    def set_record(self, record: ReferenceImageRecord, thumbnail_path: Path | None = None) -> None:
        self._record = record
        self._filename.setText(record.filename)
        self._meta.setText(f"{record.dimensions_label} · {record.import_date[:10]}")
        self._tags.setText(", ".join(record.tags) if record.tags else "Uncategorised")
        colour = Theme.SUCCESS if record.validation_status.value == "Passed" else Theme.WARNING
        self._validation.setText(f"Validation: {record.validation_status.value}")
        self._validation.setStyleSheet(f"color: {colour};")
        self._analysis.setText(f"Analysis: {record.analysis_status.value}")
        if thumbnail_path and thumbnail_path.is_file():
            pixmap = QPixmap(str(thumbnail_path))
            self._thumb.setPixmap(
                pixmap.scaled(
                    220,
                    140,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self._thumb.setText("No preview")

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self._record is not None:
            self.activated.emit(self._record.image_id)
        super().mouseDoubleClickEvent(event)

    def _show_menu(self, pos) -> None:
        if self._record is None:
            return
        menu = QMenu(self)
        menu.addAction("Open Viewer", lambda: self.activated.emit(self._record.image_id))
        menu.addAction("Analyse", lambda: self.analyse_requested.emit(self._record.image_id))
        menu.addAction("Rename", lambda: self.rename_requested.emit(self._record.image_id))
        menu.addAction("Retag", lambda: self.retag_requested.emit(self._record.image_id))
        menu.addAction("Replace", lambda: self.replace_requested.emit(self._record.image_id))
        menu.addAction("Duplicate", lambda: self.duplicate_requested.emit(self._record.image_id))
        menu.addAction("Reveal in Finder", lambda: self.reveal_requested.emit(self._record.image_id))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self.delete_requested.emit(self._record.image_id))
        menu.exec(self.mapToGlobal(pos))
