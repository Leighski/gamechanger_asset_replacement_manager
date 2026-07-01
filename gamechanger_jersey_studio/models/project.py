"""Gamechanger Jersey Studio project domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from models.design_specification import DesignSpecification
    from models.interpretation import InterpretationArchive
    from models.learning import LearningProjectRecord
    from models.reference_image import ReferenceImageManifest
    from models.vision_analysis import VisionAnalysisArchive


class KitType(str, Enum):
    HOME = "Home"
    AWAY = "Away"
    THIRD = "Third"
    GOALKEEPER = "Goalkeeper"
    WOMENS = "Women's"


class ProjectStatus(str, Enum):
    DRAFT = "Draft"
    ACTIVE = "Active"
    ARCHIVED = "Archived"


class ValidationStatus(str, Enum):
    NOT_STARTED = "Not started"
    PENDING = "Pending"
    PASSED = "Passed"
    FAILED = "Failed"


class HistoryEventType(str, Enum):
    PROJECT_CREATED = "Project Created"
    OPENED = "Opened"
    SAVED = "Saved"
    CLOSED = "Closed"
    RECOVERY_RESTORED = "Recovery Restored"
    DUPLICATED = "Duplicated"
    ARCHIVED = "Archived"
    DELETED = "Deleted"
    DESIGN_SPEC_CHANGED = "Design Specification Changed"
    REFERENCE_IMAGE_IMPORTED = "Reference Image Imported"
    REFERENCE_IMAGE_DELETED = "Reference Image Deleted"
    REFERENCE_IMAGE_REPLACED = "Reference Image Replaced"
    REFERENCE_IMAGE_RETAGGED = "Reference Image Retagged"
    REFERENCE_IMAGE_RENAMED = "Reference Image Renamed"
    REFERENCE_IMAGE_VIEWED = "Reference Image Viewed"
    VISION_ANALYSIS_STARTED = "Vision Analysis Started"
    VISION_ANALYSIS_COMPLETED = "Vision Analysis Completed"
    VISION_ANALYSIS_FAILED = "Vision Analysis Failed"
    VISION_ANALYSIS_ACCEPTED = "Vision Analysis Accepted"
    VISION_ANALYSIS_REJECTED = "Vision Analysis Rejected"
    AI_SUGGESTIONS_GENERATED = "AI Suggestions Generated"
    AI_SUGGESTIONS_FAILED = "AI Suggestions Failed"
    SUGGESTION_ACCEPTED = "Suggestion Accepted"
    SUGGESTION_REJECTED = "Suggestion Rejected"
    SUGGESTION_MODIFIED = "Suggestion Modified"
    RENDER_STARTED = "Render Started"
    RENDER_COMPLETED = "Render Completed"
    RENDER_FAILED = "Render Failed"
    PSD_SAVED = "PSD Saved"
    PNG_GENERATED = "PNG Generated"
    PRODUCTION_QUEUE_ADDED = "Production Queue Added"
    BULK_REVIEW_COMPLETED = "Bulk Review Completed"
    BATCH_RENDER_STARTED = "Batch Render Started"
    BATCH_RENDER_PAUSED = "Batch Render Paused"
    BATCH_RENDER_RESUMED = "Batch Render Resumed"
    BATCH_RENDER_CANCELLED = "Batch Render Cancelled"
    BATCH_RENDER_COMPLETED = "Batch Render Completed"
    PRODUCTION_AUDIT_RECORDED = "Production Audit Recorded"
    LEARNING_EVENT_RECORDED = "Learning Event Recorded"
    LEARNING_RULE_CREATED = "Learning Rule Created"
    LEARNING_RULE_APPLIED = "Learning Rule Applied"
    LEARNING_RECOMMENDATION_ACCEPTED = "Learning Recommendation Accepted"
    LEARNING_RECOMMENDATION_IGNORED = "Learning Recommendation Ignored"


DEFAULT_BUILD_PROFILE = "Gamechanger Broadcast"
GJS_FORMAT_VERSION = "1.0"
GJS_EXTENSION = ".gjs"


class ProjectManifest(BaseModel):
    """Canonical project metadata stored inside every .gjs package."""

    format_version: str = GJS_FORMAT_VERSION
    project_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    project_name: str
    club_name: str
    competition: str
    season: str
    kit_type: KitType
    build_profile: str = DEFAULT_BUILD_PROFILE
    output_folder: str
    project_notes: str = ""
    author: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    modified_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    application_version: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    reference_image_count: int = 0
    generated_output_count: int = 0
    validation_status: ValidationStatus = ValidationStatus.NOT_STARTED

    @field_validator("project_name", "club_name", "competition", "season", "author")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    def touch_modified(self) -> None:
        self.modified_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def summary(self) -> dict[str, str]:
        return {
            "project_name": self.project_name,
            "club_name": self.club_name,
            "competition": self.competition,
            "season": self.season,
            "build_profile": self.build_profile,
            "status": self.status.value,
            "validation_status": self.validation_status.value,
        }


class ProjectHistoryEntry(BaseModel):
    timestamp: str
    event: HistoryEventType
    application_version: str
    user: str
    details: str = ""

    @classmethod
    def create(
        cls,
        event: HistoryEventType,
        *,
        application_version: str,
        user: str,
        details: str = "",
    ) -> ProjectHistoryEntry:
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            event=event,
            application_version=application_version,
            user=user,
            details=details,
        )


class ProjectHistory(BaseModel):
    entries: list[ProjectHistoryEntry] = Field(default_factory=list)

    def append(self, entry: ProjectHistoryEntry) -> None:
        self.entries.append(entry)

    def recent(self, limit: int = 10) -> list[ProjectHistoryEntry]:
        return list(reversed(self.entries[-limit:]))


class NewProjectRequest(BaseModel):
    project_name: str
    club_name: str
    competition: str
    season: str
    kit_type: KitType
    build_profile: str = DEFAULT_BUILD_PROFILE
    output_folder: str
    project_notes: str = ""
    author: str = ""


class ProjectDocument(BaseModel):
    """In-memory representation of an open .gjs project."""

    manifest: ProjectManifest
    history: ProjectHistory = Field(default_factory=ProjectHistory)
    design_spec: "DesignSpecification | None" = None
    reference_manifest: "ReferenceImageManifest | None" = None
    vision_analyses: "VisionAnalysisArchive | None" = None
    interpretation_results: "InterpretationArchive | None" = None
    learning_record: "LearningProjectRecord | None" = None
    renderer_settings: "RendererSettings | None" = None
    template_settings: "TemplateProjectSettings | None" = None
    file_path: str = ""
    dirty: bool = False

    @property
    def display_name(self) -> str:
        return self.manifest.project_name

    def mark_saved(self) -> None:
        self.dirty = False
        self.manifest.touch_modified()

    def mark_dirty(self) -> None:
        self.dirty = True

    def to_package_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "manifest": self.manifest.model_dump(mode="json"),
            "history": self.history.model_dump(mode="json"),
        }
        if self.design_spec is not None:
            payload["design_spec"] = self.design_spec.model_dump(mode="json")
        if self.reference_manifest is not None:
            payload["reference_manifest"] = self.reference_manifest.model_dump(mode="json")
        if self.vision_analyses is not None:
            payload["vision_analyses"] = self.vision_analyses.model_dump(mode="json")
        if self.interpretation_results is not None:
            payload["interpretation_results"] = self.interpretation_results.model_dump(mode="json")
        if self.renderer_settings is not None:
            payload["renderer_settings"] = self.renderer_settings.model_dump(mode="json")
        if self.template_settings is not None:
            payload["template_settings"] = self.template_settings.model_dump(mode="json")
        return payload
