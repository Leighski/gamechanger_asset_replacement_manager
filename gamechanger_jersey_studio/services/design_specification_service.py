"""Design Specification lifecycle — edits, history, undo/redo, validation."""

from __future__ import annotations

import json
from typing import Any

from models.design_specification import DesignSpecification
from models.project import HistoryEventType, ProjectDocument
from services.design_catalogue_service import DesignCatalogues, load_catalogues
from services.design_spec_completion import CompletionReport, calculate_completion
from services.design_spec_undo import DesignSpecChange, DesignSpecUndoStack
from services.design_spec_validation import ValidationResult, validate_design_specification
from services.logging_manager import get_logger
from services.project_history_service import ProjectHistoryService

logger = get_logger()

PROJECT_INFO_FIELDS = frozenset({"club", "competition", "season", "kit_type", "manufacturer", "output_profile"})


class DesignSpecificationService:
    """Canonical service for all Design Specification mutations."""

    def __init__(
        self,
        history_service: ProjectHistoryService | None = None,
        *,
        catalogues: DesignCatalogues | None = None,
        application_version: str = "",
    ) -> None:
        self._history = history_service or ProjectHistoryService()
        self._catalogues = catalogues or load_catalogues()
        self._application_version = application_version
        self._undo = DesignSpecUndoStack()

    @property
    def catalogues(self) -> DesignCatalogues:
        return self._catalogues

    def set_catalogues(self, catalogues: DesignCatalogues) -> None:
        self._catalogues = catalogues

    def reset_undo(self) -> None:
        self._undo.clear()

    def can_undo(self) -> bool:
        return self._undo.can_undo()

    def can_redo(self) -> bool:
        return self._undo.can_redo()

    def ensure_spec(self, document: ProjectDocument) -> DesignSpecification:
        if document.design_spec is None:
            document.design_spec = DesignSpecification.from_manifest(document.manifest)
            document.mark_dirty()
        return document.design_spec

    def validate(self, spec: DesignSpecification) -> ValidationResult:
        return validate_design_specification(spec, self._catalogues)

    def completion(self, spec: DesignSpecification) -> CompletionReport:
        return calculate_completion(spec)

    def apply_change(
        self,
        document: ProjectDocument,
        property_name: str,
        value: Any,
        *,
        user: str,
        record_undo: bool = True,
        record_history: bool = True,
    ) -> DesignSpecification:
        spec = self.ensure_spec(document)
        old_value = spec.get_field(property_name)
        if _values_equal(old_value, value):
            return spec

        if record_undo:
            self._undo.push(
                DesignSpecChange(
                    property_name=property_name,
                    old_value=_serialize_value(old_value),
                    new_value=_serialize_value(value),
                )
            )

        spec.set_field(property_name, value)
        if property_name in PROJECT_INFO_FIELDS:
            spec.sync_manifest(document.manifest)
            document.manifest.touch_modified()

        validation = self.validate(spec)
        spec.validation_status = validation.status
        document.manifest.validation_status = validation.status
        document.design_spec = spec
        document.mark_dirty()

        if record_history:
            self._record_change(document, property_name, old_value, value, user)

        logger.info(
            "Design Specification changed — {}: {} → {} (user={})",
            property_name,
            _serialize_value(old_value),
            _serialize_value(value),
            user,
        )
        return spec

    def undo(self, document: ProjectDocument, *, user: str) -> DesignSpecification | None:
        change = self._undo.undo()
        if change is None:
            return None
        return self.apply_change(
            document,
            change.property_name,
            _deserialize_value(change.property_name, change.old_value),
            user=user,
            record_undo=False,
            record_history=True,
        )

    def redo(self, document: ProjectDocument, *, user: str) -> DesignSpecification | None:
        change = self._undo.redo()
        if change is None:
            return None
        return self.apply_change(
            document,
            change.property_name,
            _deserialize_value(change.property_name, change.new_value),
            user=user,
            record_undo=False,
            record_history=True,
        )

    def _record_change(
        self,
        document: ProjectDocument,
        property_name: str,
        old_value: Any,
        new_value: Any,
        user: str,
    ) -> None:
        details = json.dumps(
            {
                "property": property_name,
                "old_value": _serialize_value(old_value),
                "new_value": _serialize_value(new_value),
            },
            ensure_ascii=False,
        )
        self._history.record(
            document,
            HistoryEventType.DESIGN_SPEC_CHANGED,
            application_version=self._application_version,
            user=user,
            details=details,
        )


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    return value


def _deserialize_value(property_name: str, value: Any) -> Any:
    if property_name == "kit_type":
        from models.project import KitType

        return KitType(value)
    if property_name == "output_profile":
        from models.design_specification import OutputProfile

        return OutputProfile(value)
    return value


def _values_equal(left: Any, right: Any) -> bool:
    return _serialize_value(left) == _serialize_value(right)
