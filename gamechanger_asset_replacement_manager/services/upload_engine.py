"""Thread-safe parallel S3 upload engine."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Callable

from models.catalogue import CatalogueDefinition
from models.upload import AuditRecord, UploadAction, UploadJob, UploadProgress, UploadResultStatus
from services.s3_service import S3Service

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[UploadProgress], None]
RecordCallback = Callable[[AuditRecord], None]


class UploadEngine:
    """Thread-safe upload orchestrator with cancellation support."""

    def __init__(self, s3: S3Service, *, max_workers: int = 4) -> None:
        self._s3 = s3
        self._max_workers = max(1, min(16, max_workers))
        self._cancel = threading.Event()
        self._lock = threading.Lock()

    def cancel(self) -> None:
        self._cancel.set()

    def reset(self) -> None:
        self._cancel.clear()

    def run(
        self,
        jobs: list[UploadJob],
        catalogue: CatalogueDefinition,
        *,
        on_progress: ProgressCallback | None = None,
        on_record: RecordCallback | None = None,
    ) -> list[AuditRecord]:
        self.reset()
        to_upload = [j for j in jobs if j.action == UploadAction.REPLACE]
        skipped = [j for j in jobs if j.action == UploadAction.SKIP]
        records: list[AuditRecord] = []

        for job in skipped:
            rec = AuditRecord(
                filename=job.filename,
                clean_filename=job.clean_filename,
                catalogue=catalogue.name,
                s3_exists=job.s3_exists,
                old_size=job.old_size,
                new_size=None,
                uploaded=False,
                status=UploadResultStatus.SKIPPED.value,
                governance_status=job.governance_status,
                resolution_method=job.resolution_method,
                resolved_asset_id=job.resolved_asset_id,
                resolved_file_set_id=job.resolved_file_set_id,
                resolved_iconik_s3_key=job.resolved_iconik_s3_key,
                metadata_status=job.metadata_status,
                governance_warnings=job.governance_warnings,
            )
            records.append(rec)
            if on_record:
                on_record(rec)

        total = len(to_upload)
        if total == 0:
            progress = UploadProgress(
                total=0,
                completed=0,
                remaining=0,
                skipped_count=len(skipped),
            )
            if on_progress:
                on_progress(progress)
            return records

        start = time.monotonic()
        bytes_done = 0
        success = 0
        failed = 0
        completed = 0

        def upload_one(job: UploadJob) -> AuditRecord:
            if self._cancel.is_set():
                return AuditRecord(
                    filename=job.filename,
                    clean_filename=job.clean_filename,
                    catalogue=catalogue.name,
                    s3_exists=job.s3_exists,
                    old_size=job.old_size,
                    new_size=None,
                    uploaded=False,
                    status="cancelled",
                )
            content_type = S3Service.content_type_for_filename(job.clean_filename)
            ok, msg = self._s3.upload_file(
                str(job.local_path),
                catalogue.location,
                job.s3_key,
                content_type=content_type,
            )
            new_size = job.local_path.stat().st_size if ok else None
            return AuditRecord(
                filename=job.filename,
                clean_filename=job.clean_filename,
                catalogue=catalogue.name,
                s3_exists=job.s3_exists,
                old_size=job.old_size,
                new_size=new_size,
                uploaded=ok,
                status=UploadResultStatus.SUCCESS.value if ok else UploadResultStatus.FAILED.value,
                governance_status=job.governance_status,
                resolution_method=job.resolution_method,
                resolved_asset_id=job.resolved_asset_id,
                resolved_file_set_id=job.resolved_file_set_id,
                resolved_iconik_s3_key=job.resolved_iconik_s3_key,
                metadata_status=job.metadata_status,
                governance_warnings=job.governance_warnings,
            )

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures: dict[Future[AuditRecord], UploadJob] = {
                pool.submit(upload_one, job): job for job in to_upload
            }
            for future in as_completed(futures):
                if self._cancel.is_set():
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                job = futures[future]
                try:
                    rec = future.result()
                except Exception as exc:
                    logger.exception("Upload worker failed for %s", job.clean_filename)
                    rec = AuditRecord(
                        filename=job.filename,
                        clean_filename=job.clean_filename,
                        catalogue=catalogue.name,
                        s3_exists=job.s3_exists,
                        old_size=job.old_size,
                        new_size=None,
                        uploaded=False,
                        status=UploadResultStatus.FAILED.value,
                    )
                    rec = replace(rec, status=f"{UploadResultStatus.FAILED.value}: {exc}")

                records.append(rec)
                if on_record:
                    on_record(rec)

                completed += 1
                if rec.uploaded:
                    success += 1
                    bytes_done += job.local_path.stat().st_size
                else:
                    failed += 1

                elapsed = max(time.monotonic() - start, 0.001)
                speed_mbps = (bytes_done * 8) / elapsed / 1_000_000
                progress = UploadProgress(
                    current_file=job.clean_filename,
                    completed=completed,
                    remaining=max(0, total - completed),
                    total=total,
                    bytes_uploaded=bytes_done,
                    success_count=success,
                    failure_count=failed,
                    skipped_count=len(skipped),
                    elapsed_seconds=elapsed,
                    speed_mbps=speed_mbps,
                    cancelled=self._cancel.is_set(),
                )
                if on_progress:
                    on_progress(progress)

        logger.info(
            "Upload finished: %s success, %s failed, %s skipped",
            success,
            failed,
            len(skipped),
        )
        return records
