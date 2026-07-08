"""Validation rules for reference image collections."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from models.project import ValidationStatus
from models.reference_image import REQUIRED_CATEGORIES, ReferenceImageManifest, ReferenceImageRecord
from services.reference_image_io import LARGE_FILE_BYTES, SMALL_IMAGE_PX


class ReferenceIssueSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ReferenceValidationIssue:
    image_id: str
    field: str
    message: str
    severity: ReferenceIssueSeverity = ReferenceIssueSeverity.WARNING


@dataclass
class ReferenceValidationResult:
    issues: list[ReferenceValidationIssue] = field(default_factory=list)
    status: ValidationStatus = ValidationStatus.NOT_STARTED

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == ReferenceIssueSeverity.ERROR for issue in self.issues)

    def issues_for_image(self, image_id: str) -> list[ReferenceValidationIssue]:
        return [issue for issue in self.issues if issue.image_id == image_id]


def validate_reference_manifest(manifest: ReferenceImageManifest) -> ReferenceValidationResult:
    issues: list[ReferenceValidationIssue] = []
    checksums: dict[str, str] = {}

    if not manifest.images:
        issues.append(
            ReferenceValidationIssue(
                image_id="",
                field="collection",
                message="No reference images have been imported.",
                severity=ReferenceIssueSeverity.WARNING,
            )
        )

    present_tags: set[str] = set()
    for image in manifest.sorted_images():
        present_tags.update(image.tags)
        issues.extend(_validate_image(image, checksums))

    for required in REQUIRED_CATEGORIES:
        if required not in present_tags:
            issues.append(
                ReferenceValidationIssue(
                    image_id="",
                    field="category",
                    message=f"Missing required category: {required}.",
                    severity=ReferenceIssueSeverity.WARNING,
                )
            )

    if issues:
        has_error = any(issue.severity == ReferenceIssueSeverity.ERROR for issue in issues)
        status = ValidationStatus.FAILED if has_error else ValidationStatus.PENDING
    elif manifest.images:
        status = ValidationStatus.PASSED
    else:
        status = ValidationStatus.NOT_STARTED

    return ReferenceValidationResult(issues=issues, status=status)


def _validate_image(
    image: ReferenceImageRecord,
    checksums: dict[str, str],
) -> list[ReferenceValidationIssue]:
    issues: list[ReferenceValidationIssue] = []

    if image.checksum:
        if image.checksum in checksums.values():
            issues.append(
                ReferenceValidationIssue(
                    image_id=image.image_id,
                    field="checksum",
                    message="Duplicate checksum detected.",
                )
            )
        checksums[image.image_id] = image.checksum

    if image.width < SMALL_IMAGE_PX or image.height < SMALL_IMAGE_PX:
        issues.append(
            ReferenceValidationIssue(
                image_id=image.image_id,
                field="dimensions",
                message=f"Very small image ({image.dimensions_label}).",
            )
        )

    if image.file_size > LARGE_FILE_BYTES:
        issues.append(
            ReferenceValidationIssue(
                image_id=image.image_id,
                field="file_size",
                message="Large file size — consider optimising before import.",
            )
        )

    if image.colour_profile and image.colour_profile not in {"", "sRGB", "ICC"}:
        issues.append(
            ReferenceValidationIssue(
                image_id=image.image_id,
                field="colour_profile",
                message=f"Unsupported colour profile: {image.colour_profile}.",
            )
        )

    if not image.tags:
        issues.append(
            ReferenceValidationIssue(
                image_id=image.image_id,
                field="tags",
                message="Missing category tag.",
            )
        )

    return issues


def missing_categories(manifest: ReferenceImageManifest) -> list[str]:
    present = {tag for image in manifest.images for tag in image.tags}
    return [category for category in REQUIRED_CATEGORIES if category not in present]
