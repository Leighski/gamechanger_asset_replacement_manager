"""Reference Images page — card gallery with import and drag-and-drop."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models.project import ProjectDocument
from models.reference_image import ALL_CATEGORIES, SUPPORTED_EXTENSIONS
from services.reference_image_service import ReferenceImageService
from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography
from ui.widgets.reference_image_card import ReferenceImageCard
from ui.widgets.reference_image_viewer import ReferenceImageViewer


class ReferenceImagesPanel(QFrame):
    """Dedicated reference image management page."""

    images_changed = Signal()
    import_requested = Signal(list)

    analyse_requested = Signal(str)

    _FILTER = "Images (*.png *.jpg *.jpeg *.tiff *.tif *.webp *.psd)"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._service: ReferenceImageService | None = None
        self._document: ProjectDocument | None = None
        self._viewer: ReferenceImageViewer | None = None
        self._cards: list[ReferenceImageCard] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        root.setSpacing(Theme.SPACING_MD)

        header = QHBoxLayout()
        glyph = QLabel()
        glyph.setPixmap(icon("image", color=Theme.ACCENT, size=20).pixmap(20, 20))
        title_block = QVBoxLayout()
        title = QLabel("Reference Images")
        title.setFont(Typography.heading())
        subtitle = QLabel("Immutable source evidence for design analysis")
        subtitle.setProperty("muted", True)
        subtitle.setFont(Typography.caption())
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addWidget(glyph)
        header.addLayout(title_block)
        header.addStretch(1)
        self._import_btn = QPushButton("Import Images…")
        self._import_btn.clicked.connect(self._choose_import)
        header.addWidget(self._import_btn)

        self._summary = QLabel("No images imported")
        self._summary.setProperty("muted", True)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(Theme.SPACING_MD)
        scroll.setWidget(self._grid_host)

        root.addLayout(header)
        root.addWidget(self._summary)
        root.addWidget(scroll, stretch=1)

    def set_service(self, service: ReferenceImageService) -> None:
        self._service = service

    def set_project(self, document: ProjectDocument | None) -> None:
        self._document = document
        enabled = document is not None and self._service is not None
        self._import_btn.setEnabled(enabled)
        self.setEnabled(enabled)
        if not enabled:
            self._summary.setText("Open a project to manage reference images.")
            self._clear_cards()
            return
        self._refresh()

    def _refresh(self) -> None:
        if self._service is None or self._document is None:
            return
        manifest = self._service.ensure_manifest(self._document)
        validation = self._service.validate(manifest)
        missing = self._service.missing_categories()
        self._summary.setText(
            f"{len(manifest.images)} image(s) · Validation: {validation.status.value}"
            + (f" · Missing: {', '.join(missing)}" if missing else "")
        )
        self._clear_cards()
        project_id = self._document.manifest.project_id
        for index, record in enumerate(manifest.sorted_images()):
            card = ReferenceImageCard()
            thumb = self._service.thumbnail_path(project_id, record.image_id)
            card.set_record(record, thumb)
            card.activated.connect(self._open_viewer)
            card.delete_requested.connect(self._delete_image)
            card.duplicate_requested.connect(self._duplicate_image)
            card.replace_requested.connect(self._replace_image)
            card.rename_requested.connect(self._rename_image)
            card.retag_requested.connect(self._retag_image)
            card.reveal_requested.connect(self._reveal_image)
            card.analyse_requested.connect(self._analyse_image)
            row, col = divmod(index, 3)
            self._grid.addWidget(card, row, col)
            self._cards.append(card)

    def _clear_cards(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()

    def _choose_import(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Import Reference Images", "", self._FILTER)
        if paths:
            self._import_paths(paths)

    def _import_paths(self, paths: list[str]) -> None:
        if self._service is None or self._document is None:
            return
        user = self._document.manifest.author or "Operator"
        self._service.import_files(self._document, paths, user=user)
        self._refresh()
        self.images_changed.emit()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and self._document is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in SUPPORTED_EXTENSIONS or path.suffix.lower() == ".jpeg":
                paths.append(str(path))
        if paths:
            self._import_paths(paths)
        event.acceptProposedAction()

    def _bytes_by_id(self) -> dict[str, bytes]:
        lookup: dict[str, bytes] = {}
        if self._service is None:
            return lookup
        for record in self._service.manifest.images:
            data = self._service.image_bytes(record.image_id)
            if data:
                lookup[record.image_id] = data
        return lookup

    def _open_viewer(self, image_id: str) -> None:
        if self._service is None or self._document is None:
            return
        images = self._service.manifest.sorted_images()
        ids = [image.image_id for image in images]
        index = ids.index(image_id) if image_id in ids else 0
        user = self._document.manifest.author or "Operator"
        self._service.record_viewed(self._document, image_id, user=user)
        self._viewer = ReferenceImageViewer(self)
        self._viewer.set_images(images, self._bytes_by_id(), start_index=index)
        self._viewer.showMaximized()

    def _delete_image(self, image_id: str) -> None:
        if self._service is None or self._document is None:
            return
        user = self._document.manifest.author or "Operator"
        self._service.delete_image(self._document, image_id, user=user)
        self._refresh()
        self.images_changed.emit()

    def _duplicate_image(self, image_id: str) -> None:
        if self._service is None or self._document is None:
            return
        user = self._document.manifest.author or "Operator"
        self._service.duplicate_image(self._document, image_id, user=user)
        self._refresh()
        self.images_changed.emit()

    def _replace_image(self, image_id: str) -> None:
        if self._service is None or self._document is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Replace Reference Image", "", self._FILTER)
        if not path:
            return
        user = self._document.manifest.author or "Operator"
        self._service.replace_image(self._document, image_id, path, user=user)
        self._refresh()
        self.images_changed.emit()

    def _rename_image(self, image_id: str) -> None:
        from PySide6.QtWidgets import QInputDialog

        if self._service is None or self._document is None:
            return
        record = self._service.manifest.get(image_id)
        if record is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Image", "Filename:", text=record.filename)
        if ok and name.strip():
            user = self._document.manifest.author or "Operator"
            self._service.rename_image(self._document, image_id, name.strip(), user=user)
            self._refresh()
            self.images_changed.emit()

    def _retag_image(self, image_id: str) -> None:
        from PySide6.QtWidgets import QInputDialog

        if self._service is None or self._document is None:
            return
        record = self._service.manifest.get(image_id)
        if record is None:
            return
        tags, ok = QInputDialog.getText(
            self,
            "Retag Image",
            f"Tags (comma-separated). Options: {', '.join(ALL_CATEGORIES)}",
            text=", ".join(record.tags),
        )
        if ok:
            user = self._document.manifest.author or "Operator"
            new_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            self._service.retag_image(self._document, image_id, new_tags, user=user)
            self._refresh()
            self.images_changed.emit()

    def _reveal_image(self, image_id: str) -> None:
        import subprocess
        import sys

        if self._document is None or not self._document.file_path:
            return
        path = Path(self._document.file_path)
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)], check=False)

    def _analyse_image(self, image_id: str) -> None:
        self.analyse_requested.emit(image_id)
