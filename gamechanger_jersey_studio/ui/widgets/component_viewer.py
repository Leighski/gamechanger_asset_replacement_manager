"""Component Viewer — detailed component inspection."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from models.component_catalogue import CatalogueComponent
from services.catalogue_manager_service import CatalogueManagerService
from ui.theme import Theme
from ui.typography import Typography


class ComponentViewerDialog(QDialog):
    """Display component preview, metadata, version history, and future PSD placeholders."""

    def __init__(self, component: CatalogueComponent, manager: CatalogueManagerService, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(component.name)
        self.setMinimumSize(640, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        root.setSpacing(Theme.SPACING_MD)

        header = QLabel(f"{component.name} ({component.id})")
        header.setFont(Typography.heading())
        root.addWidget(header)

        body = QHBoxLayout()
        preview = QLabel()
        preview.setFixedSize(240, 240)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setStyleSheet(f"background: {Theme.PANEL_ELEVATED}; border-radius: {Theme.RADIUS_SM}px;")
        path = manager.preview_path(component)
        if path:
            preview.setPixmap(
                QPixmap(str(path)).scaled(
                    220, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )
        else:
            preview.setText("No preview")
        body.addWidget(preview)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        form = QFormLayout(host)
        form.setSpacing(Theme.SPACING_SM)

        def row(label: str, value: str) -> None:
            name = QLabel(label)
            name.setFont(Typography.caption())
            val = QLabel(value or "—")
            val.setWordWrap(True)
            form.addRow(name, val)

        row("Category", component.category.value)
        row("Version", component.version)
        row("Status", component.status.value)
        row("Description", component.description)
        row("Author", component.author)
        row("Created", component.created_at[:10])
        row("Modified", component.modified_at[:10])
        row("Tags", ", ".join(component.tags))
        row("Legacy IDs", ", ".join(component.legacy_ids))
        row("Dependencies", ", ".join(component.dependencies) or "None")
        row("Notes", component.notes)

        form.addRow(QLabel("Version History"), QLabel(""))
        for entry in component.version_history:
            form.addRow(
                entry.version,
                QLabel(f"{entry.date[:10]} — {entry.notes or 'No notes'}"),
            )

        form.addRow(QLabel("Future Assets"), QLabel(""))
        row("PSD Layer Ref", component.assets.psd_layer_ref or "Not available")
        row("Mask Ref", component.assets.mask_ref or "Not available")
        row("SVG Preview", component.assets.svg_preview or "Not available")
        row("Geometry", str(component.assets.geometry) if component.assets.geometry else "Not defined")
        row("Anchor Points", str(len(component.assets.anchor_points)))
        row("Rendering Metadata", str(component.assets.rendering_metadata) if component.assets.rendering_metadata else "Not defined")

        scroll.setWidget(host)
        body.addWidget(scroll, stretch=1)
        root.addLayout(body)
