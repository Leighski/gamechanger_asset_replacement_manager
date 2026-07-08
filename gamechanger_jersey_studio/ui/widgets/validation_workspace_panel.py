"""Validation Workspace — visual comparison and accuracy scoring."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from models.design_specification import DesignSpecification
from models.validation import ValidationAssetBundle
from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography


class ValidationWorkspacePanel(QFrame):
    """Side-by-side comparison, pixel diff, and accuracy scores."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._projects: ProjectsManager | None = None
        self._assets = ValidationAssetBundle()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG)

        heading = QLabel("Validation Workspace")
        heading.setFont(Typography.heading())
        layout.addWidget(heading)

        btn_row = QHBoxLayout()
        self._btn_ref = QPushButton("Load Reference Images…")
        self._btn_orig_psd = QPushButton("Original PSD…")
        self._btn_studio_psd = QPushButton("Studio PSD…")
        self._btn_png = QPushButton("PNG Preview…")
        self._btn_compare = QPushButton("Run Comparison")
        self._btn_score = QPushButton("Calculate Accuracy")
        for btn in (self._btn_ref, self._btn_orig_psd, self._btn_studio_psd, self._btn_png, self._btn_compare, self._btn_score):
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self._btn_ref.clicked.connect(self._load_references)
        self._btn_orig_psd.clicked.connect(lambda: self._load_file("original_psd_path"))
        self._btn_studio_psd.clicked.connect(lambda: self._load_file("studio_psd_path"))
        self._btn_png.clicked.connect(lambda: self._load_file("png_preview_path"))
        self._btn_compare.clicked.connect(self._run_comparison)
        self._btn_score.clicked.connect(self._run_accuracy)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._before_label = QLabel("Before")
        self._before_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._before_label.setMinimumSize(280, 280)
        self._before_label.setStyleSheet(f"background: {Theme.PANEL_ELEVATED}; border: 1px solid {Theme.BORDER};")
        self._after_label = QLabel("After")
        self._after_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._after_label.setMinimumSize(280, 280)
        self._after_label.setStyleSheet(f"background: {Theme.PANEL_ELEVATED}; border: 1px solid {Theme.BORDER};")
        self._diff_label = QLabel("Difference Overlay")
        self._diff_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._diff_label.setMinimumSize(200, 200)
        self._diff_label.setStyleSheet(f"background: {Theme.PANEL_ELEVATED}; border: 1px solid {Theme.BORDER};")
        splitter.addWidget(self._before_label)
        splitter.addWidget(self._after_label)
        splitter.addWidget(self._diff_label)
        layout.addWidget(splitter, stretch=2)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(50)
        self._slider.setToolTip("Before/After slider")
        layout.addWidget(self._slider)

        self._pixel_info = QLabel("Pixel accuracy: —")
        self._pixel_info.setProperty("muted", True)
        layout.addWidget(self._pixel_info)

        self._scores_table = QTableWidget(0, 3)
        self._scores_table.setHorizontalHeaderLabels(["Category", "Score", "Confidence"])
        self._scores_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._scores_table)

        self._layer_table = QTableWidget(0, 3)
        self._layer_table.setHorizontalHeaderLabels(["Layer", "Before", "After"])
        self._layer_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._layer_table)

    def set_services(self, projects: ProjectsManager) -> None:
        self._projects = projects

    def refresh(self) -> None:
        if self._projects is None or not self._projects.session.loaded:
            return
        document = self._projects.session.document
        if document is None:
            return
        if document.reference_manifest:
            self._assets.reference_images = [
                img.filename for img in document.reference_manifest.images
            ]

    def _load_references(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Reference Images", "", "Images (*.png *.jpg *.jpeg)")
        if paths:
            self._assets.reference_images = paths
            if paths:
                self._set_image(self._before_label, paths[0])

    def _load_file(self, field: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "All Files (*)")
        if path:
            setattr(self._assets, field, path)
            if field == "png_preview_path":
                self._set_image(self._after_label, path)

    def _set_image(self, label: QLabel, path: str) -> None:
        pix = QPixmap(path)
        if not pix.isNull():
            label.setPixmap(pix.scaled(label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _run_comparison(self) -> None:
        if self._projects is None or self._projects.production_manager is None:
            return
        comparison = self._projects.production_manager.comparison
        before = self._assets.original_psd_path or (self._assets.reference_images[0] if self._assets.reference_images else "")
        after = self._assets.png_preview_path or self._assets.studio_psd_path
        if not before or not after:
            self._pixel_info.setText("Load before/after images to compare.")
            return
        from core.paths import CACHE_DIR
        diff_path = CACHE_DIR / "validation_diff.png"
        result = comparison.build_visual_comparison(before, after, diff_output_path=diff_path)
        if result.pixel:
            self._pixel_info.setText(
                f"Pixel accuracy: {result.pixel.accuracy_percent}% "
                f"({result.pixel.matching_pixels}/{result.pixel.total_pixels} pixels)"
            )
        if result.diff_overlay_path and Path(result.diff_overlay_path).is_file():
            self._set_image(self._diff_label, result.diff_overlay_path)
        if self._assets.original_psd_path and self._assets.studio_psd_path:
            layers = comparison.compare_psd_layers(self._assets.original_psd_path, self._assets.studio_psd_path)
            self._layer_table.setRowCount(len(layers))
            for row, layer in enumerate(layers):
                self._layer_table.setItem(row, 0, QTableWidgetItem(layer.layer_name))
                self._layer_table.setItem(row, 1, QTableWidgetItem("Visible" if layer.visible_before else "Hidden"))
                self._layer_table.setItem(row, 2, QTableWidgetItem("Visible" if layer.visible_after else "Hidden"))

    def _run_accuracy(self) -> None:
        if self._projects is None or not self._projects.session.loaded:
            return
        document = self._projects.session.document
        if document is None or document.design_spec is None:
            return
        pm = self._projects.production_manager
        generated = document.design_spec
        expected = DesignSpecification.model_validate(generated.model_dump())
        report = pm.accuracy.score(expected, generated, project_name=document.manifest.project_name)
        rows = [report.overall] + list(report.categories)
        self._scores_table.setRowCount(len(rows))
        for i, cat in enumerate(rows):
            self._scores_table.setItem(i, 0, QTableWidgetItem(cat.category.value))
            self._scores_table.setItem(i, 1, QTableWidgetItem(f"{cat.score}%"))
            self._scores_table.setItem(i, 2, QTableWidgetItem(f"{cat.confidence}%"))
