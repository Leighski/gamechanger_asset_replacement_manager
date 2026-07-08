"""Iconik library housekeeping audits — read-only, no asset modifications."""

from __future__ import annotations

import logging
import threading
import traceback
from collections import defaultdict
from typing import Callable

from models.housekeeping import (
    AssetPageProgress,
    DuplicateGroup,
    HousekeepingAssetRecord,
    HousekeepingAuditResult,
    HousekeepingProgress,
    OrphanAssetRecord,
)
from services.iconik_verification import IconikVerificationService, METADATA_STATUS_MISSING

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = frozenset({"ACTIVE", "ONLINE", "READY"})


def _log_phase_error(phase: str) -> None:
    logger.error(
        "[HOUSEKEEPING-ERROR] phase=%s exception=%s",
        phase,
        traceback.format_exc(),
    )


class HousekeepingService:
    """Audit-only Iconik library diagnostics."""

    def __init__(self, iconik: IconikVerificationService) -> None:
        self._iconik = iconik
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def reset_cancel(self) -> None:
        self._cancel.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def run_audit(
        self,
        *,
        on_progress: Callable[[HousekeepingProgress], None] | None = None,
    ) -> HousekeepingAuditResult:
        """Scan entire Iconik library and classify duplicate/orphan findings."""
        self.reset_cancel()
        result = HousekeepingAuditResult()

        if not self._iconik.configured():
            result.error = "Iconik credentials not configured"
            return result

        def progress(
            phase: str,
            current: int,
            total: int,
            message: str = "",
            *,
            pages_scanned: int = 0,
            duplicates_filtered: int = 0,
            assets_reported: int = 0,
        ) -> None:
            if on_progress:
                on_progress(
                    HousekeepingProgress(
                        phase,
                        current,
                        total,
                        message,
                        pages_scanned=pages_scanned,
                        duplicates_filtered=duplicates_filtered,
                        assets_reported=assets_reported,
                    )
                )

        try:
            logger.warning("[HOUSEKEEPING] START_SCAN")
            try:
                progress("search", 0, 1, "Searching Iconik library…")

                def on_search_page(page_progress: AssetPageProgress) -> None:
                    total = max(
                        page_progress.assets_reported_by_iconik,
                        page_progress.running_total,
                        1,
                    )
                    progress(
                        "search",
                        page_progress.running_total,
                        total,
                        (
                            f"Pages scanned: {page_progress.pages_received} | "
                            f"Assets scanned: {page_progress.running_total} | "
                            f"Duplicates found: {page_progress.duplicates_filtered}"
                        ),
                        pages_scanned=page_progress.pages_received,
                        duplicates_filtered=page_progress.duplicates_filtered,
                        assets_reported=page_progress.assets_reported_by_iconik,
                    )

                scan = self._iconik.iterate_all_assets(
                    query="",
                    cancel_check=self._cancel.is_set,
                    on_page=on_search_page,
                )
                result.scan_summary = scan.summary
                result.warnings = list(scan.summary.warnings)
            except Exception as exc:
                _log_phase_error("scan")
                result.error = str(exc)
                return result

            if scan.summary.cancelled or self._cancel.is_set():
                result.cancelled = True
                result.all_records = []
                return result

            raw_assets = scan.assets
            if self._cancel.is_set():
                result.cancelled = True
                return result

            logger.warning("[HOUSEKEEPING] START_ENRICH")
            try:
                total = len(raw_assets)
                records: list[HousekeepingAssetRecord] = []
                for index, raw in enumerate(raw_assets, start=1):
                    if self._cancel.is_set():
                        result.cancelled = True
                        result.all_records = records
                        return result
                    asset_id = str(raw.get("id") or raw.get("asset_id") or "")
                    if not asset_id:
                        continue
                    progress(
                        "enrich",
                        index,
                        total,
                        f"Enriching {asset_id} ({index}/{total})",
                    )
                    records.append(self._build_record(asset_id, raw))

                result.all_records = records
                result.total_scanned = len(records)
            except Exception as exc:
                _log_phase_error("enrich")
                result.error = str(exc)
                result.all_records = records if "records" in locals() else []
                return result

            if self._cancel.is_set():
                result.cancelled = True
                return result

            logger.warning("[HOUSEKEEPING] START_ANALYZE")
            try:
                progress("analyze", 0, 1, "Analysing duplicates and orphans…")
                result.duplicate_filename_groups = _find_duplicate_groups(
                    records,
                    key_fn=lambda r: r.file_set_name.strip(),
                    skip_empty=True,
                )
                result.duplicate_storage_groups = _find_duplicate_groups(
                    records,
                    key_fn=lambda r: r.storage_key.strip(),
                    skip_empty=True,
                )
                result.duplicate_title_groups = _find_duplicate_groups(
                    records,
                    key_fn=lambda r: r.title.strip(),
                    skip_empty=False,
                )
                result.orphan_assets = _find_orphans(records)
                progress("analyze", 1, 1, "Audit complete")
            except Exception as exc:
                _log_phase_error("analyze")
                result.error = str(exc)
                return result

            logger.warning(
                "[HOUSEKEEPING] assets_scanned=%s filename_duplicates=%s "
                "storage_duplicates=%s title_duplicates=%s orphan_assets=%s",
                result.total_scanned,
                len(result.duplicate_filename_groups),
                len(result.duplicate_storage_groups),
                len(result.duplicate_title_groups),
                len(result.orphan_assets),
            )
            return result
        except Exception as exc:
            _log_phase_error("audit")
            result.error = str(exc)
            return result

    def _build_record(self, asset_id: str, raw: dict) -> HousekeepingAssetRecord:
        title = str(raw.get("title") or raw.get("name") or "")
        status = str(raw.get("status") or raw.get("state") or "")
        date_created = str(raw.get("date_created") or raw.get("created") or "")
        date_modified = str(raw.get("date_modified") or raw.get("modified") or "")

        file_set_id = ""
        file_set_name = ""
        storage_id = ""
        storage_key = ""
        metadata_status = ""

        try:
            details = self._iconik.resolve_file_details(asset_id)
            file_set_id = str(details.get("file_set_id") or "")
            file_set_name = str(details.get("original_filename") or details.get("iconik_file_name") or "")
            storage_id = str(details.get("storage_id") or "")
            storage_key = str(details.get("iconik_s3_key") or details.get("storage_path") or "")
        except Exception as exc:
            logger.debug("File details unavailable for %s: %s", asset_id, exc)

        try:
            metadata = self._iconik.fetch_metadata(asset_id)
            metadata_status = metadata.status
        except Exception as exc:
            logger.debug("Metadata lookup unavailable for %s: %s", asset_id, exc)
            metadata_status = "ERROR"

        if not title:
            try:
                asset = self._iconik.get_asset(asset_id)
                title = str(asset.get("title") or asset.get("name") or "")
                if not status:
                    status = str(asset.get("status") or asset.get("state") or "")
                if not date_created:
                    date_created = str(asset.get("date_created") or "")
                if not date_modified:
                    date_modified = str(asset.get("date_modified") or "")
            except Exception:
                pass

        return HousekeepingAssetRecord(
            asset_id=asset_id,
            title=title,
            status=status,
            file_set_id=file_set_id,
            file_set_name=file_set_name,
            storage_id=storage_id,
            storage_key=storage_key,
            date_created=date_created,
            date_modified=date_modified,
            metadata_status=metadata_status,
        )


def _find_duplicate_groups(
    records: list[HousekeepingAssetRecord],
    *,
    key_fn: Callable[[HousekeepingAssetRecord], str],
    skip_empty: bool,
) -> list[DuplicateGroup]:
    buckets: dict[str, list[HousekeepingAssetRecord]] = defaultdict(list)
    for record in records:
        key = key_fn(record)
        if skip_empty and not key:
            continue
        buckets[key].append(record)

    groups: list[DuplicateGroup] = []
    for key, items in buckets.items():
        if len(items) <= 1:
            continue
        groups.append(
            DuplicateGroup(
                group_key=key,
                count=len(items),
                asset_ids=[r.asset_id for r in items],
                titles=[r.title for r in items],
            )
        )
    groups.sort(key=lambda g: (-g.count, g.group_key.lower()))
    return groups


def _find_orphans(records: list[HousekeepingAssetRecord]) -> list[OrphanAssetRecord]:
    orphans: list[OrphanAssetRecord] = []
    for record in records:
        reasons: list[str] = []
        if not record.file_set_id.strip():
            reasons.append("no_file_set")
        if not record.storage_key.strip():
            reasons.append("no_storage_key")
        status_upper = record.status.strip().upper()
        if status_upper and status_upper not in ACTIVE_STATUSES:
            reasons.append(f"inactive_status:{record.status}")
        if record.metadata_status == METADATA_STATUS_MISSING:
            reasons.append("missing_metadata_view")
        if not reasons:
            continue
        orphans.append(
            OrphanAssetRecord(
                asset_id=record.asset_id,
                title=record.title,
                status=record.status,
                file_set_id=record.file_set_id,
                file_set_name=record.file_set_name,
                storage_id=record.storage_id,
                storage_key=record.storage_key,
                date_created=record.date_created,
                date_modified=record.date_modified,
                metadata_status=record.metadata_status,
                orphan_reasons=reasons,
            )
        )
    orphans.sort(key=lambda o: o.asset_id)
    return orphans
