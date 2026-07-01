"""Smart Object Service — index Smart Objects from PSD analysis."""

from __future__ import annotations

from models.psd_template import PSDAnalysisReport, SmartObjectRecord


class SmartObjectService:
    """Query indexed Smart Objects — read-only, no editing."""

    def index(self, analysis: PSDAnalysisReport) -> list[SmartObjectRecord]:
        return list(analysis.smart_objects)

    def find_by_name(self, analysis: PSDAnalysisReport, name: str) -> SmartObjectRecord | None:
        target = name.strip().lower()
        for record in analysis.smart_objects:
            if record.name.strip().lower() == target:
                return record
        return None

    def find_by_id(self, analysis: PSDAnalysisReport, smart_object_id: str) -> SmartObjectRecord | None:
        for record in analysis.smart_objects:
            if record.smart_object_id == smart_object_id:
                return record
        return None

    def in_group(self, analysis: PSDAnalysisReport, parent_group: str) -> list[SmartObjectRecord]:
        return [record for record in analysis.smart_objects if record.parent_group == parent_group]

    def count(self, analysis: PSDAnalysisReport) -> int:
        return len(analysis.smart_objects)
