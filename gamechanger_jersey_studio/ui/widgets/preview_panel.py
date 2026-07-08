"""Right-hand live preview panel."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from models.project import ProjectDocument
from models.renderer import RenderLayerId, RendererSettings, RenderQuality, RenderResult
from services.live_renderer_service import LiveRendererService
from ui.theme import Theme
from ui.typography import Typography
from ui.widgets.empty_state import EmptyState
from ui.widgets.renderer_inspector import RendererInspector


class PreviewPanel(QFrame):
    """Live jersey preview — auto-refreshes when the Design Specification changes."""

    settings_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setMinimumWidth(280)

        self._document: ProjectDocument | None = None
        self._renderer: LiveRendererService | None = None
        self._settings = RendererSettings()
        self._last_result: RenderResult | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        layout.setSpacing(Theme.SPACING_MD)

        header = QHBoxLayout()
        heading = QLabel("Live Preview")
        heading.setFont(Typography.subheading())
        self._quality = QComboBox()
        for quality in RenderQuality:
            self._quality.addItem(quality.value, quality)
        self._quality.setCurrentText(RenderQuality.STANDARD.value)
        header.addWidget(heading)
        header.addStretch()
        header.addWidget(self._quality)

        self._stack = QStackedWidget()
        self._empty = EmptyState(
            icon_name="preview",
            title="Preview unavailable",
            message="Import a project to begin.",
        )
        self._loaded = QWidget()
        loaded_layout = QVBoxLayout(self._loaded)
        loaded_layout.setContentsMargins(0, 0, 0, 0)
        loaded_layout.setSpacing(Theme.SPACING_SM)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumHeight(200)
        self._image_label.setStyleSheet(
            f"background: {Theme.PANEL_ELEVATED}; border: 1px solid {Theme.BORDER_SUBTLE}; "
            f"border-radius: {Theme.RADIUS_MD}px;"
        )

        self._timing_label = QLabel("")
        self._timing_label.setFont(Typography.caption())
        self._timing_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")

        layer_scroll = QScrollArea()
        layer_scroll.setWidgetResizable(True)
        layer_scroll.setMaximumHeight(140)
        layer_host = QWidget()
        self._layer_grid = QGridLayout(layer_host)
        self._layer_grid.setContentsMargins(0, 0, 0, 0)
        self._layer_grid.setSpacing(Theme.SPACING_XS)
        self._layer_checks: dict[RenderLayerId, QCheckBox] = {}
        for index, layer_id in enumerate(RenderLayerId):
            checkbox = QCheckBox(layer_id.value.replace("_", " ").title())
            checkbox.setChecked(True)
            checkbox.setFont(Typography.caption())
            checkbox.toggled.connect(self._on_layer_toggled)
            self._layer_checks[layer_id] = checkbox
            self._layer_grid.addWidget(checkbox, index // 2, index % 2)
        layer_scroll.setWidget(layer_host)

        self._inspector_toggle = QCheckBox("Show Renderer Inspector")
        self._inspector_toggle.setFont(Typography.caption())
        self._inspector_toggle.toggled.connect(self._on_inspector_toggled)
        self._inspector = RendererInspector()
        self._inspector.setVisible(False)

        loaded_layout.addWidget(self._image_label, stretch=1)
        loaded_layout.addWidget(self._timing_label)
        loaded_layout.addWidget(layer_scroll)
        loaded_layout.addWidget(self._inspector_toggle)
        loaded_layout.addWidget(self._inspector)

        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._loaded)

        layout.addLayout(header)
        layout.addWidget(self._stack, stretch=1)

        self._quality.currentIndexChanged.connect(self._on_quality_changed)

    def set_renderer_service(self, service: LiveRendererService) -> None:
        self._renderer = service

    def set_project(self, document: ProjectDocument | None) -> None:
        self._document = document
        if document is None:
            self._stack.setCurrentIndex(0)
            self._image_label.clear()
            self._timing_label.setText("")
            self._inspector.clear()
            return
        if document.renderer_settings is not None:
            self._apply_settings(document.renderer_settings)
        self._stack.setCurrentIndex(1)
        self.refresh_preview()

    def set_project_loaded(self, loaded: bool, project_name: str = "") -> None:
        if loaded:
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(0)

    def refresh_preview(self) -> None:
        if self._document is None or self._renderer is None:
            return
        settings = self._sync_settings_to_document()
        from models.design_specification import DesignSpecification

        spec = self._document.design_spec or DesignSpecification.from_manifest(self._document.manifest)
        result = self._renderer.render_document(self._document)
        self._last_result = result
        if result.success and result.image_png:
            pixmap = QPixmap()
            pixmap.loadFromData(result.image_png)
            scaled = pixmap.scaled(
                max(self._image_label.width(), 200) - 8,
                max(self._image_label.height(), 200) - 8,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._image_label.setStyleSheet(
                f"background: {Theme.PANEL_ELEVATED}; border: 1px solid {Theme.BORDER_SUBTLE}; "
                f"border-radius: {Theme.RADIUS_MD}px;"
            )
            self._image_label.setText("")
            self._image_label.setPixmap(scaled)
            total_cache = result.stats.cache_hits + result.stats.cache_misses
            self._timing_label.setText(
                f"{result.stats.total_ms:.1f} ms · cache {result.stats.cache_hits}/{total_cache}"
            )
            active = [layer_id for layer_id in RenderLayerId if settings.is_layer_visible(layer_id)]
            self._inspector.update_stats(result.stats, active)
        elif not result.success:
            self._image_label.clear()
            self._image_label.setText(self._format_render_error(result.error or "Unknown render error"))
            self._image_label.setStyleSheet(
                f"background: {Theme.PANEL_ELEVATED}; border: 1px solid {Theme.BORDER_SUBTLE}; "
                f"border-radius: {Theme.RADIUS_MD}px; color: {Theme.WARNING}; padding: 8px;"
            )
            self._timing_label.setText("")
            self._inspector.clear()
        self._image_label.update()

    @staticmethod
    def _format_render_error(error: str) -> str:
        if error.startswith("Missing "):
            return f"{error}\n\nOpen Design Specification and assign catalogue components."
        if "No certified component" in error:
            return f"{error}\n\nCheck the component library or update Design Specification."
        return f"Render failed: {error}"

    def _sync_settings_to_document(self) -> RendererSettings:
        quality = self._quality.currentData()
        visibility = {
            layer_id.value: checkbox.isChecked()
            for layer_id, checkbox in self._layer_checks.items()
        }
        settings = RendererSettings(
            quality=quality,
            background_colour=self._settings.background_colour,
            layer_visibility=visibility,
            show_inspector=self._inspector_toggle.isChecked(),
        )
        self._settings = settings
        if self._document is not None:
            self._document.renderer_settings = settings
        return settings

    def _apply_settings(self, settings: RendererSettings) -> None:
        self._settings = settings
        index = self._quality.findData(settings.quality)
        if index >= 0:
            self._quality.blockSignals(True)
            self._quality.setCurrentIndex(index)
            self._quality.blockSignals(False)
        for layer_id, checkbox in self._layer_checks.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(settings.is_layer_visible(layer_id))
            checkbox.blockSignals(False)
        self._inspector_toggle.blockSignals(True)
        self._inspector_toggle.setChecked(settings.show_inspector)
        self._inspector.setVisible(settings.show_inspector)
        self._inspector_toggle.blockSignals(False)

    def _on_quality_changed(self) -> None:
        if self._document is None:
            return
        self._document.mark_dirty()
        self.settings_changed.emit()
        self.refresh_preview()

    def _on_layer_toggled(self) -> None:
        if self._document is None:
            return
        self._document.mark_dirty()
        self.settings_changed.emit()
        self.refresh_preview()

    def _on_inspector_toggled(self, visible: bool) -> None:
        self._inspector.setVisible(visible)
        if self._document is not None:
            self._document.mark_dirty()
        self.settings_changed.emit()
