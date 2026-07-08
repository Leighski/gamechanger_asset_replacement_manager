"""Project tree explorer."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from models.project import ProjectDocument
from models.reference_image import ImageCategory
from services.design_spec_validation import ValidationResult
from services.design_specification_service import DesignSpecificationService
from services.reference_image_service import ReferenceImageService
from ui.theme import Theme
from ui.typography import Typography

TREE_SECTIONS = (
    ("Project Information", None),
    ("Reference Images", "No reference images have been imported."),
    ("Design Specification", "Create a Design Specification to begin."),
    ("Generated Artwork", "No generated artwork yet."),
    ("Validation", "No validation reports available."),
    ("Reports", "No reports available."),
    ("History", "No project history recorded."),
)

DESIGN_SPEC_SECTIONS = (
    ("Project", "project_information"),
    ("Colours", "colours"),
    ("Construction", "construction"),
    ("Pattern", "pattern"),
    ("Effects", "effects"),
    ("Output", "output"),
    ("Notes", "notes"),
)


class ProjectTree(QFrame):
    section_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setMinimumWidth(240)
        self.setMaximumWidth(320)
        self._design_service: DesignSpecificationService | None = None
        self._reference_service: ReferenceImageService | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_MD, Theme.SPACING_LG, Theme.SPACING_MD, Theme.SPACING_LG)
        layout.setSpacing(Theme.SPACING_SM)

        heading = QLabel("Project Explorer")
        heading.setFont(Typography.subheading())

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._build_empty_tree()

        layout.addWidget(heading)
        layout.addWidget(self._tree, stretch=1)
        self._tree.itemClicked.connect(self._on_item_clicked)

    def set_design_service(self, service: DesignSpecificationService) -> None:
        self._design_service = service

    def set_reference_service(self, service: ReferenceImageService) -> None:
        self._reference_service = service

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        text = item.text(0)
        if text == "Reference Images" or item.parent() and item.parent().text(0) == "Reference Images":
            self.section_selected.emit("references")

    def _empty_child(self, message: str) -> QTreeWidgetItem:
        child = QTreeWidgetItem([message])
        child.setForeground(0, QColor(Theme.TEXT_MUTED))
        child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return child

    def _section_child(self, label: str, valid: bool | None = None) -> QTreeWidgetItem:
        text = label
        if valid is True:
            text = f"✓ {label}"
        elif valid is False:
            text = f"✗ {label}"
        child = QTreeWidgetItem([text])
        child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if valid is True:
            child.setForeground(0, QColor(Theme.SUCCESS))
        elif valid is False:
            child.setForeground(0, QColor(Theme.ERROR))
        return child

    def _build_empty_tree(self) -> None:
        self._tree.clear()
        for label, empty_message in TREE_SECTIONS:
            item = QTreeWidgetItem([label])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if empty_message:
                item.addChild(self._empty_child(empty_message))
            self._tree.addTopLevelItem(item)
        self._tree.expandAll()

    def set_project(self, document: ProjectDocument | None) -> None:
        self._tree.clear()
        if document is None:
            self._build_empty_tree()
            return

        manifest = document.manifest
        validation: ValidationResult | None = None
        if self._design_service is not None:
            spec = self._design_service.ensure_spec(document)
            validation = self._design_service.validate(spec)

        sections: dict[str, list[QTreeWidgetItem]] = {
            "Project Information": [
                self._section_child(manifest.project_name),
                self._section_child(manifest.club_name),
                self._section_child(f"{manifest.competition} — {manifest.season}"),
                self._section_child(manifest.kit_type.value),
            ],
            "Reference Images": self._reference_children(document),
            "Design Specification": self._design_spec_children(validation),
            "Generated Artwork": (
                [self._section_child(f"{manifest.generated_output_count} item(s)")]
                if manifest.generated_output_count
                else [self._empty_child("No generated artwork yet.")]
            ),
            "Validation": [self._section_child(manifest.validation_status.value)],
            "Reports": [self._empty_child("No reports available.")],
            "History": (
                [self._section_child(f"{len(document.history.entries)} event(s)")]
                if document.history.entries
                else [self._empty_child("No project history recorded.")]
            ),
        }

        for label, _ in TREE_SECTIONS:
            item = QTreeWidgetItem([label])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            for child in sections.get(label, [self._empty_child("(empty)")]):
                item.addChild(child)
            self._tree.addTopLevelItem(item)
        self._tree.expandAll()

    def _design_spec_children(self, validation: ValidationResult | None) -> list[QTreeWidgetItem]:
        if validation is None:
            return [self._empty_child("Create a Design Specification to begin.")]
        children: list[QTreeWidgetItem] = []
        for label, section_key in DESIGN_SPEC_SECTIONS:
            valid = validation.section_valid(section_key) if section_key != "notes" else True
            children.append(self._section_child(label, valid))
        return children

    def _reference_children(self, document: ProjectDocument) -> list[QTreeWidgetItem]:
        if self._reference_service is None:
            return [self._empty_child("No reference images have been imported.")]
        manifest = self._reference_service.ensure_manifest(document)
        if not manifest.images:
            return [self._empty_child("No reference images have been imported.")]
        validation = self._reference_service.validate(manifest)
        children = [self._section_child(f"All Images ({len(manifest.images)})")]
        for label, tag in (
            ("Front Views", ImageCategory.FRONT_VIEW.value),
            ("Rear Views", ImageCategory.REAR_VIEW.value),
            ("Details", ImageCategory.DETAIL.value),
        ):
            count = sum(1 for image in manifest.images if image.has_tag(tag))
            children.append(self._section_child(f"{label} ({count})"))
        uncategorised = sum(1 for image in manifest.images if not image.tags)
        children.append(self._section_child(f"Uncategorised ({uncategorised})"))
        children.append(
            self._section_child(
                f"Validation ({validation.status.value})",
                valid=validation.is_valid if manifest.images else None,
            )
        )
        return children
