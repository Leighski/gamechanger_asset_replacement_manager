"""Design Specification validation rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from models.component_catalogue import (
    DESIGN_SPEC_CATALOGUE_FIELDS,
    ComponentCategory,
    ComponentLibrary,
)
from models.design_specification import DesignSpecification
from models.project import ValidationStatus
from services.design_catalogue_service import DesignCatalogues, load_catalogues


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    section: str
    field: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)
    status: ValidationStatus = ValidationStatus.NOT_STARTED

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    def issues_for_section(self, section: str) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.section == section]

    def section_valid(self, section: str) -> bool:
        return not any(
            issue.section == section and issue.severity == ValidationSeverity.ERROR
            for issue in self.issues
        )


PATTERN_OPACITY_MIN = 0.0
PATTERN_OPACITY_MAX = 1.0

COLOUR_FIELDS = (
    "primary_colour",
    "secondary_colour",
    "third_colour",
    "sleeve_colour",
    "collar_colour",
    "trim_colour",
)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _format_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def validate_design_specification(
    spec: DesignSpecification,
    catalogues: DesignCatalogues | None = None,
    component_library: ComponentLibrary | None = None,
) -> ValidationResult:
    cats = catalogues or load_catalogues()
    if component_library is None and cats:
        from core.paths import COMPONENT_LIBRARY_DIR
        from services.catalogue.loader import CatalogueLoader

        if COMPONENT_LIBRARY_DIR.is_dir():
            component_library = CatalogueLoader(COMPONENT_LIBRARY_DIR).load_library()
            if not component_library.all_components():
                component_library = None

    issues: list[ValidationIssue] = []

    for field_name in ("club", "competition", "season", "manufacturer"):
        if _is_empty(spec.get_field(field_name)):
            issues.append(
                ValidationIssue(
                    section="project_information",
                    field=field_name,
                    message=f"{field_name.replace('_', ' ').title()} cannot be empty.",
                )
            )

    for field_name in COLOUR_FIELDS:
        if _is_empty(spec.get_field(field_name)):
            issues.append(
                ValidationIssue(
                    section="colours",
                    field=field_name,
                    message=f"{field_name.replace('_', ' ').title()} cannot be empty.",
                )
            )

    _validate_catalogue_field(
        issues,
        spec,
        "pattern",
        "pattern",
        ComponentCategory.PATTERNS,
        cats,
        component_library,
        required=True,
    )

    if spec.pattern_opacity < PATTERN_OPACITY_MIN or spec.pattern_opacity > PATTERN_OPACITY_MAX:
        issues.append(
            ValidationIssue(
                section="pattern",
                field="pattern_opacity",
                message=(
                    f"Pattern opacity must be between {PATTERN_OPACITY_MIN} "
                    f"and {PATTERN_OPACITY_MAX}."
                ),
            )
        )

    for field_name, category in (
        ("collar_style", ComponentCategory.COLLARS),
        ("sleeve_style", ComponentCategory.SLEEVES),
        ("trim_style", ComponentCategory.TRIMS),
        ("material_style", ComponentCategory.MATERIALS),
        ("shadow_style", ComponentCategory.SHADOW_PROFILES),
        ("lighting_style", ComponentCategory.LIGHTING_PROFILES),
        ("texture_style", ComponentCategory.TEXTURES),
    ):
        section = "effects" if field_name in ("shadow_style", "lighting_style", "texture_style") else "construction"
        _validate_catalogue_field(
            issues,
            spec,
            section,
            field_name,
            category,
            cats,
            component_library,
            required=False,
        )

    if issues:
        status = ValidationStatus.FAILED if any(i.severity == ValidationSeverity.ERROR for i in issues) else ValidationStatus.PENDING
    else:
        status = ValidationStatus.PASSED

    return ValidationResult(issues=issues, status=status)


def _validate_catalogue_field(
    issues: list[ValidationIssue],
    spec: DesignSpecification,
    section: str,
    field_name: str,
    category: ComponentCategory,
    cats: DesignCatalogues,
    library: ComponentLibrary | None,
    *,
    required: bool,
) -> None:
    value = str(spec.get_field(field_name) or "")
    if _is_empty(value):
        if required:
            issues.append(
                ValidationIssue(
                    section=section,
                    field=field_name,
                    message=f"{field_name.replace('_', ' ').title()} must be selected from the catalogue.",
                )
            )
        return

    component = library.get_component(category, value) if library else None
    if component is None:
        id_sets = {
            ComponentCategory.COLLARS: cats.collar_ids(),
            ComponentCategory.PATTERNS: cats.pattern_ids(),
            ComponentCategory.SLEEVES: cats.sleeve_ids(),
            ComponentCategory.MATERIALS: cats.material_ids(),
            ComponentCategory.TRIMS: cats.trim_ids(),
            ComponentCategory.SHADOW_PROFILES: cats.shadow_ids(),
            ComponentCategory.LIGHTING_PROFILES: cats.lighting_ids(),
            ComponentCategory.TEXTURES: cats.texture_ids(),
        }
        allowed = id_sets.get(category, set())
        if value not in allowed:
            issues.append(
                ValidationIssue(
                    section=section,
                    field=field_name,
                    message=f"{field_name.replace('_', ' ').title()} '{value}' is not in the catalogue.",
                )
            )
            return
        return

    from models.component_catalogue import ComponentStatus

    if component.status == ComponentStatus.DEPRECATED:
        issues.append(
            ValidationIssue(
                section=section,
                field=field_name,
                message=f"Component '{component.name}' is deprecated.",
                severity=ValidationSeverity.WARNING,
            )
        )
    elif component.status in (ComponentStatus.DRAFT, ComponentStatus.REVIEW):
        issues.append(
            ValidationIssue(
                section=section,
                field=field_name,
                message=f"Component '{component.name}' is {component.status.value} — not certified for production.",
                severity=ValidationSeverity.WARNING,
            )
        )
