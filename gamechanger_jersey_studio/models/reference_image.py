"""Reference image domain models — immutable project evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from models.project import ValidationStatus

REFERENCE_MANIFEST_SCHEMA_VERSION = "1.0"
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".psd"}


class ImageCategory(str, Enum):
    FRONT_VIEW = "Front View"
    REAR_VIEW = "Rear View"
    SIDE_VIEW = "Side View"
    DETAIL = "Detail"
    COLLAR = "Collar"
    SLEEVE = "Sleeve"
    PATTERN = "Pattern"
    MANUFACTURER = "Manufacturer"
    BADGE = "Badge"
    SPONSOR = "Sponsor"
    TEXTURE = "Texture"
    OTHER = "Other"


ALL_CATEGORIES = tuple(category.value for category in ImageCategory)
REQUIRED_CATEGORIES = (ImageCategory.FRONT_VIEW.value,)

_LEGACY_IMPORT_DATE_FIELDS = ("imported_at", "import_timestamp", "created_at")
_LEGACY_CATEGORY_FIELDS = ("view_type", "image_category", "reference_type", "category")


class AnalysisStatus(str, Enum):
    NOT_STARTED = "Not started"
    PENDING = "Pending"
    COMPLETE = "Complete"
    FAILED = "Failed"


class ReferenceImageRecord(BaseModel):
    """Metadata for a single immutable reference image."""

    image_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    filename: str
    import_date: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    width: int = 0
    height: int = 0
    file_size: int = 0
    colour_profile: str = ""
    checksum: str = ""
    orientation: int = 0
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    validation_status: ValidationStatus = ValidationStatus.NOT_STARTED
    analysis_status: AnalysisStatus = AnalysisStatus.NOT_STARTED
    sort_order: int = 0
    storage_path: str = ""
    media_type: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_fields(cls, data: Any) -> Any:
        """Map legacy manifest fields onto the current schema when loading .gjs packages."""
        if not isinstance(data, dict):
            return data
        merged = dict(data)
        if not merged.get("import_date"):
            for legacy in _LEGACY_IMPORT_DATE_FIELDS:
                if merged.get(legacy):
                    merged["import_date"] = merged[legacy]
                    break
        if not merged.get("tags"):
            for legacy in _LEGACY_CATEGORY_FIELDS:
                value = merged.get(legacy)
                if not value:
                    continue
                if isinstance(value, str):
                    merged["tags"] = [value]
                elif isinstance(value, list):
                    merged["tags"] = [str(item) for item in value]
                break
        return merged

    @property
    def dimensions_label(self) -> str:
        return f"{self.width} × {self.height}"

    def category_labels(self) -> list[str]:
        """Category tags for this image (canonical representation)."""
        return list(self.tags)

    def primary_category_label(self) -> str:
        """First category tag, if any."""
        labels = self.category_labels()
        return labels[0] if labels else ""

    def import_timestamp(self) -> str:
        """When the image was imported (ISO timestamp)."""
        return self.import_date

    def replay_entry(self) -> dict[str, object]:
        """Serialise for production replay — omits missing optional fields."""
        entry: dict[str, object] = {
            "id": self.image_id,
            "filename": self.filename,
        }
        labels = self.category_labels()
        if labels:
            entry["categories"] = labels
        timestamp = self.import_timestamp()
        if timestamp:
            entry["imported"] = timestamp
        return entry

    def audit_details(self) -> str:
        """Summary line for production audit chain links."""
        labels = self.category_labels()
        if labels:
            return ", ".join(labels)
        return self.filename

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags


class ReferenceImageManifest(BaseModel):
    """Canonical manifest describing every imported reference image."""

    schema_version: str = REFERENCE_MANIFEST_SCHEMA_VERSION
    images: list[ReferenceImageRecord] = Field(default_factory=list)

    def sorted_images(self) -> list[ReferenceImageRecord]:
        return sorted(self.images, key=lambda image: (image.sort_order, image.import_date))

    def get(self, image_id: str) -> ReferenceImageRecord | None:
        for image in self.images:
            if image.image_id == image_id:
                return image
        return None

    def index_of(self, image_id: str) -> int:
        for index, image in enumerate(self.images):
            if image.image_id == image_id:
                return index
        return -1
