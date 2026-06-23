"""Validation result models consumed by preview and upload."""

from __future__ import annotations

from dataclasses import dataclass, field

from models.discovery import PreflightRow
from models.upload import UploadAction, UploadJob, UploadSummary
from services.asset_resolution_service import AssetResolutionResult


@dataclass(frozen=True)
class ValidatedFile:
    """Single file outcome from pre-flight validation."""

    filename: str
    clean_filename: str
    s3_exists: bool
    old_size: int | None
    new_size: int | None
    action: str  # REPLACE | SKIP
    s3_key: str
    status_message: str


@dataclass
class ValidationResult:
    """Complete validation output for UI and upload queue."""

    rows: list[PreflightRow]
    summary: UploadSummary
    validated_files: list[ValidatedFile]
    upload_jobs: list[UploadJob]
    resolution_results: list[AssetResolutionResult] = field(default_factory=list)
    governance_complete: bool = False


def build_validated_files(rows: list[PreflightRow]) -> list[ValidatedFile]:
    """Map preflight rows to validated_files for preview and upload."""
    result: list[ValidatedFile] = []
    for row in rows:
        d = row.discovered
        if d.excluded or not d.clean_filename:
            continue
        result.append(
            ValidatedFile(
                filename=d.original_filename,
                clean_filename=d.clean_filename,
                s3_exists=row.s3_exists,
                old_size=row.s3_size,
                new_size=d.size_bytes,
                action=row.action,
                s3_key=row.s3_key,
                status_message=row.status_message,
            )
        )
    return result


def build_validation_result(
    rows: list[PreflightRow],
    summary: UploadSummary,
    upload_jobs: list[UploadJob],
) -> ValidationResult:
    return ValidationResult(
        rows=rows,
        summary=summary,
        validated_files=build_validated_files(rows),
        upload_jobs=upload_jobs,
    )
