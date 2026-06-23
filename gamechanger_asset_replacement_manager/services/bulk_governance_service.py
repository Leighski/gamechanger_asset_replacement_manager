"""Iconik governance pass for Source Files bulk upload candidates."""

from __future__ import annotations

import logging

from models.catalogue import CatalogueDefinition
from models.discovery import DiscoveryResult, PreflightRow, PreflightStatus
from models.upload import UploadAction, UploadJob, UploadSummary
from services.asset_resolution_service import (
    AssetResolutionResult,
    AssetResolutionService,
    GovernanceStatus,
)
from services.dual_replacement_service import ReplacementTarget
from services.iconik_verification import IconikVerificationService
from services.replacement_variant import ReplacementAssetType, detect_replacement_type

logger = logging.getLogger(__name__)


def resolve_governance_for_preflight(
    rows: list[PreflightRow],
    *,
    catalogue: CatalogueDefinition,
    iconik: IconikVerificationService,
) -> list[AssetResolutionResult]:
    """Run AssetResolutionService for each S3 REPLACE preflight candidate."""
    replace_rows = [
        row
        for row in rows
        if not row.discovered.excluded
        and row.action == UploadAction.REPLACE.value
        and row.discovered.clean_filename
    ]

    if not replace_rows:
        return []

    if not iconik.configured():
        logger.warning("Iconik not configured — bulk governance cannot resolve assets")
        return [
            _iconik_unconfigured_result(row.discovered.clean_filename)
            for row in replace_rows
        ]

    targets: list[ReplacementTarget] = []
    synthetic: list[AssetResolutionResult] = []

    for row in replace_rows:
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

    for row in rows:
        if row.discovered.excluded or row.action != UploadAction.REPLACE.value:
            continue
        clean_name = row.discovered.clean_filename
        result = by_filename.get(clean_name)
        if result is None:
            row.governance_status = GovernanceStatus.NOT_FOUND.value
            row.governance_message = "No governance result returned"
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


def build_governed_summary(
    rows: list[PreflightRow],
    discovery: DiscoveryResult,
) -> UploadSummary:
    """Recompute upload summary after governance — ready = S3 REPLACE + VERIFIED."""
    media = [r for r in rows if not r.discovered.excluded]
    s3_replace = sum(1 for r in media if r.action == UploadAction.REPLACE.value)
    governed_ready = sum(
        1
        for r in media
        if r.action == UploadAction.REPLACE.value
        and r.governance_status == GovernanceStatus.VERIFIED.value
    )
    preflight_errors = sum(1 for r in media if r.status == PreflightStatus.ERROR)
    governance_blocked = sum(
        1
        for r in media
        if r.action == UploadAction.REPLACE.value
        and r.governance_status
        and r.governance_status != GovernanceStatus.VERIFIED.value
    )
    skip = sum(
        1
        for r in media
        if r.action == UploadAction.SKIP.value
        or (
            r.action == UploadAction.REPLACE.value
            and r.governance_status != GovernanceStatus.VERIFIED.value
        )
    )
    return UploadSummary(
        files_scanned=discovery.media_count,
        files_to_replace=governed_ready,
        files_to_skip=skip,
        validation_errors=preflight_errors,
        s3_replace_candidates=s3_replace,
        governance_blocked=governance_blocked,
    )


def build_governed_upload_jobs(rows: list[PreflightRow]) -> list[UploadJob]:
    """Upload queue: only S3 REPLACE rows with VERIFIED governance may replace."""
    jobs: list[UploadJob] = []
    for row in rows:
        if row.discovered.excluded:
            continue

        s3_replace = row.action == UploadAction.REPLACE.value
        governed = row.governance_status == GovernanceStatus.VERIFIED.value
        if s3_replace and governed:
            action = UploadAction.REPLACE
        else:
            action = UploadAction.SKIP

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
    """True when every S3 REPLACE candidate has GovernanceStatus.VERIFIED."""
    replace_rows = [
        r
        for r in rows
        if not r.discovered.excluded and r.action == UploadAction.REPLACE.value
    ]
    if not replace_rows:
        return True
    return all(r.governance_status == GovernanceStatus.VERIFIED.value for r in replace_rows)


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
        status=GovernanceStatus.NOT_FOUND,
        target=None,
        message="Iconik credentials not configured — governance required for upload",
    )
