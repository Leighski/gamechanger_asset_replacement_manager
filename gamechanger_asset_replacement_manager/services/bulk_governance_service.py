"""Iconik governance pass for Source Files bulk upload candidates."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from models.catalogue import CatalogueDefinition
from models.discovery import DiscoveryResult, PreflightRow, PreflightStatus, S3Status
from models.upload import UploadAction, UploadJob, UploadSummary
from services.asset_resolution_service import (
    AssetResolutionResult,
    AssetResolutionService,
    GovernanceStatus,
)
from services.dual_replacement_service import ReplacementTarget
from services.iconik_verification import IconikVerificationService
from services.paths import REPORTS_DIR
from services.replacement_variant import ReplacementAssetType, detect_replacement_type
from services.s3_service import S3Service

logger = logging.getLogger(__name__)

GOVERNANCE_VERIFICATION_REPORT = REPORTS_DIR / "governance_phase2_verification.json"


def _governance_media_rows(rows: list[PreflightRow]) -> list[PreflightRow]:
    """All discovered media files eligible for Iconik governance."""
    return [
        row
        for row in rows
        if not row.discovered.excluded and row.discovered.clean_filename
    ]


def resolve_governance_for_preflight(
    rows: list[PreflightRow],
    *,
    catalogue: CatalogueDefinition,
    iconik: IconikVerificationService,
) -> list[AssetResolutionResult]:
    """Run AssetResolutionService for every discovered media file with a clean filename."""
    media_rows = _governance_media_rows(rows)

    if not media_rows:
        return []

    if not iconik.configured():
        logger.warning("Iconik not configured — bulk governance cannot resolve assets")
        return [
            _iconik_unconfigured_result(row.discovered.clean_filename)
            for row in media_rows
        ]

    targets: list[ReplacementTarget] = []
    synthetic: list[AssetResolutionResult] = []

    for row in media_rows:
        clean_name = row.discovered.clean_filename
        asset_type = detect_replacement_type(clean_name)
        if asset_type is None:
            synthetic.append(_type_mismatch_result(clean_name))
            continue
        targets.append(
            ReplacementTarget(
                local_path=row.discovered.path,
                asset_type=asset_type,
                iconik_filename=clean_name,
                s3_key=row.s3_key,
            )
        )

    resolved = AssetResolutionService(iconik).resolve_batch(targets, catalogue=catalogue)
    return synthetic + resolved


def apply_governance_results(
    rows: list[PreflightRow],
    resolutions: list[AssetResolutionResult],
) -> None:
    """Merge governance outcomes into preflight rows keyed by clean filename."""
    by_filename = {r.local_filename: r for r in resolutions}

    for row in _governance_media_rows(rows):
        clean_name = row.discovered.clean_filename
        result = by_filename.get(clean_name)
        if result is None:
            row.governance_status = GovernanceStatus.NOT_FOUND.value
            row.governance_message = "No governance result returned"
            logger.warning(
                "[GOVERNANCE] file=%s status=%s asset=%s file_set=%s resolved_key=%s",
                clean_name,
                row.governance_status,
                "",
                "",
                "",
            )
            continue

        row.governance_status = result.status.value
        row.resolution_method = result.resolution_method
        row.governance_message = result.message
        row.governance_warnings = (
            ", ".join(result.governance_warnings) if result.governance_warnings else ""
        )

        if result.status == GovernanceStatus.VERIFIED and result.target:
            target = result.target
            row.resolved_asset_id = target.asset_id
            row.resolved_file_set_id = target.file_set_id
            row.resolved_iconik_s3_key = target.iconik_s3_key
            row.metadata_status = target.metadata_status
        else:
            row.resolved_asset_id = result.resolved_asset_id
            row.resolved_file_set_id = result.resolved_file_set_id
            row.resolved_iconik_s3_key = result.resolved_iconik_s3_key
            row.metadata_status = ""

        logger.warning(
            "[GOVERNANCE] file=%s status=%s asset=%s file_set=%s resolved_key=%s",
            clean_name,
            row.governance_status,
            row.resolved_asset_id,
            row.resolved_file_set_id,
            row.resolved_iconik_s3_key,
        )


def preserve_catalogue_s3_preflight(rows: list[PreflightRow]) -> None:
    """Snapshot catalogue-key S3 preflight before resolved-key validation."""
    for row in _governance_media_rows(rows):
        row.catalogue_s3_exists = row.s3_exists
        row.catalogue_s3_status = row.s3_status or _s3_status_from_preflight(row).value


def validate_s3_against_resolved_keys(
    rows: list[PreflightRow],
    s3: S3Service,
    catalogue: CatalogueDefinition,
) -> None:
    """HEAD S3 at each resolved Iconik key — independent of governance status."""
    for row in _governance_media_rows(rows):
        clean_name = row.discovered.clean_filename
        resolved_key = row.resolved_iconik_s3_key.strip()
        if not resolved_key:
            row.s3_exists = False
            row.s3_status = S3Status.MISSING.value
            logger.warning(
                "[S3-CHECK] file=%s key=%s exists=%s",
                clean_name,
                "",
                False,
            )
            continue

        info = s3.head_object(catalogue.location, resolved_key)
        if info.error:
            row.s3_exists = False
            row.s3_status = S3Status.ERROR.value
        elif info.exists:
            row.s3_exists = True
            row.s3_status = S3Status.EXISTS.value
            if info.size is not None:
                row.s3_size = info.size
        else:
            row.s3_exists = False
            row.s3_status = S3Status.MISSING.value

        logger.warning(
            "[S3-CHECK] file=%s key=%s exists=%s",
            clean_name,
            resolved_key,
            row.s3_exists,
        )


def recompute_row_readiness(row: PreflightRow) -> None:
    """READY_TO_REPLACE = VERIFIED governance + resolved Iconik S3 key (informational S3)."""
    if row.discovered.excluded or row.status == PreflightStatus.ERROR:
        return

    ready = is_ready_to_replace(row)
    if ready:
        row.action = UploadAction.REPLACE.value
        row.status = PreflightStatus.READY
        s3_note = ""
        if row.s3_status == S3Status.MISSING.value:
            s3_note = " (resolved S3 key missing — informational)"
        elif row.s3_status == S3Status.ERROR.value:
            s3_note = " (resolved S3 check error — informational)"
        row.status_message = f"Governance VERIFIED — ready to replace{s3_note}"
        return

    row.action = UploadAction.SKIP.value
    if row.governance_status == GovernanceStatus.VERIFIED.value:
        row.status = PreflightStatus.WARNING
        row.status_message = "Governance VERIFIED but no resolved Iconik S3 key"
    elif row.governance_status:
        row.status = PreflightStatus.SKIP
        row.status_message = (
            row.governance_message
            or f"Governance {row.governance_status} — skipped"
        )
    elif row.catalogue_s3_status == S3Status.MISSING.value:
        row.status = PreflightStatus.SKIP
        row.status_message = "Awaiting governance resolution"


def recompute_all_row_readiness(rows: list[PreflightRow]) -> None:
    for row in rows:
        recompute_row_readiness(row)


def is_ready_to_replace(row: PreflightRow) -> bool:
    return (
        row.governance_status == GovernanceStatus.VERIFIED.value
        and bool(row.resolved_iconik_s3_key.strip())
    )


_GOVERNANCE_ERROR_STATUSES = frozenset(
    {
        GovernanceStatus.ERROR.value,
        GovernanceStatus.TYPE_MISMATCH.value,
        GovernanceStatus.PATH_MISMATCH.value,
        GovernanceStatus.FILESET_MISMATCH.value,
    }
)


@dataclass(frozen=True)
class GovernanceStats:
    verified: int = 0
    not_found: int = 0
    duplicate: int = 0
    errors: int = 0
    s3_missing: int = 0
    ready_to_replace: int = 0


def compute_governance_stats(rows: list[PreflightRow]) -> GovernanceStats:
    """Aggregate governance and resolved-S3 counts for preview summary cards."""
    verified = not_found = duplicate = errors = s3_missing = ready_to_replace = 0
    for row in _governance_media_rows(rows):
        status = row.governance_status
        if status == GovernanceStatus.VERIFIED.value:
            verified += 1
        elif status == GovernanceStatus.NOT_FOUND.value:
            not_found += 1
        elif status == GovernanceStatus.DUPLICATE.value:
            duplicate += 1
        elif status in _GOVERNANCE_ERROR_STATUSES:
            errors += 1
        if (
            status == GovernanceStatus.VERIFIED.value
            and row.resolved_iconik_s3_key.strip()
            and row.s3_status == S3Status.MISSING.value
        ):
            s3_missing += 1
        if is_ready_to_replace(row):
            ready_to_replace += 1
    return GovernanceStats(
        verified=verified,
        not_found=not_found,
        duplicate=duplicate,
        errors=errors,
        s3_missing=s3_missing,
        ready_to_replace=ready_to_replace,
    )


def build_governed_summary(
    rows: list[PreflightRow],
    discovery: DiscoveryResult,
) -> UploadSummary:
    """Recompute upload summary — ready = VERIFIED governance + resolved Iconik S3 key."""
    media = [r for r in rows if not r.discovered.excluded]
    governed_ready = sum(1 for r in media if is_ready_to_replace(r))
    s3_replace = sum(
        1
        for r in media
        if r.catalogue_s3_status == S3Status.EXISTS.value
        or (not r.catalogue_s3_status and r.catalogue_s3_exists)
    )
    preflight_errors = sum(1 for r in media if r.status == PreflightStatus.ERROR)
    governance_blocked = sum(
        1
        for r in media
        if r.governance_status
        and r.governance_status != GovernanceStatus.VERIFIED.value
    )
    skip = sum(1 for r in media if not is_ready_to_replace(r))
    return UploadSummary(
        files_scanned=discovery.media_count,
        files_to_replace=governed_ready,
        files_to_skip=skip,
        validation_errors=preflight_errors,
        s3_replace_candidates=s3_replace,
        governance_blocked=governance_blocked,
    )


def build_governed_upload_jobs(rows: list[PreflightRow]) -> list[UploadJob]:
    """Upload queue: only governance-ready rows may replace."""
    jobs: list[UploadJob] = []
    for row in rows:
        if row.discovered.excluded:
            continue

        action = UploadAction.REPLACE if is_ready_to_replace(row) else UploadAction.SKIP

        jobs.append(
            UploadJob(
                local_path=row.discovered.path,
                filename=row.discovered.original_filename,
                clean_filename=row.discovered.clean_filename,
                s3_key=row.s3_key,
                action=action,
                s3_exists=row.s3_exists,
                old_size=row.s3_size,
                governance_status=row.governance_status,
                resolution_method=row.resolution_method,
                resolved_asset_id=row.resolved_asset_id,
                resolved_file_set_id=row.resolved_file_set_id,
                resolved_iconik_s3_key=row.resolved_iconik_s3_key,
                metadata_status=row.metadata_status,
                governance_warnings=row.governance_warnings,
            )
        )
    return jobs


def all_replace_candidates_verified(rows: list[PreflightRow]) -> bool:
    """True when every row marked REPLACE has GovernanceStatus.VERIFIED."""
    replace_rows = [
        r
        for r in rows
        if not r.discovered.excluded and r.action == UploadAction.REPLACE.value
    ]
    if not replace_rows:
        return True
    return all(r.governance_status == GovernanceStatus.VERIFIED.value for r in replace_rows)


def write_governance_verification_report(rows: list[PreflightRow]) -> Path:
    """Write per-file governance + S3 verification JSON for Phase 2 diagnostics."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for row in _governance_media_rows(rows):
        records.append(
            {
                "filename": row.discovered.clean_filename,
                "governance_status": row.governance_status,
                "asset_id": row.resolved_asset_id,
                "file_set_id": row.resolved_file_set_id,
                "resolved_iconik_s3_key": row.resolved_iconik_s3_key,
                "s3_exists": row.s3_exists,
                "s3_status": row.s3_status,
                "catalogue_s3_exists": row.catalogue_s3_exists,
                "catalogue_s3_status": row.catalogue_s3_status,
                "resolution_method": row.resolution_method,
            }
        )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(records),
        "files": records,
    }
    GOVERNANCE_VERIFICATION_REPORT.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    logger.info("Wrote governance verification report: %s", GOVERNANCE_VERIFICATION_REPORT)
    return GOVERNANCE_VERIFICATION_REPORT


def _s3_status_from_preflight(row: PreflightRow) -> S3Status:
    if row.status == PreflightStatus.ERROR and row.s3_status == S3Status.ERROR.value:
        return S3Status.ERROR
    if row.s3_exists:
        return S3Status.EXISTS
    return S3Status.MISSING


def _type_mismatch_result(clean_filename: str) -> AssetResolutionResult:
    return AssetResolutionResult(
        local_filename=clean_filename,
        asset_type=ReplacementAssetType.ENGP,
        status=GovernanceStatus.TYPE_MISMATCH,
        target=None,
        message="Filename is not ENGP or CFX — expected *_ENGP.mp4 or *_CFX.mp4",
    )


def _iconik_unconfigured_result(clean_filename: str) -> AssetResolutionResult:
    return AssetResolutionResult(
        local_filename=clean_filename,
        asset_type=ReplacementAssetType.ENGP,
        status=GovernanceStatus.ERROR,
        target=None,
        message="Iconik credentials not configured — governance required for upload",
    )
