"""Design Specification editor — grouped panels with live updates."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.design_specification import DesignSpecification, OutputProfile
from models.project import KitType, ProjectDocument
from services.design_catalogue_service import DesignCatalogues
from services.design_spec_validation import ValidationResult
from services.design_specification_service import DesignSpecificationService
from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography


class _Panel(QFrame):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_MD, Theme.SPACING_LG, Theme.SPACING_MD)
        layout.setSpacing(Theme.SPACING_MD)
        heading = QLabel(title)
        heading.setFont(Typography.subheading())
        self._form = QFormLayout()
        self._form.setSpacing(Theme.SPACING_SM)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(heading)
        layout.addLayout(self._form)

    def add_row(self, label: str, widget: QWidget) -> None:
        name = QLabel(label)
        name.setFont(Typography.body())
        self._form.addRow(name, widget)


class DesignSpecificationEditor(QFrame):
    """Professional grouped editor for the canonical jersey design specification."""

    specification_changed = Signal()
    validation_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: DesignSpecificationService | None = None
        self._document: ProjectDocument | None = None
        self._catalogues: DesignCatalogues | None = None
        self._binding = False
        self._fields: dict[str, QWidget] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        root.setSpacing(Theme.SPACING_MD)

        header = QHBoxLayout()
        glyph = QLabel()
        glyph.setPixmap(icon("design", color=Theme.ACCENT, size=20).pixmap(20, 20))
        title_block = QVBoxLayout()
        self._title = QLabel("Design Specification")
        self._title.setFont(Typography.heading())
        self._subtitle = QLabel("Canonical jersey data model")
        self._subtitle.setProperty("muted", True)
        self._subtitle.setFont(Typography.caption())
        title_block.addWidget(self._title)
        title_block.addWidget(self._subtitle)
        header.addWidget(glyph)
        header.addLayout(title_block)
        header.addStretch(1)
        self._validation_badge = QLabel("Not validated")
        self._validation_badge.setFont(Typography.caption())
        header.addWidget(self._validation_badge)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        panels = QVBoxLayout(host)
        panels.setSpacing(Theme.SPACING_MD)

        self._panel_project = _Panel("Project")
        self._panel_colours = _Panel("Colours")
        self._panel_construction = _Panel("Construction")
        self._panel_pattern = _Panel("Pattern")
        self._panel_effects = _Panel("Effects")
        self._panel_output = _Panel("Output")
        self._panel_validation = _Panel("Validation")
        self._panel_notes = _Panel("Notes")

        self._validation_list = QLabel("No validation issues.")
        self._validation_list.setWordWrap(True)
        self._validation_list.setProperty("muted", True)
        self._panel_validation.add_row("Status", self._validation_list)

        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Operator notes for this design…")
        self._notes.setMinimumHeight(100)
        self._panel_notes.add_row("Notes", self._notes)

        for panel in (
            self._panel_project,
            self._panel_colours,
            self._panel_construction,
            self._panel_pattern,
            self._panel_effects,
            self._panel_output,
            self._panel_validation,
            self._panel_notes,
        ):
            panels.addWidget(panel)
        panels.addStretch(1)

        scroll.setWidget(host)
        root.addLayout(header)
        root.addWidget(scroll, stretch=1)

        self._build_fields()

    def set_service(self, service: DesignSpecificationService) -> None:
        self._service = service
        self._catalogues = service.catalogues
        self._populate_catalogue_widgets()

    def set_project(self, document: ProjectDocument | None) -> None:
        self._document = document
        if document is None or self._service is None:
            self._set_enabled(False)
            return
        self._set_enabled(True)
        spec = self._service.ensure_spec(document)
        self._subtitle.setText(f"{spec.club or document.manifest.club_name} · {spec.season or document.manifest.season}")
        self._load_spec(spec)
        self._refresh_validation(spec)

    def _set_enabled(self, enabled: bool) -> None:
        self.setEnabled(enabled)
        if not enabled:
            self._subtitle.setText("Open a project to edit the design specification")

    def _build_fields(self) -> None:
        self._add_text(self._panel_project, "club", "Club")
        self._add_text(self._panel_project, "competition", "Competition")
        self._add_text(self._panel_project, "season", "Season")
        self._add_combo(
            self._panel_project,
            "kit_type",
            "Kit Type",
            [item.value for item in KitType],
        )
        self._add_text(self._panel_project, "manufacturer", "Manufacturer")

        colour_grid = QWidget()
        grid = QGridLayout(colour_grid)
        grid.setSpacing(Theme.SPACING_SM)
        for index, (name, label) in enumerate(
            (
                ("primary_colour", "Primary"),
                ("secondary_colour", "Secondary"),
                ("third_colour", "Third"),
                ("sleeve_colour", "Sleeve"),
                ("collar_colour", "Collar"),
                ("trim_colour", "Trim"),
            )
        ):
            field = QLineEdit()
            field.setPlaceholderText("#RRGGBB")
            field.editingFinished.connect(lambda n=name, w=field: self._on_text_changed(n, w))
            self._fields[name] = field
            row, col = divmod(index, 2)
            cell = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setFont(Typography.caption())
            cell.addWidget(lbl)
            cell.addWidget(field)
            wrap = QWidget()
            wrap.setLayout(cell)
            grid.addWidget(wrap, row, col)
        self._panel_colours._form.addRow("Palette", colour_grid)

        self._add_catalogue_combo(self._panel_construction, "sleeve_style", "Sleeve Style", "sleeves")
        self._add_catalogue_combo(self._panel_construction, "collar_style", "Collar Style", "collars")
        self._add_catalogue_combo(self._panel_construction, "trim_style", "Trim Style", "trims")
        self._add_catalogue_combo(self._panel_construction, "material_style", "Material", "materials")

        self._add_catalogue_combo(self._panel_pattern, "pattern", "Pattern", "patterns")
        self._add_spin(self._panel_pattern, "pattern_scale", "Pattern Scale", 0.1, 5.0, 0.1, 2)
        self._add_spin(self._panel_pattern, "pattern_rotation", "Pattern Rotation", -360.0, 360.0, 1.0, 0)
        self._add_spin(self._panel_pattern, "pattern_opacity", "Pattern Opacity", 0.0, 1.0, 0.05, 2)

        self._add_catalogue_combo(self._panel_effects, "shadow_style", "Shadow", "shadows")
        self._add_catalogue_combo(self._panel_effects, "lighting_style", "Lighting", "lighting")
        self._add_catalogue_combo(self._panel_effects, "texture_style", "Texture", "textures")

        self._add_combo(
            self._panel_output,
            "output_profile",
            "Output Profile",
            [item.value for item in OutputProfile],
        )

        self._notes.textChanged.connect(self._on_notes_changed)

    def _add_text(self, panel: _Panel, name: str, label: str) -> None:
        field = QLineEdit()
        field.editingFinished.connect(lambda n=name, w=field: self._on_text_changed(n, w))
        self._fields[name] = field
        panel.add_row(label, field)

    def _add_combo(self, panel: _Panel, name: str, label: str, items: list[str]) -> None:
        field = QComboBox()
        field.addItems(items)
        field.currentTextChanged.connect(lambda _text, n=name, w=field: self._on_combo_changed(n, w))
        self._fields[name] = field
        panel.add_row(label, field)

    def _add_catalogue_combo(self, panel: _Panel, name: str, label: str, category: str) -> None:
        field = QComboBox()
        field.setProperty("catalogue_category", category)
        field.currentTextChanged.connect(lambda _text, n=name, w=field: self._on_catalogue_changed(n, w))
        self._fields[name] = field
        panel.add_row(label, field)

    def _add_spin(
        self,
        panel: _Panel,
        name: str,
        label: str,
        minimum: float,
        maximum: float,
        step: float,
        decimals: int,
    ) -> None:
        field = QDoubleSpinBox()
        field.setRange(minimum, maximum)
        field.setSingleStep(step)
        field.setDecimals(decimals)
        field.valueChanged.connect(lambda _value, n=name, w=field: self._on_spin_changed(n, w))
        self._fields[name] = field
        panel.add_row(label, field)

    def _populate_catalogue_widgets(self) -> None:
        if self._catalogues is None:
            return
        mapping = {
            "sleeves": self._catalogues.sleeves,
            "collars": self._catalogues.collars,
            "materials": self._catalogues.materials,
            "patterns": self._catalogues.patterns,
            "trims": self._catalogues.trims,
            "shadows": self._catalogues.shadows,
            "lighting": self._catalogues.lighting,
            "textures": self._catalogues.textures,
        }
        for widget in self._fields.values():
            if not isinstance(widget, QComboBox):
                continue
            category = widget.property("catalogue_category")
            if not category:
                continue
            widget.blockSignals(True)
            widget.clear()
            widget.addItem("")
            for item in mapping[str(category)]:
                widget.addItem(item.label, item.id)
            widget.blockSignals(False)

    def _load_spec(self, spec: DesignSpecification) -> None:
        self._binding = True
        try:
            for name, widget in self._fields.items():
                value = spec.get_field(name)
                if isinstance(widget, QLineEdit):
                    widget.setText(_display_value(value))
                elif isinstance(widget, QComboBox):
                    if widget.property("catalogue_category") and self._catalogues:
                        category = str(widget.property("catalogue_category"))
                        stored = str(value)
                        label = self._catalogues.label_for_id(category, stored)
                        index = widget.findText(label)
                        if index < 0:
                            index = widget.findData(self._catalogues.id_for_reference(category, stored))
                        widget.setCurrentIndex(max(0, index))
                    else:
                        widget.setCurrentText(_display_value(value))
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value))
            self._notes.blockSignals(True)
            self._notes.setPlainText(spec.operator_notes)
            self._notes.blockSignals(False)
        finally:
            self._binding = False

    def _refresh_validation(self, spec: DesignSpecification) -> None:
        if self._service is None:
            return
        result = self._service.validate(spec)
        self._validation_badge.setText(result.status.value)
        colour = Theme.SUCCESS if result.is_valid else Theme.WARNING if result.issues else Theme.TEXT_MUTED
        self._validation_badge.setStyleSheet(f"color: {colour}; font-weight: 600;")
        if result.issues:
            lines = [f"• {issue.field}: {issue.message}" for issue in result.issues]
            self._validation_list.setText("\n".join(lines))
        else:
            self._validation_list.setText("All validation rules passed.")
        self.validation_changed.emit(result)

    def _apply(self, name: str, value: Any) -> None:
        if self._binding or self._document is None or self._service is None:
            return
        user = self._document.manifest.author or "Operator"
        spec = self._service.apply_change(self._document, name, value, user=user)
        self._refresh_validation(spec)
        self.specification_changed.emit()

    def _on_text_changed(self, name: str, widget: QLineEdit) -> None:
        self._apply(name, widget.text().strip())

    def _on_combo_changed(self, name: str, widget: QComboBox) -> None:
        text = widget.currentText()
        if name == "kit_type":
            self._apply(name, KitType(text))
            return
        if name == "output_profile":
            self._apply(name, OutputProfile(text))
            return
        self._apply(name, text)

    def _on_catalogue_changed(self, name: str, widget: QComboBox) -> None:
        item_id = widget.currentData()
        if item_id:
            self._apply(name, str(item_id))
        elif widget.currentText():
            category = str(widget.property("catalogue_category"))
            if self._catalogues:
                self._apply(name, self._catalogues.id_for_label(category, widget.currentText()))
        else:
            self._apply(name, "")

    def _on_spin_changed(self, name: str, widget: QDoubleSpinBox) -> None:
        self._apply(name, widget.value())

    def _on_notes_changed(self) -> None:
        self._apply("operator_notes", self._notes.toPlainText())


def _display_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value) if value is not None else ""
