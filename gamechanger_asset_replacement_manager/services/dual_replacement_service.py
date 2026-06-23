"""Single-operation ENGP and/or CFX replacement with Iconik verification."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from models.catalogue import CatalogueDefinition
from models.upload import ReplacementVerificationRecord
from services.asset_resolution_service import (
    AssetResolutionResult,
    AssetResolutionService,
    GovernanceStatus,
    ResolvedAssetTarget,
)
from services.cfx_replacement_audit import CfxReplacementAudit, audit_cfx_replacement, log_cfx_pre_replacement
from services.content_verification import ContentFingerprint, fingerprint_file
from services.iconik_verification import (
    REPLACEMENT_SCAN_FALLBACK,
    IconikAssetReference,
    IconikVerificationService,
    VERIFY_FAIL,
)
from services.replacement_variant import (
    ReplacementAssetType,
    detect_replacement_type,
    stems_associated,
)
from services.s3_service import S3Service

logger = logging.getLogger(__name__)

LogFn = Callable[[str], None]


@dataclass(frozen=True)
class ReplacementTarget:
    local_path: Path
    asset_type: ReplacementAssetType
    iconik_filename: str
    s3_key: str


@dataclass(frozen=True)
class DualReplacementOutcome:
    records: list[ReplacementVerificationRecord]
    batch_failed: bool
    failure_records: list[ReplacementVerificationRecord]
    resolution_results: list[AssetResolutionResult] = field(default_factory=list)


class DualReplacementService:
    def __init__(
        self,
        s3: S3Service,
        iconik: IconikVerificationService,
        resolver: AssetResolutionService | None = None,
    ) -> None:
        self._s3 = s3
        self._iconik = iconik
        self._resolver = resolver or AssetResolutionService(iconik)

    def build_targets(
        self,
        *,
        engp_path: str = "",
        cfx_path: str = "",
        catalogue: CatalogueDefinition,
    ) -> list[ReplacementTarget]:
        targets: list[ReplacementTarget] = []
        if engp_path.strip():
            path = Path(engp_path.strip())
            asset_type = detect_replacement_type(path.name)
            if asset_type != ReplacementAssetType.ENGP:
                raise ValueError(f"ENGP file must match *_ENGP.mp4: {path.name}")
            key = catalogue.location.key_for_filename(path.name)
            targets.append(
                ReplacementTarget(
                    local_path=path,
                    asset_type=ReplacementAssetType.ENGP,
                    iconik_filename=path.name,
                    s3_key=key,
                )
            )
        if cfx_path.strip():
            path = Path(cfx_path.strip())
            asset_type = detect_replacement_type(path.name)
            if asset_type != ReplacementAssetType.CFX:
                raise ValueError(f"CFX file must match *_CFX.mp4: {path.name}")
            key = catalogue.location.key_for_filename(path.name)
            targets.append(
                ReplacementTarget(
                    local_path=path,
                    asset_type=ReplacementAssetType.CFX,
                    iconik_filename=path.name,
                    s3_key=key,
                )
            )
        if len(targets) == 2 and not stems_associated(
            targets[0].iconik_filename, targets[1].iconik_filename
        ):
            raise ValueError(
                "ENGP and CFX stems do not match. "
                f"Expected paired files for the same event stem."
            )
        if not targets:
            raise ValueError("Select at least one replacement file (ENGP and/or CFX).")
        for target in targets:
            if not target.local_path.is_file():
                raise FileNotFoundError(f"Replacement file not found: {target.local_path}")
        return targets

    def resolve_targets(
        self,
        targets: list[ReplacementTarget],
        catalogue: CatalogueDefinition,
    ) -> list[AssetResolutionResult]:
        return self._resolver.resolve_batch(targets, catalogue=catalogue)

    @staticmethod
    def resolutions_are_runnable(results: list[AssetResolutionResult]) -> bool:
        return bool(results) and all(r.status == GovernanceStatus.VERIFIED and r.target for r in results)

    def _upload_keys_for_target(
        self,
        target: ReplacementTarget,
        resolved: ResolvedAssetTarget,
    ) -> list[str]:
        keys = [resolved.iconik_s3_key]
        if target.s3_key and target.s3_key not in keys:
            keys.append(target.s3_key)
        return keys

    def run(
        self,
        targets: list[ReplacementTarget],
        resolutions: list[AssetResolutionResult],
        catalogue: CatalogueDefinition,
        *,
        preserve_asset_ids: bool = True,
        log: LogFn | None = None,
    ) -> DualReplacementOutcome:
        def emit(msg: str) -> None:
            logger.info(msg)
            if log:
                log(msg)

        if not self._iconik.configured():
            raise RuntimeError("Iconik credentials and storage ID are required in Preferences.")

        resolution_by_filename = {r.local_filename: r for r in resolutions}
        if not self.resolutions_are_runnable(resolutions):
            blocked = [
                f"{r.local_filename}: {r.status.value} — {r.message}"
                for r in resolutions
                if r.status != GovernanceStatus.VERIFIED
            ]
            raise RuntimeError(
                "Replacement blocked: asset resolution is not VERIFIED.\n" + "\n".join(blocked)
            )

        pre_snapshots: dict[str, IconikAssetReference] = {}
        resolved_targets: dict[str, ResolvedAssetTarget] = {}
        cfx_local_fps: dict[str, ContentFingerprint] = {}
        replacement_methods: dict[str, str] = {}
        needs_scan_fallback = False

        for target in targets:
            label = target.asset_type.value
            resolution = resolution_by_filename[target.iconik_filename]
            resolved = resolution.target
            if resolved is None:
                raise RuntimeError(f"Missing resolved target for {target.iconik_filename}")

            resolved_targets[target.iconik_filename] = resolved
            before = resolved.to_iconik_reference()
            pre_snapshots[target.iconik_filename] = before

            emit(f"[{label}] Replacement Started")
            emit(f"[GOVERNANCE] Status: {resolution.status.value}")
            emit(f"[GOVERNANCE] Resolution: {resolution.resolution_method}")
            if resolution.governance_warnings:
                emit(
                    f"[GOVERNANCE] Warnings: {', '.join(resolution.governance_warnings)}"
                )
            self._iconik.log_existing_asset(before, emit)
            if target.asset_type == ReplacementAssetType.CFX:
                cfx_local_fps[target.iconik_filename] = log_cfx_pre_replacement(
                    target_path=target.local_path,
                    before=before,
                    emit=emit,
                )

        for target in targets:
            label = target.asset_type.value
            before = pre_snapshots[target.iconik_filename]
            resolved = resolved_targets[target.iconik_filename]
            resolution = resolution_by_filename[target.iconik_filename]
            upload_keys = self._upload_keys_for_target(target, resolved)

            if resolved.iconik_s3_key != target.s3_key:
                emit(
                    f"[{label}] Iconik S3 key differs from catalogue key — "
                    f"uploading to both"
                )
                emit(f"[{label}] Catalogue key: {target.s3_key}")
                emit(f"[{label}] Iconik key: {resolved.iconik_s3_key}")

            primary_exists = False
            for key in upload_keys:
                info = self._s3.head_object(catalogue.location, key)
                if info.exists:
                    primary_exists = True
                    break
            if not primary_exists:
                raise RuntimeError(
                    f"S3 object missing for {resolved.iconik_s3_key}. "
                    "Enable only replacement of existing objects."
                )

            content_type = S3Service.content_type_for_filename(target.iconik_filename)
            for key in upload_keys:
                ok, msg = self._s3.upload_file(
                    str(target.local_path),
                    catalogue.location,
                    key,
                    content_type=content_type,
                )
                if not ok:
                    raise RuntimeError(f"S3 upload failed for {key}: {msg}")
                emit(f"[{label}] S3 upload complete → {key}")

            verify_key = resolved.iconik_s3_key or target.s3_key
            content_ok, content_detail = self._s3.remote_matches_local(
                catalogue.location,
                verify_key,
                target.local_path,
            )
            emit(
                f"[{label}] Remote content check ({verify_key}): "
                f"{'MATCH' if content_ok else 'MISMATCH'} — {content_detail}"
            )

            method = REPLACEMENT_SCAN_FALLBACK
            if preserve_asset_ids:
                direct = self._iconik.attempt_direct_replacement(target.local_path, before)
                if direct.success:
                    method = direct.method
                    emit("[ICONIK] DIRECT REPLACEMENT SUCCESS")
                    emit(f"[ICONIK] Method: {method}")
                else:
                    emit("[ICONIK] DIRECT REPLACEMENT FAILED")
                    emit("Falling back to storage scan workflow")
                    if "metadata sync only" in direct.message:
                        emit(
                            "[ICONIK] Metadata-only Iconik update detected — "
                            "scan required to refresh playback content"
                        )
                needs_scan_fallback = True
            else:
                needs_scan_fallback = True

            if not content_ok:
                emit(f"[{label}] WARNING: remote object does not match local source")
                needs_scan_fallback = True

            replacement_methods[target.iconik_filename] = method
            emit(f"[{label}] Replacement Complete")

        if needs_scan_fallback:
            scan_result = self._iconik.trigger_storage_scan()
            emit(f"Iconik storage scan: {scan_result}")
            if not self._iconik.wait_for_scan():
                logger.warning("Iconik storage scan wait timed out")

        records: list[ReplacementVerificationRecord] = []
        failure_records: list[ReplacementVerificationRecord] = []
        batch_failed = False

        for target in targets:
            if batch_failed:
                break
            before = pre_snapshots[target.iconik_filename]
            resolution = resolution_by_filename[target.iconik_filename]
            after = self._iconik.snapshot_by_asset_id(before.asset_id)
            verification = self._iconik.verify_preservation(
                before,
                after,
                require_file_id=preserve_asset_ids,
            )
            label = target.asset_type.value
            method = replacement_methods.get(target.iconik_filename, REPLACEMENT_SCAN_FALLBACK)
            emit(f"[VERIFY] POST-CHECK asset_id {before.asset_id}")
            if after:
                emit(f"[VERIFY] Asset ID {after.asset_id}")
            emit(f"[VERIFY] {verification.status} {target.iconik_filename}")

            cfx_audit: CfxReplacementAudit | None = None
            audit_message = verification.message
            if target.asset_type == ReplacementAssetType.CFX:
                cfx_audit = audit_cfx_replacement(
                    target_path=target.local_path,
                    catalogue=catalogue,
                    catalogue_s3_key=target.s3_key,
                    before=before,
                    after=after,
                    replacement_method=method,
                    s3=self._s3,
                    emit=emit,
                    local_fp=cfx_local_fps.get(target.iconik_filename),
                )
                audit_message = (
                    f"{verification.message}; {cfx_audit.diagnosis}"
                    if verification.message
                    else cfx_audit.diagnosis
                )

            record = self._build_verification_record(
                target=target,
                before=before,
                after=after,
                method=method,
                verification_status=verification.status,
                message=audit_message,
                cfx_audit=cfx_audit,
                resolution=resolution,
            )
            records.append(record)

            if self._iconik.asset_id_changed(before, after):
                emit("✗ CRITICAL ERROR — ASSET ID CHANGED")
                emit(f"[VERIFY] PRE-CHECK Asset {before.asset_id}")
                emit(f"[VERIFY] POST-CHECK Asset {after.asset_id if after else 'MISSING'}")
                emit("[VERIFY] FAIL Asset ID changed")
                emit("BATCH FAILED")
                batch_failed = True
                failure_records.append(
                    self._build_verification_record(
                        target=target,
                        before=before,
                        after=after,
                        method=method,
                        verification_status=VERIFY_FAIL,
                        message="Asset ID preservation failed",
                        cfx_audit=cfx_audit,
                        resolution=resolution,
                    )
                )
                break

        return DualReplacementOutcome(
            records=records,
            batch_failed=batch_failed,
            failure_records=failure_records,
            resolution_results=resolutions,
        )

    @staticmethod
    def _build_verification_record(
        *,
        target: ReplacementTarget,
        before: IconikAssetReference,
        after: IconikAssetReference | None,
        method: str,
        verification_status: str,
        message: str,
        cfx_audit: CfxReplacementAudit | None,
        resolution: AssetResolutionResult,
    ) -> ReplacementVerificationRecord:
        cfx_fields: dict[str, object] = {}
        if cfx_audit is not None:
            cfx_fields = cfx_audit.as_report_fields()

        return ReplacementVerificationRecord(
            filename=target.iconik_filename,
            asset_type=target.asset_type.value,
            asset_id_before=before.asset_id,
            asset_id_after=after.asset_id if after else "",
            file_set_before=before.file_set_id,
            file_set_after=after.file_set_id if after else "",
            file_id_before=before.file_id,
            file_id_after=after.file_id if after else "",
            format_id_before=before.format_id,
            format_id_after=after.format_id if after else "",
            storage_id_before=before.storage_id,
            storage_id_after=after.storage_id if after else "",
            metadata_count_before=before.metadata_field_count,
            metadata_count_after=after.metadata_field_count if after else 0,
            metadata_status=before.metadata_status,
            metadata_status_after=after.metadata_status if after else "",
            replacement_method=method,
            status=verification_status,
            message=message,
            uploaded=True,
            resolution_method=resolution.resolution_method,
            duplicate_count=resolution.duplicate_count,
            resolved_asset_id=resolution.resolved_asset_id,
            resolved_file_set_id=resolution.resolved_file_set_id,
            resolved_iconik_s3_key=resolution.resolved_iconik_s3_key,
            governance_status=resolution.status.value,
            resolved_asset_title=(
                resolution.target.asset_title if resolution.target else ""
            ),
            resolved_file_set_name=(
                resolution.target.iconik_filename if resolution.target else ""
            ),
            governance_warnings=(
                ", ".join(resolution.governance_warnings)
                if resolution.governance_warnings
                else ""
            ),
            local_cfx_filename=str(cfx_fields.get("local_cfx_filename", "")),
            local_cfx_size=cfx_fields.get("local_cfx_size"),  # type: ignore[arg-type]
            local_cfx_md5=str(cfx_fields.get("local_cfx_md5", "")),
            iconik_base_dir_before=str(cfx_fields.get("iconik_base_dir_before", "")),
            iconik_file_name_before=str(cfx_fields.get("iconik_file_name_before", "")),
            iconik_storage_path_before=str(cfx_fields.get("iconik_storage_path_before", "")),
            catalogue_upload_key=str(cfx_fields.get("catalogue_upload_key", "")),
            iconik_storage_key=str(cfx_fields.get("iconik_storage_key", "")),
            remote_object_size=cfx_fields.get("remote_object_size"),  # type: ignore[arg-type]
            remote_object_md5=str(cfx_fields.get("remote_object_md5", "")),
            remote_catalogue_size=cfx_fields.get("remote_catalogue_size"),  # type: ignore[arg-type]
            remote_catalogue_md5=str(cfx_fields.get("remote_catalogue_md5", "")),
            iconik_storage_key_after=str(cfx_fields.get("iconik_storage_key_after", "")),
            iconik_storage_path_after=str(cfx_fields.get("iconik_storage_path_after", "")),
            verify_reached_iconik_object=str(cfx_fields.get("verify_reached_iconik_object", "")),
            verify_size_match=str(cfx_fields.get("verify_size_match", "")),
            verify_hash_match=str(cfx_fields.get("verify_hash_match", "")),
            verify_fileset_points_elsewhere=str(cfx_fields.get("verify_fileset_points_elsewhere", "")),
            cfx_diagnosis=str(cfx_fields.get("cfx_diagnosis", "")),
        )
