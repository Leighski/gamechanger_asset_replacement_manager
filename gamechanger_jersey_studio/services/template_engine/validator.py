"""Template Validator — validate PSD templates, mappings, and anchors."""

from __future__ import annotations

from models.psd_template import (
    AnchorPointSet,
    LayerMappingSet,
    PSDAnalysisReport,
    PSDTemplate,
    TemplateValidationIssue,
    TemplateValidationReport,
)
from services.logging_manager import get_logger

logger = get_logger()

SUPPORTED_COLOUR_PROFILES = {"", "embedded", "sRGB", "Adobe RGB (1998)"}
REQUIRED_ANCHOR_ROLES = (
    "collar",
    "sleeve",
    "badge",
    "sponsor",
    "manufacturer_logo",
    "number",
    "name",
)


class TemplateValidator:
    """Validate template registration, analysis, mappings, and anchors."""

    def validate(
        self,
        template: PSDTemplate,
        analysis: PSDAnalysisReport | None,
        mappings: LayerMappingSet,
        anchors: AnchorPointSet,
    ) -> TemplateValidationReport:
        issues: list[TemplateValidationIssue] = []

        if analysis is None:
            issues.append(
                TemplateValidationIssue(
                    severity="error",
                    code="analysis_missing",
                    message="PSD analysis has not been generated for this template.",
                )
            )
        else:
            issues.extend(self._validate_analysis(analysis))

        issues.extend(self._validate_mappings(mappings, analysis))
        issues.extend(self._validate_anchors(anchors))
        issues.extend(self._validate_compatibility(template))

        layer_names = [layer.name for layer in analysis.layers] if analysis else []
        duplicate_names = {name for name in layer_names if layer_names.count(name) > 1}
        for name in sorted(duplicate_names):
            issues.append(
                TemplateValidationIssue(
                    severity="warning",
                    code="duplicate_layer_name",
                    message=f"Duplicate PSD layer name: {name}",
                    layer_name=name,
                )
            )

        report = TemplateValidationReport(
            template_id=template.template_id,
            valid=not any(issue.severity == "error" for issue in issues),
            issues=issues,
            layer_count=analysis.layer_count if analysis else 0,
            smart_object_count=analysis.smart_object_count if analysis else 0,
            anchor_count=len(anchors.anchors),
            mapping_count=len(mappings.mappings),
        )
        logger.info(
            "Validation complete — template={}, valid={}, issues={}",
            template.template_id,
            report.valid,
            len(issues),
        )
        return report

    def _validate_analysis(self, analysis: PSDAnalysisReport) -> list[TemplateValidationIssue]:
        issues: list[TemplateValidationIssue] = []
        if analysis.psd_version not in {1}:
            issues.append(
                TemplateValidationIssue(
                    severity="warning",
                    code="unsupported_psd_version",
                    message=f"PSD version {analysis.psd_version} may not be fully supported.",
                )
            )
        profile = analysis.colour_profile or ""
        if profile and profile not in SUPPORTED_COLOUR_PROFILES:
            issues.append(
                TemplateValidationIssue(
                    severity="warning",
                    code="unsupported_colour_profile",
                    message=f"Colour profile '{profile}' is not in the supported list.",
                )
            )
        for warning in analysis.warnings:
            issues.append(
                TemplateValidationIssue(
                    severity="warning",
                    code="analysis_warning",
                    message=warning,
                )
            )
        return issues

    def _validate_mappings(
        self,
        mappings: LayerMappingSet,
        analysis: PSDAnalysisReport | None,
    ) -> list[TemplateValidationIssue]:
        issues: list[TemplateValidationIssue] = []
        if not mappings.mappings:
            issues.append(
                TemplateValidationIssue(
                    severity="error",
                    code="mappings_missing",
                    message="No layer mappings configured for this template.",
                )
            )
            return issues

        layer_names = {layer.name for layer in analysis.layers} if analysis else set()
        smart_ids = {record.smart_object_id for record in analysis.smart_objects} if analysis else set()

        for rule in mappings.mappings:
            if analysis and rule.psd_layer_name and rule.psd_layer_name not in layer_names:
                issues.append(
                    TemplateValidationIssue(
                        severity="error",
                        code="required_layer_missing",
                        message=f"Mapped PSD layer not found: {rule.psd_layer_name}",
                        field_name=rule.design_spec_field,
                        layer_name=rule.psd_layer_name,
                    )
                )
            if analysis and rule.smart_object_id and rule.smart_object_id not in smart_ids:
                issues.append(
                    TemplateValidationIssue(
                        severity="warning",
                        code="missing_smart_object",
                        message=f"Mapped Smart Object not found: {rule.smart_object_id}",
                        field_name=rule.design_spec_field,
                    )
                )
        return issues

    def _validate_anchors(self, anchors: AnchorPointSet) -> list[TemplateValidationIssue]:
        issues: list[TemplateValidationIssue] = []
        anchor_ids = [anchor.anchor_id for anchor in anchors.anchors]
        for anchor_id in anchor_ids:
            if anchor_ids.count(anchor_id) > 1:
                issues.append(
                    TemplateValidationIssue(
                        severity="error",
                        code="duplicate_anchor_id",
                        message=f"Duplicate anchor ID: {anchor_id}",
                    )
                )
        missing = [role for role in REQUIRED_ANCHOR_ROLES if role not in {a.role for a in anchors.anchors}]
        for role in missing:
            issues.append(
                TemplateValidationIssue(
                    severity="warning",
                    code="missing_anchor",
                    message=f"Recommended anchor role missing: {role}",
                )
            )
        return issues

    def _validate_compatibility(self, template: PSDTemplate) -> list[TemplateValidationIssue]:
        issues: list[TemplateValidationIssue] = []
        if not template.build_profile_compatibility:
            issues.append(
                TemplateValidationIssue(
                    severity="warning",
                    code="no_build_profiles",
                    message="Template does not declare build profile compatibility.",
                )
            )
        return issues
