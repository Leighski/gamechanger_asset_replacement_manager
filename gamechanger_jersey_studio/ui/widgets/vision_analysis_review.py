"""Vision Engine analysis review — operator approval before Design Specification changes."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.interpretation import ConfidenceBand, InterpretationResult, InterpretationSuggestion, SuggestionStatus
from models.project import ProjectDocument
from models.vision_analysis import VisionAnalysisResult
from services.design_specification_service import DesignSpecificationService
from services.interpretation_service import InterpretationError, InterpretationService
from services.reference_image_service import ReferenceImageService
from services.vision.pipeline import VisionEngineError
from services.vision_analysis_service import VisionAnalysisService
from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography


class _AnalysisCanvas(QLabel):
    """Display reference image with shirt outline and detected regions."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(360, 420)
        self.setStyleSheet(f"background: {Theme.PANEL_ELEVATED}; border-radius: {Theme.RADIUS_SM}px;")
        self._base: QPixmap | None = None
        self._analysis: VisionAnalysisResult | None = None

    def set_analysis(self, pixmap: QPixmap | None, analysis: VisionAnalysisResult | None) -> None:
        self._base = pixmap
        self._analysis = analysis
        self._render()

    def _render(self) -> None:
        if self._base is None or self._base.isNull():
            self.setText("No image selected")
            self.setPixmap(QPixmap())
            return
        scaled = self._base.scaled(
            max(360, self.width() - 16),
            max(420, self.height() - 16),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        composed = QPixmap(scaled.size())
        composed.fill(Qt.GlobalColor.transparent)
        painter = QPainter(composed)
        painter.drawPixmap(0, 0, scaled)
        if self._analysis is not None:
            scale_x = scaled.width() / max(1, self._base.width())
            scale_y = scaled.height() / max(1, self._base.height())
            if self._analysis.shirt_detection:
                pen = QPen(QColor(Theme.ACCENT))
                pen.setWidth(2)
                painter.setPen(pen)
                outline = self._analysis.shirt_detection.outline_points
                if len(outline) >= 2:
                    for index in range(len(outline)):
                        x0, y0 = outline[index]
                        x1, y1 = outline[(index + 1) % len(outline)]
                        painter.drawLine(
                            int(x0 * scale_x),
                            int(y0 * scale_y),
                            int(x1 * scale_x),
                            int(y1 * scale_y),
                        )
            region_colours = {
                "Collar": "#E74C3C",
                "Sleeves": "#3498DB",
                "Body": "#2ECC71",
                "Shoulders": "#F39C12",
                "Side Panels": "#9B59B6",
                "Trim": "#1ABC9C",
            }
            for region in self._analysis.regions:
                colour = QColor(region_colours.get(region.name, Theme.TEXT_MUTED))
                colour.setAlpha(60)
                painter.setBrush(colour)
                painter.setPen(QPen(QColor(region_colours.get(region.name, Theme.TEXT_MUTED)), 1))
                if len(region.points) >= 3:
                    polygon = QPolygon(
                        [QPoint(int(x * scale_x), int(y * scale_y)) for x, y in region.points]
                    )
                    painter.drawPolygon(polygon)
        painter.end()
        self.setPixmap(composed)
        self.setText("")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._render()


class _SuggestionRow(QFrame):
    """Single AI interpretation suggestion with editable proposed value."""

    def __init__(self, suggestion: InterpretationSuggestion, parent=None) -> None:
        super().__init__(parent)
        self.suggestion = suggestion
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_SM, Theme.SPACING_SM, Theme.SPACING_SM, Theme.SPACING_SM)
        layout.setSpacing(Theme.SPACING_XS)

        header = QHBoxLayout()
        self.checkbox = QCheckBox(f"{suggestion.target_field}")
        self.checkbox.setChecked(suggestion.auto_select_eligible())
        self.checkbox.setEnabled(suggestion.status == SuggestionStatus.PENDING)
        band_colour = {
            ConfidenceBand.HIGH: Theme.SUCCESS,
            ConfidenceBand.MEDIUM: Theme.WARNING,
            ConfidenceBand.LOW: "#E74C3C",
        }[suggestion.confidence_band]
        band = QLabel(f"{suggestion.confidence_band.value} ({suggestion.confidence:.0f}%)")
        band.setStyleSheet(f"color: {band_colour};")
        band.setFont(Typography.caption())
        header.addWidget(self.checkbox)
        header.addStretch(1)
        header.addWidget(band)
        layout.addLayout(header)

        current = QLabel(f"Current: {suggestion.current_value or '—'}")
        current.setFont(Typography.caption())
        current.setProperty("muted", True)
        layout.addWidget(current)

        value_row = QHBoxLayout()
        value_row.addWidget(QLabel("Proposed:"))
        self.value_edit = QLineEdit(suggestion.effective_value())
        self.value_edit.setEnabled(suggestion.status == SuggestionStatus.PENDING)
        value_row.addWidget(self.value_edit, stretch=1)
        layout.addLayout(value_row)

        reason = QLabel(f"Reason: {suggestion.reasoning}")
        reason.setWordWrap(True)
        reason.setFont(Typography.caption())
        layout.addWidget(reason)

        if suggestion.source_measurements:
            sources = QLabel("Sources: " + ", ".join(suggestion.source_measurements))
            sources.setWordWrap(True)
            sources.setFont(Typography.caption())
            sources.setProperty("muted", True)
            layout.addWidget(sources)

        status = QLabel(f"Status: {suggestion.status.value}")
        status.setFont(Typography.caption())
        layout.addWidget(status)


class VisionAnalysisReviewPanel(QFrame):
    """Review vision measurements and AI interpretation before Design Specification changes."""

    analysis_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._vision: VisionAnalysisService | None = None
        self._interpretation: InterpretationService | None = None
        self._design: DesignSpecificationService | None = None
        self._references: ReferenceImageService | None = None
        self._document: ProjectDocument | None = None
        self._current: VisionAnalysisResult | None = None
        self._interpretation_result: InterpretationResult | None = None
        self._mapping_checks: dict[str, QCheckBox] = {}
        self._suggestion_rows: dict[str, _SuggestionRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        root.setSpacing(Theme.SPACING_MD)

        header = QHBoxLayout()
        glyph = QLabel()
        glyph.setPixmap(icon("validation", color=Theme.ACCENT, size=20).pixmap(20, 20))
        title_block = QVBoxLayout()
        title = QLabel("Analysis & Interpretation Review")
        title.setFont(Typography.heading())
        subtitle = QLabel("Vision measurements and AI suggestions — operator decides all Design Specification changes")
        subtitle.setProperty("muted", True)
        subtitle.setFont(Typography.caption())
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addWidget(glyph)
        header.addLayout(title_block)
        header.addStretch(1)
        self._image_selector = QComboBox()
        self._image_selector.setMinimumWidth(220)
        self._image_selector.currentIndexChanged.connect(self._on_image_changed)
        header.addWidget(QLabel("Reference:"))
        header.addWidget(self._image_selector)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._canvas = _AnalysisCanvas()
        left_layout.addWidget(self._canvas, stretch=1)

        self._summary = QLabel("Select a reference image to review analysis.")
        self._summary.setProperty("muted", True)
        self._summary.setWordWrap(True)
        left_layout.addWidget(self._summary)
        splitter.addWidget(left)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_host = QWidget()
        right_layout = QVBoxLayout(right_host)
        right_layout.setSpacing(Theme.SPACING_MD)

        self._colour_grid = QGridLayout()
        colour_heading = QLabel("Colour Palette")
        colour_heading.setFont(Typography.subheading())
        right_layout.addWidget(colour_heading)
        right_layout.addLayout(self._colour_grid)

        self._confidence_table = QTableWidget(0, 2)
        self._confidence_table.setHorizontalHeaderLabels(["Measurement", "Confidence"])
        self._confidence_table.horizontalHeader().setStretchLastSection(True)
        self._confidence_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        conf_heading = QLabel("Confidence Summary")
        conf_heading.setFont(Typography.subheading())
        right_layout.addWidget(conf_heading)
        right_layout.addWidget(self._confidence_table)

        self._measurements_table = QTableWidget(0, 3)
        self._measurements_table.setHorizontalHeaderLabels(["Measurement", "Value", "Confidence"])
        self._measurements_table.horizontalHeader().setStretchLastSection(True)
        self._measurements_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        meas_heading = QLabel("Shape & Pattern Measurements")
        meas_heading.setFont(Typography.subheading())
        right_layout.addWidget(meas_heading)
        right_layout.addWidget(self._measurements_table)

        mappings_heading = QLabel("Suggested Design Specification Changes")
        mappings_heading.setFont(Typography.subheading())
        right_layout.addWidget(mappings_heading)
        self._mappings_host = QVBoxLayout()
        right_layout.addLayout(self._mappings_host)

        spec_heading = QLabel("Current Design Specification")
        spec_heading.setFont(Typography.subheading())
        right_layout.addWidget(spec_heading)
        self._spec_table = QTableWidget(0, 2)
        self._spec_table.setHorizontalHeaderLabels(["Field", "Value"])
        self._spec_table.horizontalHeader().setStretchLastSection(True)
        self._spec_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        right_layout.addWidget(self._spec_table)

        ai_heading = QLabel("AI Interpretation Suggestions")
        ai_heading.setFont(Typography.subheading())
        right_layout.addWidget(ai_heading)
        self._ai_status = QLabel("Generate interpretation from vision measurements.")
        self._ai_status.setProperty("muted", True)
        self._ai_status.setWordWrap(True)
        right_layout.addWidget(self._ai_status)
        self._interpret_btn = QPushButton("Generate AI Interpretation")
        self._interpret_btn.clicked.connect(self._generate_interpretation)
        self._interpret_btn.setEnabled(False)
        right_layout.addWidget(self._interpret_btn)
        self._suggestions_host = QVBoxLayout()
        right_layout.addLayout(self._suggestions_host)

        self._warnings = QLabel()
        self._warnings.setWordWrap(True)
        self._warnings.setStyleSheet(f"color: {Theme.WARNING};")
        right_layout.addWidget(self._warnings)

        right_layout.addStretch(1)
        right_scroll.setWidget(right_host)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, stretch=1)

        actions = QHBoxLayout()
        self._accept_all_btn = QPushButton("Accept All")
        self._accept_selected_btn = QPushButton("Accept Selected")
        self._reject_btn = QPushButton("Reject Analysis")
        self._reanalyse_btn = QPushButton("Reanalyse")
        self._accept_ai_all_btn = QPushButton("Accept All AI")
        self._accept_ai_selected_btn = QPushButton("Accept Selected AI")
        self._reject_ai_selected_btn = QPushButton("Reject Selected AI")
        self._reject_ai_all_btn = QPushButton("Reject All AI")
        for button in (
            self._accept_all_btn,
            self._accept_selected_btn,
            self._reject_btn,
            self._reanalyse_btn,
            self._accept_ai_all_btn,
            self._accept_ai_selected_btn,
            self._reject_ai_selected_btn,
            self._reject_ai_all_btn,
        ):
            button.setEnabled(False)
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)

        self._accept_all_btn.clicked.connect(self._accept_all)
        self._accept_selected_btn.clicked.connect(self._accept_selected)
        self._reject_btn.clicked.connect(self._reject)
        self._reanalyse_btn.clicked.connect(self._reanalyse)
        self._accept_ai_all_btn.clicked.connect(self._accept_ai_all)
        self._accept_ai_selected_btn.clicked.connect(self._accept_ai_selected)
        self._reject_ai_selected_btn.clicked.connect(self._reject_ai_selected)
        self._reject_ai_all_btn.clicked.connect(self._reject_ai_all)

    def set_services(
        self,
        vision: VisionAnalysisService,
        references: ReferenceImageService,
        interpretation: InterpretationService | None = None,
        design: DesignSpecificationService | None = None,
    ) -> None:
        self._vision = vision
        self._references = references
        self._interpretation = interpretation
        self._design = design

    def set_project(self, document: ProjectDocument | None) -> None:
        self._document = document
        self._current = None
        self._image_selector.blockSignals(True)
        self._image_selector.clear()
        self._image_selector.blockSignals(False)
        enabled = document is not None and self._vision is not None and self._references is not None
        self.setEnabled(enabled)
        for button in (
            self._accept_all_btn,
            self._accept_selected_btn,
            self._reject_btn,
            self._reanalyse_btn,
            self._accept_ai_all_btn,
            self._accept_ai_selected_btn,
            self._reject_ai_selected_btn,
            self._reject_ai_all_btn,
            self._interpret_btn,
        ):
            button.setEnabled(False)
        if not enabled:
            self._canvas.set_analysis(None, None)
            self._summary.setText("Open a project to review vision analysis.")
            self._clear_detail_panels()
            return
        for record in self._references.manifest.sorted_images():
            self._image_selector.addItem(record.filename, record.image_id)
        if self._image_selector.count():
            self._image_selector.setCurrentIndex(0)
            self._on_image_changed(0)

    def show_analysis_for_image(self, image_id: str) -> None:
        index = self._image_selector.findData(image_id)
        if index >= 0:
            self._image_selector.setCurrentIndex(index)

    def run_analysis(self, image_id: str) -> None:
        if self._vision is None or self._document is None:
            return
        user = self._document.manifest.author or "Operator"
        try:
            self._vision.analyse_image(self._document, image_id, user=user)
            self.show_analysis_for_image(image_id)
            self.analysis_changed.emit()
        except VisionEngineError as exc:
            QMessageBox.warning(self, "Analysis Failed", str(exc))

    def _on_image_changed(self, index: int) -> None:
        if index < 0 or self._references is None or self._vision is None:
            return
        image_id = self._image_selector.itemData(index)
        if not image_id:
            return
        self._current = self._vision.latest_for_image(image_id)
        pixmap = self._load_pixmap(image_id)
        self._canvas.set_analysis(pixmap, self._current)
        self._populate_details()
        has_analysis = self._current is not None
        for button in (
            self._accept_all_btn,
            self._accept_selected_btn,
            self._reject_btn,
            self._reanalyse_btn,
            self._interpret_btn,
        ):
            button.setEnabled(has_analysis)

    def _load_pixmap(self, image_id: str) -> QPixmap | None:
        if self._references is None or self._document is None:
            return None
        data = self._references.image_bytes(image_id)
        if not data:
            return None
        image = QImage.fromData(data)
        if image.isNull():
            return None
        return QPixmap.fromImage(image)

    def _clear_detail_panels(self) -> None:
        while self._colour_grid.count():
            item = self._colour_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._confidence_table.setRowCount(0)
        self._measurements_table.setRowCount(0)
        while self._mappings_host.count():
            item = self._mappings_host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._mapping_checks.clear()
        self._suggestion_rows.clear()
        self._spec_table.setRowCount(0)
        self._interpretation_result = None
        while self._suggestions_host.count():
            item = self._suggestions_host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._warnings.setText("")
        self._ai_status.setText("Generate interpretation from vision measurements.")

    def _populate_details(self) -> None:
        self._clear_detail_panels()
        analysis = self._current
        if analysis is None:
            self._summary.setText("No analysis available for this image. Use Analyse from Reference Images.")
            return

        overall = analysis.overall_confidence()
        perf = analysis.performance
        perf_text = ""
        if perf:
            perf_text = (
                f" · {perf.processing_time_ms:.0f}ms · {perf.image_width}×{perf.image_height}"
                f" · {perf.memory_usage_mb:.1f} MB"
            )
        self._summary.setText(
            f"Analysis {analysis.analysis_id[:8]}… · Overall confidence {overall:.1f}%"
            f" · Review: {analysis.review_status.value}{perf_text}"
        )

        for index, colour in enumerate(analysis.colours):
            swatch = QFrame()
            swatch.setFixedSize(28, 28)
            swatch.setStyleSheet(
                f"background: {colour.channels.hex_value}; border: 1px solid {Theme.BORDER}; border-radius: 4px;"
            )
            label = QLabel(f"{colour.name}\n{colour.channels.hex_value} ({colour.confidence:.0f}%)")
            label.setFont(Typography.caption())
            if colour.catalogue_match:
                label.setText(f"{label.text()}\nCatalogue: {colour.catalogue_match}")
            row, col = divmod(index, 2)
            self._colour_grid.addWidget(swatch, row * 2, col)
            self._colour_grid.addWidget(label, row * 2 + 1, col)

        for row, (name, value) in enumerate(sorted(analysis.confidence_summary.items())):
            self._confidence_table.insertRow(row)
            self._confidence_table.setItem(row, 0, QTableWidgetItem(name))
            self._confidence_table.setItem(row, 1, QTableWidgetItem(f"{value:.1f}%"))

        rows: list[tuple[str, str, float]] = []
        if analysis.shapes:
            rows.extend(
                [
                    ("Collar position Y", f"{analysis.shapes.collar_position_y.value:.3f}", analysis.shapes.collar_position_y.confidence),
                    ("Sleeve length ratio", f"{analysis.shapes.sleeve_length_ratio.value:.3f}", analysis.shapes.sleeve_length_ratio.confidence),
                    ("Neck opening ratio", f"{analysis.shapes.neck_opening_width_ratio.value:.3f}", analysis.shapes.neck_opening_width_ratio.confidence),
                    ("Shoulder width ratio", f"{analysis.shapes.shoulder_width_ratio.value:.3f}", analysis.shapes.shoulder_width_ratio.confidence),
                    ("Body height ratio", f"{analysis.shapes.body_height_ratio.value:.3f}", analysis.shapes.body_height_ratio.confidence),
                ]
            )
        if analysis.patterns:
            rows.extend(
                [
                    ("Pattern coverage %", f"{analysis.patterns.coverage_percent.value:.1f}", analysis.patterns.coverage_percent.confidence),
                    ("Pattern density", f"{analysis.patterns.density.value:.3f}", analysis.patterns.density.confidence),
                    ("Pattern orientation °", f"{analysis.patterns.orientation_degrees.value:.1f}", analysis.patterns.orientation_degrees.confidence),
                    ("Pattern frequency", f"{analysis.patterns.frequency.value:.3f}", analysis.patterns.frequency.confidence),
                ]
            )
        self._measurements_table.setRowCount(len(rows))
        for row_index, (name, value, confidence) in enumerate(rows):
            self._measurements_table.setItem(row_index, 0, QTableWidgetItem(name))
            self._measurements_table.setItem(row_index, 1, QTableWidgetItem(value))
            self._measurements_table.setItem(row_index, 2, QTableWidgetItem(f"{confidence:.1f}%"))

        for mapping in analysis.suggested_mappings:
            checkbox = QCheckBox(
                f"{mapping.design_spec_field} → {mapping.suggested_value} "
                f"({mapping.confidence:.0f}% from {mapping.source_measurement})"
            )
            checkbox.setChecked(not mapping.accepted)
            checkbox.setEnabled(not mapping.accepted)
            self._mapping_checks[mapping.mapping_id] = checkbox
            self._mappings_host.addWidget(checkbox)

        if analysis.warnings:
            self._warnings.setText("Warnings: " + " · ".join(analysis.warnings))

        self._populate_spec_table()
        self._populate_interpretation()

    def _populate_spec_table(self) -> None:
        if self._design is None or self._document is None:
            return
        spec = self._design.ensure_spec(self._document)
        fields = (
            "primary_colour",
            "secondary_colour",
            "third_colour",
            "collar_colour",
            "sleeve_colour",
            "trim_colour",
            "collar_style",
            "sleeve_style",
            "pattern",
        )
        self._spec_table.setRowCount(len(fields))
        for row, field in enumerate(fields):
            self._spec_table.setItem(row, 0, QTableWidgetItem(field))
            value = str(spec.get_field(field) or "")
            self._spec_table.setItem(row, 1, QTableWidgetItem(value))

    def _populate_interpretation(self) -> None:
        if self._interpretation is None or self._current is None:
            return
        self._interpretation_result = self._interpretation.latest_for_analysis(self._current.analysis_id)
        has_analysis = self._current is not None
        self._interpret_btn.setEnabled(has_analysis)
        if self._interpretation_result is None:
            mode = "offline manual mode" if self._interpretation.is_offline_mode else "AI provider ready"
            self._ai_status.setText(f"No interpretation yet. Provider: {mode}.")
            return
        result = self._interpretation_result
        perf = result.performance
        perf_text = f" · {perf.total_ms:.0f}ms total" if perf else ""
        self._ai_status.setText(
            f"Interpretation {result.interpretation_id[:8]}… · Provider: {result.ai_provider}"
            f" · {len(result.suggestions)} suggestion(s){perf_text}"
            + (" · Offline mode" if result.offline_mode else "")
        )
        has_pending = any(s.status == SuggestionStatus.PENDING for s in result.suggestions)
        for suggestion in result.suggestions:
            row = _SuggestionRow(suggestion)
            self._suggestion_rows[suggestion.suggestion_id] = row
            self._suggestions_host.addWidget(row)
        for button in (
            self._accept_ai_all_btn,
            self._accept_ai_selected_btn,
            self._reject_ai_selected_btn,
            self._reject_ai_all_btn,
        ):
            button.setEnabled(has_pending)

    def _generate_interpretation(self) -> None:
        if self._interpretation is None or self._document is None or self._current is None:
            return
        user = self._document.manifest.author or "Operator"
        try:
            while self._suggestions_host.count():
                item = self._suggestions_host.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self._suggestion_rows.clear()
            self._interpretation_result = self._interpretation.interpret_analysis(
                self._document,
                self._current,
                user=user,
            )
            self._populate_interpretation()
            self.analysis_changed.emit()
        except InterpretationError as exc:
            QMessageBox.warning(self, "Interpretation Failed", str(exc))

    def _accept_all(self) -> None:
        if not self._current or self._vision is None or self._document is None:
            return
        user = self._document.manifest.author or "Operator"
        self._vision.accept_mappings(
            self._document,
            self._current.analysis_id,
            None,
            user=user,
            accept_all=True,
        )
        self._populate_details()
        self.analysis_changed.emit()

    def _accept_selected(self) -> None:
        if not self._current or self._vision is None or self._document is None:
            return
        selected = [mapping_id for mapping_id, checkbox in self._mapping_checks.items() if checkbox.isChecked()]
        if not selected:
            QMessageBox.information(self, "Accept Selected", "Select at least one suggested mapping.")
            return
        user = self._document.manifest.author or "Operator"
        self._vision.accept_mappings(
            self._document,
            self._current.analysis_id,
            selected,
            user=user,
        )
        self._populate_details()
        self.analysis_changed.emit()

    def _reject(self) -> None:
        if not self._current or self._vision is None or self._document is None:
            return
        user = self._document.manifest.author or "Operator"
        self._vision.reject_analysis(self._document, self._current.analysis_id, user=user)
        self._populate_details()
        self.analysis_changed.emit()

    def _reanalyse(self) -> None:
        index = self._image_selector.currentIndex()
        if index < 0:
            return
        image_id = self._image_selector.itemData(index)
        if image_id:
            self.run_analysis(image_id)

    def _accept_ai_all(self) -> None:
        self._accept_ai_suggestions(accept_all=True)

    def _accept_ai_selected(self) -> None:
        selected = [
            sid for sid, row in self._suggestion_rows.items() if row.checkbox.isChecked()
        ]
        if not selected:
            QMessageBox.information(self, "Accept Selected AI", "Select at least one AI suggestion.")
            return
        self._accept_ai_suggestions(suggestion_ids=selected)

    def _accept_ai_suggestions(
        self,
        *,
        accept_all: bool = False,
        suggestion_ids: list[str] | None = None,
    ) -> None:
        if not self._interpretation_result or self._interpretation is None or self._document is None:
            return
        edited = {
            sid: row.value_edit.text().strip()
            for sid, row in self._suggestion_rows.items()
        }
        user = self._document.manifest.author or "Operator"
        try:
            self._interpretation.accept_suggestions(
                self._document,
                self._interpretation_result.interpretation_id,
                suggestion_ids,
                user=user,
                accept_all=accept_all,
                edited_values=edited,
            )
            self._populate_spec_table()
            self._populate_interpretation()
            self.analysis_changed.emit()
        except InterpretationError as exc:
            QMessageBox.warning(self, "Accept Failed", str(exc))

    def _reject_ai_selected(self) -> None:
        if not self._interpretation_result or self._interpretation is None or self._document is None:
            return
        selected = [
            sid for sid, row in self._suggestion_rows.items() if row.checkbox.isChecked()
        ]
        if not selected:
            QMessageBox.information(self, "Reject Selected AI", "Select at least one AI suggestion.")
            return
        user = self._document.manifest.author or "Operator"
        for suggestion_id in selected:
            self._interpretation.reject_suggestion(
                self._document,
                self._interpretation_result.interpretation_id,
                suggestion_id,
                user=user,
            )
        self._populate_interpretation()
        self.analysis_changed.emit()

    def _reject_ai_all(self) -> None:
        if not self._interpretation_result or self._interpretation is None or self._document is None:
            return
        user = self._document.manifest.author or "Operator"
        self._interpretation.reject_all(
            self._document,
            self._interpretation_result.interpretation_id,
            user=user,
        )
        self._populate_interpretation()
        self.analysis_changed.emit()
