"""Template Inspector — detailed PSD template view."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from models.psd_template import PSDTemplate, TemplateValidationReport
from services.template_manager_service import TemplateManagerService
from ui.theme import Theme
from ui.typography import Typography


class TemplateInspectorDialog(QDialog):
    def __init__(
        self,
        template: PSDTemplate,
        manager: TemplateManagerService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Template Inspector — {template.name}")
        self.resize(760, 640)
        root = QVBoxLayout(self)
        root.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        header = QLabel(template.template_id)
        header.setFont(Typography.caption())
        header.setProperty("muted", True)
        root.addWidget(header)

        tabs = QTabWidget()
        analysis = manager.manager.analysis(template.template_id)
        mappings = manager.manager.mappings(template.template_id)
        anchors = manager.manager.anchors(template.template_id)
        validation = manager.manager.validation(template.template_id)

        tabs.addTab(self._general_tab(template, validation), "General")
        tabs.addTab(self._text_tab(self._layer_structure(analysis)), "Layer Structure")
        tabs.addTab(self._text_tab(self._mapped_components(mappings)), "Mapped Components")
        tabs.addTab(self._text_tab(self._anchor_points(anchors)), "Anchor Points")
        tabs.addTab(self._text_tab(self._validation_text(validation)), "Validation")
        tabs.addTab(self._text_tab(self._compatibility(template)), "Compatibility")
        root.addWidget(tabs)

    def _general_tab(self, template: PSDTemplate, validation: TemplateValidationReport | None) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        lines = [
            f"Name: {template.name}",
            f"Version: {template.version}",
            f"Status: {template.status.value}",
            f"Description: {template.description}",
            f"PSD Path: {template.psd_path}",
            f"Layer Count: {validation.layer_count if validation else 0}",
            f"Smart Objects: {validation.smart_object_count if validation else 0}",
            f"Anchors: {validation.anchor_count if validation else 0}",
            f"Mappings: {validation.mapping_count if validation else 0}",
        ]
        label = QLabel("\n".join(lines))
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return widget

    def _text_tab(self, text: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(text)
        layout.addWidget(editor)
        return widget

    @staticmethod
    def _layer_structure(analysis) -> str:
        if analysis is None:
            return "No analysis available."
        lines = [
            f"Canvas: {analysis.canvas_width}×{analysis.canvas_height} @ {analysis.resolution_ppi} ppi",
            f"Colour mode: {analysis.colour_mode} · Profile: {analysis.colour_profile}",
            f"PSD version: {analysis.psd_version}",
            "",
        ]
        for layer in analysis.layers:
            indent = "  " if layer.parent_id else ""
            flags = []
            if layer.is_group:
                flags.append("group")
            if layer.is_smart_object:
                flags.append("smart object")
            if layer.is_adjustment:
                flags.append("adjustment")
            if layer.has_mask:
                flags.append("mask")
            flag_text = f" [{', '.join(flags)}]" if flags else ""
            lines.append(f"{indent}{layer.layer_id} · {layer.name}{flag_text}")
        return "\n".join(lines)

    @staticmethod
    def _mapped_components(mappings) -> str:
        if mappings is None:
            return "No mappings configured."
        lines = []
        for rule in mappings.mappings:
            target = rule.smart_object_id or rule.psd_layer_name
            lines.append(f"{rule.design_spec_field} → {target} ({rule.render_layer or '—'})")
        return "\n".join(lines)

    @staticmethod
    def _anchor_points(anchors) -> str:
        if anchors is None:
            return "No anchors configured."
        lines = []
        for anchor in anchors.anchors:
            lines.append(
                f"{anchor.anchor_id} · {anchor.name} [{anchor.role}] @ ({anchor.x:.2f}, {anchor.y:.2f})"
            )
        return "\n".join(lines)

    @staticmethod
    def _validation_text(validation: TemplateValidationReport | None) -> str:
        if validation is None:
            return "Validation has not been run."
        lines = [f"Valid: {validation.valid}", ""]
        for issue in validation.issues:
            lines.append(f"[{issue.severity}] {issue.code}: {issue.message}")
        return "\n".join(lines)

    @staticmethod
    def _compatibility(template: PSDTemplate) -> str:
        lines = [
            "Build profiles:",
            *[f"  • {profile}" for profile in template.build_profile_compatibility],
            "",
            "Output profiles:",
            *[f"  • {profile}" for profile in template.supported_output_profiles],
            "",
            "Collar types:",
            *[f"  • {item}" for item in template.supported_collar_types[:8]],
            "",
            "Sleeve types:",
            *[f"  • {item}" for item in template.supported_sleeve_types[:8]],
        ]
        return "\n".join(lines)
