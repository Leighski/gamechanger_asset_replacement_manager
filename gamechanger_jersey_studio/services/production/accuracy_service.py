"""Accuracy scoring — compare expected vs generated design specifications."""

from __future__ import annotations

from models.design_specification import DesignSpecification
from models.validation import AccuracyCategory, AccuracyReport, CategoryScore

_CATEGORY_FIELDS: dict[AccuracyCategory, tuple[str, ...]] = {
    AccuracyCategory.COLOUR: (
        "primary_colour",
        "secondary_colour",
        "third_colour",
        "sleeve_colour",
        "collar_colour",
        "trim_colour",
    ),
    AccuracyCategory.PATTERN: (
        "pattern",
        "pattern_scale",
        "pattern_rotation",
        "pattern_opacity",
    ),
    AccuracyCategory.COLLAR: ("collar_style", "collar_colour"),
    AccuracyCategory.TRIM: ("trim_style", "trim_colour"),
    AccuracyCategory.SLEEVE: ("sleeve_style", "sleeve_colour"),
    AccuracyCategory.TEMPLATE: ("output_profile",),
}

_FLOAT_FIELDS = {"pattern_scale", "pattern_rotation", "pattern_opacity"}


def _field_value(spec: DesignSpecification, field_name: str) -> str:
    value = getattr(spec, field_name, "")
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _fields_match(expected: str, generated: str, field_name: str) -> bool:
    if field_name in _FLOAT_FIELDS:
        try:
            return abs(float(expected or 0) - float(generated or 0)) < 0.01
        except ValueError:
            return expected.strip().lower() == generated.strip().lower()
    return expected.strip().lower() == generated.strip().lower()


class AccuracyService:
    """Calculate per-category accuracy scores with confidence."""

    def score_category(
        self,
        expected: DesignSpecification,
        generated: DesignSpecification,
        category: AccuracyCategory,
        *,
        base_confidence: float = 85.0,
    ) -> CategoryScore:
        fields = _CATEGORY_FIELDS[category]
        matched = 0
        details: list[str] = []
        for field_name in fields:
            exp_val = _field_value(expected, field_name)
            gen_val = _field_value(generated, field_name)
            if _fields_match(exp_val, gen_val, field_name):
                matched += 1
            else:
                details.append(f"{field_name}: expected '{exp_val}' vs generated '{gen_val}'")
        total = len(fields)
        score = round(matched / total * 100.0, 2) if total else 0.0
        confidence = round(base_confidence * (matched / total) if total else base_confidence, 2)
        return CategoryScore(
            category=category,
            score=score,
            confidence=confidence,
            matched_fields=matched,
            total_fields=total,
            details=details,
        )

    def score(
        self,
        expected: DesignSpecification,
        generated: DesignSpecification,
        *,
        project_name: str = "",
        base_confidence: float = 85.0,
        missing_components: list[str] | None = None,
    ) -> AccuracyReport:
        categories = [
            self.score_category(expected, generated, cat, base_confidence=base_confidence)
            for cat in (
                AccuracyCategory.COLOUR,
                AccuracyCategory.PATTERN,
                AccuracyCategory.COLLAR,
                AccuracyCategory.TRIM,
                AccuracyCategory.SLEEVE,
                AccuracyCategory.TEMPLATE,
            )
        ]
        overall_score = (
            round(sum(c.score for c in categories) / len(categories), 2) if categories else 0.0
        )
        overall_confidence = (
            round(sum(c.confidence for c in categories) / len(categories), 2)
            if categories
            else base_confidence
        )
        overall = CategoryScore(
            category=AccuracyCategory.OVERALL,
            score=overall_score,
            confidence=overall_confidence,
            matched_fields=sum(c.matched_fields for c in categories),
            total_fields=sum(c.total_fields for c in categories),
        )
        return AccuracyReport(
            project_name=project_name,
            overall=overall,
            categories=categories,
            missing_catalogue_components=missing_components or [],
        )

    def detect_missing_components(self, spec: DesignSpecification) -> list[str]:
        missing: list[str] = []
        checks = (
            ("collar_style", "Collar component"),
            ("sleeve_style", "Sleeve component"),
            ("pattern", "Pattern component"),
            ("trim_style", "Trim component"),
            ("material_style", "Material component"),
        )
        for field_name, label in checks:
            if not _field_value(spec, field_name):
                missing.append(label)
        return missing
