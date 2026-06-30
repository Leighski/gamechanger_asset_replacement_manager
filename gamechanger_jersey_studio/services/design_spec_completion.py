"""Design Specification completeness scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models.design_specification import DesignSpecification


@dataclass(frozen=True)
class SectionCompletion:
    section: str
    label: str
    percent: int
    filled: int
    total: int


@dataclass(frozen=True)
class CompletionReport:
    sections: tuple[SectionCompletion, ...]
    overall_percent: int

    def as_dict(self) -> dict[str, int]:
        return {section.section: section.percent for section in self.sections}


SECTION_LABELS = {
    "project_information": "Project Information",
    "colours": "Colours",
    "construction": "Construction",
    "pattern": "Pattern",
    "effects": "Effects",
    "output": "Output",
}


def _is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float)):
        return True
    if hasattr(value, "value"):
        return bool(str(value.value).strip())
    return bool(value)


def _section_percent(spec: DesignSpecification, section: str, fields: tuple[str, ...]) -> SectionCompletion:
    filled = sum(1 for name in fields if _is_filled(spec.get_field(name)))
    total = len(fields)
    percent = round((filled / total) * 100) if total else 0
    return SectionCompletion(
        section=section,
        label=SECTION_LABELS.get(section, section.replace("_", " ").title()),
        percent=percent,
        filled=filled,
        total=total,
    )


def calculate_completion(spec: DesignSpecification) -> CompletionReport:
    sections = spec.section_fields
    scored = (
        _section_percent(spec, "project_information", sections["project_information"]),
        _section_percent(spec, "colours", sections["colours"]),
        _section_percent(spec, "construction", sections["construction"]),
        _section_percent(spec, "pattern", sections["pattern"]),
        _section_percent(spec, "effects", sections["effects"]),
        _section_percent(spec, "output", sections["output"]),
    )
    total_filled = sum(section.filled for section in scored)
    total_fields = sum(section.total for section in scored)
    overall = round((total_filled / total_fields) * 100) if total_fields else 0
    return CompletionReport(sections=scored, overall_percent=overall)
