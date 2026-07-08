"""Pre-flight validation combining discovery and S3 checks."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from models.catalogue import CatalogueDefinition
from models.discovery import DiscoveredFile, DiscoveryResult, FileIssue, PreflightRow, PreflightStatus, S3Status
from models.upload import UploadAction, UploadSummary
from services.s3_service import S3Service

logger = logging.getLogger(__name__)


class PreflightValidator:
    def __init__(self, s3: S3Service, *, max_workers: int = 8) -> None:
        self._s3 = s3
        self._max_workers = max_workers

    def validate(
        self,
        discovery: DiscoveryResult,
        catalogue: CatalogueDefinition,
        *,
        replace_existing_only: bool = True,
    ) -> tuple[list[PreflightRow], UploadSummary]:
        logger.info("Preflight validation for catalogue %s", catalogue.name)
        media_files = [f for f in discovery.files if not f.excluded and f.clean_filename]
        rows: list[PreflightRow] = []

        def check_one(item: DiscoveredFile) -> PreflightRow:
            return self._validate_file(item, catalogue, replace_existing_only=replace_existing_only)

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(check_one, f): f for f in media_files}
            for future in as_completed(futures):
                rows.append(future.result())

        for item in discovery.files:
            if item.excluded:
                rows.append(self._excluded_row(item))

        rows.sort(key=lambda r: r.discovered.clean_filename.lower())
        summary = self._build_summary(rows, discovery)
        logger.info(
            "Preflight complete: %s catalogue S3 exists, %s skip, %s errors",
            summary.s3_replace_candidates,
            summary.files_to_skip,
            summary.validation_errors,
        )
        return rows, summary

    def _validate_file(
        self,
        item: DiscoveredFile,
        catalogue: CatalogueDefinition,
        *,
        replace_existing_only: bool,
    ) -> PreflightRow:
        key = catalogue.location.key_for_filename(item.clean_filename)
        errors: list[str] = []

        if FileIssue.DUPLICATE_NAME in item.issues:
            errors.append("Duplicate clean filename")
        if FileIssue.INVALID_EXTENSION in item.issues:
            errors.append("Invalid extension")
        if not item.clean_filename:
            errors.append("Missing clean filename")

        if errors:
            return PreflightRow(
                discovered=item,
                s3_exists=False,
                s3_size=None,
                size_mismatch=False,
                action=UploadAction.SKIP.value,
                status=PreflightStatus.ERROR,
                status_message="; ".join(errors),
                s3_key=key,
                s3_status=S3Status.ERROR.value,
                catalogue_s3_exists=False,
                catalogue_s3_status=S3Status.ERROR.value,
            )

        info = self._s3.head_object(catalogue.location, key)
        logger.warning(
            "[S3-CHECK] file=%s key=%s exists=%s",
            item.clean_filename,
            key,
            info.exists and not info.error,
        )
        if info.error:
            return PreflightRow(
                discovered=item,
                s3_exists=False,
                s3_size=None,
                size_mismatch=False,
                action=UploadAction.SKIP.value,
                status=PreflightStatus.ERROR,
                status_message=f"S3 error: {info.error}",
                s3_key=key,
                s3_status=S3Status.ERROR.value,
                catalogue_s3_exists=False,
                catalogue_s3_status=S3Status.ERROR.value,
            )

        s3_status = S3Status.EXISTS if info.exists else S3Status.MISSING
        size_mismatch = (
            info.exists
            and info.size is not None
            and info.size != item.size_bytes
        )
        warnings: list[str] = []
        if size_mismatch:
            warnings.append(
                f"Size differs (local {item.size_bytes:,} vs S3 {info.size:,})"
            )
        if item.issues:
            warnings.append("Filename sanitisation applied")

        if info.exists:
            action = UploadAction.REPLACE.value
            status = PreflightStatus.READY
            if warnings:
                status = PreflightStatus.WARNING
            message = "; ".join(warnings) if warnings else "Catalogue S3 object exists"
        elif replace_existing_only:
            action = UploadAction.SKIP.value
            status = PreflightStatus.SKIP
            message = "Not in catalogue S3 — pending governance resolution"
        else:
            action = UploadAction.REPLACE.value
            status = PreflightStatus.WARNING
            message = "Not in catalogue S3 — would upload (safety off)"

        return PreflightRow(
            discovered=item,
            s3_exists=info.exists,
            s3_size=info.size,
            size_mismatch=size_mismatch,
            action=action,
            status=status,
            status_message=message,
            s3_key=key,
            s3_status=s3_status.value,
            catalogue_s3_exists=info.exists,
            catalogue_s3_status=s3_status.value,
        )

    @staticmethod
    def _excluded_row(item: DiscoveredFile) -> PreflightRow:
        return PreflightRow(
            discovered=item,
            s3_exists=False,
            s3_size=None,
            size_mismatch=False,
            action=UploadAction.SKIP.value,
            status=PreflightStatus.SKIP,
            status_message=item.exclude_reason or "Excluded",
            s3_key="",
            s3_status="",
        )

    @staticmethod
    def _build_summary(rows: list[PreflightRow], discovery: DiscoveryResult) -> UploadSummary:
        media = [r for r in rows if not r.discovered.excluded]
        catalogue_exists = sum(
            1
            for r in media
            if r.s3_status == S3Status.EXISTS.value or r.catalogue_s3_exists
        )
        skip = sum(1 for r in media if r.action == UploadAction.SKIP.value)
        errors = sum(1 for r in media if r.status == PreflightStatus.ERROR)
        return UploadSummary(
            files_scanned=discovery.media_count,
            files_to_replace=catalogue_exists,
            files_to_skip=skip,
            validation_errors=errors,
            s3_replace_candidates=catalogue_exists,
        )

    def build_validation_result(
        self,
        rows: list[PreflightRow],
        summary: UploadSummary,
    ):
        """Build full validation payload for GUI and upload queue."""
        from models.validation import build_validation_result

        jobs = self.build_upload_jobs(rows)
        return build_validation_result(rows, summary, jobs)

    def build_upload_jobs(self, rows: list[PreflightRow]) -> list:
        from models.upload import UploadJob

        jobs: list[UploadJob] = []
        for row in rows:
            if row.discovered.excluded:
                continue
            action = UploadAction.REPLACE if row.action == UploadAction.REPLACE.value else UploadAction.SKIP
            jobs.append(
                UploadJob(
                    local_path=row.discovered.path,
                    filename=row.discovered.original_filename,
                    clean_filename=row.discovered.clean_filename,
                    s3_key=row.s3_key,
                    action=action,
                    s3_exists=row.s3_exists,
                    old_size=row.s3_size,
                )
            )
        return jobs
