"""Reference image domain models — immutable project evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

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

    @property
    def dimensions_label(self) -> str:
        return f"{self.width} × {self.height}"

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
