"""Full-screen reference image viewer."""

from __future__ import annotations

import io

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut, QTransform
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models.reference_image import ReferenceImageRecord
from ui.theme import Theme
from ui.typography import Typography


class ReferenceImageViewer(QDialog):
    """Full-screen viewer with zoom, pan, and navigation."""

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reference Image Viewer")
        self.setModal(False)
        self.resize(1200, 800)
        self._images: list[ReferenceImageRecord] = []
        self._index = 0
        self._bytes_lookup: dict[str, bytes] = {}
        self._zoom = 1.0
        self._space_pan = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(Theme.SPACING_MD, Theme.SPACING_SM, Theme.SPACING_MD, Theme.SPACING_SM)
        self._title = QLabel("Image")
        self._title.setFont(Typography.subheading())
        self._btn_fit = QPushButton("Fit to Window")
        self._btn_100 = QPushButton("100%")
        self._btn_prev = QPushButton("Previous")
        self._btn_next = QPushButton("Next")
        for button in (self._btn_fit, self._btn_100, self._btn_prev, self._btn_next):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        toolbar.addWidget(self._title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setWidget(self._image_label)

        info_panel = QWidget()
        info_panel.setObjectName("panel")
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_MD, Theme.SPACING_LG, Theme.SPACING_MD)
        self._info = QLabel("No image loaded")
        self._info.setWordWrap(True)
        self._info.setFont(Typography.body())
        info_layout.addWidget(self._info)

        root.addLayout(toolbar)
        root.addWidget(self._scroll, stretch=1)
        root.addWidget(info_panel)

        self._btn_fit.clicked.connect(self._fit_to_window)
        self._btn_100.clicked.connect(lambda: self._set_zoom(1.0))
        self._btn_prev.clicked.connect(self._show_previous)
        self._btn_next.clicked.connect(self._show_next)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self._toggle_pan_hint)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=self._show_previous)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=self._show_next)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.close)

    def set_images(
        self,
        images: list[ReferenceImageRecord],
        bytes_lookup: dict[str, bytes],
        *,
        start_index: int = 0,
    ) -> None:
        self._images = images
        self._bytes_lookup = bytes_lookup
        self._index = max(0, min(start_index, len(images) - 1))
        self._show_current()

    def _show_current(self) -> None:
        if not self._images:
            return
        record = self._images[self._index]
        data = self._bytes_lookup.get(record.image_id)
        self._title.setText(f"{record.filename} ({self._index + 1}/{len(self._images)})")
        tags = ", ".join(record.tags) if record.tags else "Uncategorised"
        self._info.setText(
            f"Filename: {record.filename}\n"
            f"Dimensions: {record.dimensions_label}\n"
            f"File size: {record.file_size:,} bytes\n"
            f"Colour profile: {record.colour_profile or 'Unknown'}\n"
            f"Checksum: {record.checksum[:16]}…\n"
            f"Tags: {tags}\n"
            f"Import date: {record.import_date}\n"
            f"Validation: {record.validation_status.value}\n"
            f"Analysis: {record.analysis_status.value}"
        )
        if not data:
            self._image_label.setText("Image data unavailable")
            return
        image = QImage.fromData(data)
        if image.isNull():
            self._image_label.setText("Could not render image")
            return
        if record.orientation:
            transform = Qt.TransformationMode.SmoothTransformation
            image = image.transformed(
                QTransform().rotate(record.orientation),
                transform,
            )
        self._source_pixmap = QPixmap.fromImage(image)
        self._fit_to_window()

    def _set_zoom(self, factor: float) -> None:
        self._zoom = max(0.1, min(factor, 8.0))
        scaled = self._source_pixmap.scaled(
            int(self._source_pixmap.width() * self._zoom),
            int(self._source_pixmap.height() * self._zoom),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)

    def _fit_to_window(self) -> None:
        if not hasattr(self, "_source_pixmap"):
            return
        viewport = self._scroll.viewport().size()
        factor = min(
            viewport.width() / max(1, self._source_pixmap.width()),
            viewport.height() / max(1, self._source_pixmap.height()),
        )
        self._set_zoom(factor * 0.95)

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        step = 1.1 if delta > 0 else 0.9
        self._set_zoom(self._zoom * step)

    def _show_previous(self) -> None:
        if not self._images:
            return
        self._index = (self._index - 1) % len(self._images)
        self._show_current()

    def _show_next(self) -> None:
        if not self._images:
            return
        self._index = (self._index + 1) % len(self._images)
        self._show_current()

    def _toggle_pan_hint(self) -> None:
        self._space_pan = not self._space_pan
        cursor = Qt.CursorShape.OpenHandCursor if self._space_pan else Qt.CursorShape.ArrowCursor
        self._scroll.viewport().setCursor(cursor)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(event)
