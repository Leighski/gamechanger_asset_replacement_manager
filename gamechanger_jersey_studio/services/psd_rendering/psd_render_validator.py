"""PSD Render validation — abort export when prerequisites fail."""

from __future__ import annotations

from models.design_specification import DesignSpecification
from models.component_catalogue import DESIGN_SPEC_CATALOGUE_FIELDS
from models.psd_template import PublishedTemplateMappings
from models.psd_render import PSDRenderValidationIssue
from services.rendering.component_assembler import ComponentAssembler


REQUIRED_COLOUR_FIELDS = (
    "primary_colour",
    "secondary_colour",
    "sleeve_colour",
    "collar_colour",
    "trim_colour",
)


class PSDRenderValidator:
    """Validate mappings, components, colours, and PSD layer presence."""

    def validate(
        self,
        spec: DesignSpecification,
        mappings: PublishedTemplateMappings,
        assembler: ComponentAssembler,
        layer_index: dict[str, object],
    ) -> list[PSDRenderValidationIssue]:
        issues: list[PSDRenderValidationIssue] = []

        if mappings.analysis is None:
            issues.append(
                PSDRenderValidationIssue(
                    severity="error",
                    code="analysis_missing",
                    message="Template analysis is required for PSD rendering.",
                )
            )

        for field in REQUIRED_COLOUR_FIELDS:
            value = str(spec.get_field(field) or "").strip()
            if not value:
                issues.append(
                    PSDRenderValidationIssue(
                        severity="error",
                        code="missing_colour",
                        message=f"Required colour not set: {field}",
                        field_name=field,
                    )
                )

        seen_fields: set[str] = set()
        for rule in mappings.mappings:
            if rule.design_spec_field in seen_fields:
                continue
            seen_fields.add(rule.design_spec_field)
            if rule.design_spec_field not in DESIGN_SPEC_CATALOGUE_FIELDS:
                continue
            reference = str(spec.get_field(rule.design_spec_field) or "").strip()
            if not reference:
                issues.append(
                    PSDRenderValidationIssue(
                        severity="error",
                        code="missing_component_reference",
                        message=f"No catalogue reference for {rule.design_spec_field}",
                        field_name=rule.design_spec_field,
                    )
                )
                continue
            if rule.component_category and rule.design_spec_field in DESIGN_SPEC_CATALOGUE_FIELDS:
                component = assembler.resolve_field(rule.design_spec_field, reference)
                if component is None:
                    issues.append(
                        PSDRenderValidationIssue(
                            severity="error",
                            code="component_not_found",
                            message=f"Catalogue component not found for {rule.design_spec_field}={reference}",
                            field_name=rule.design_spec_field,
                        )
                    )

            layer_name = rule.psd_layer_name
            if layer_name and layer_name not in layer_index:
                issues.append(
                    PSDRenderValidationIssue(
                        severity="error",
                        code="mapped_layer_missing",
                        message=f"Mapped PSD layer not found: {layer_name}",
                        field_name=rule.design_spec_field,
                        layer_name=layer_name,
                    )
                )

            if rule.smart_object_id and mappings.analysis:
                smart_ids = {record.smart_object_id for record in mappings.analysis.smart_objects}
                if rule.smart_object_id not in smart_ids:
                    issues.append(
                        PSDRenderValidationIssue(
                            severity="warning",
                            code="smart_object_unresolved",
                            message=f"Smart Object ID not in analysis: {rule.smart_object_id}",
                            field_name=rule.design_spec_field,
                            layer_name=layer_name,
                        )
                    )

        return issues

    @staticmethod
    def has_errors(issues: list[PSDRenderValidationIssue]) -> bool:
        return any(issue.severity == "error" for issue in issues)
