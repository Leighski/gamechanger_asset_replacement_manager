"""CFX.mp4 replacement diagnostics and storage-object verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from models.catalogue import CatalogueDefinition
from services.content_verification import ContentFingerprint, etag_to_md5, fingerprint_file
from services.iconik_verification import IconikAssetReference
from services.s3_service import S3Service

LogFn = Callable[[str], None]

VERIFY_PASS = "PASS"
VERIFY_FAIL = "FAIL"


@dataclass(frozen=True)
class CfxReplacementAudit:
    local_cfx_filename: str
    local_cfx_size: int
    local_cfx_md5: str
    asset_id_before: str
    file_set_id_before: str
    file_id_before: str
    storage_id_before: str
    iconik_base_dir_before: str
    iconik_file_name_before: str
    iconik_storage_path_before: str
    catalogue_upload_key: str
    iconik_storage_key: str
    remote_object_size: int | None
    remote_object_md5: str
    remote_catalogue_size: int | None
    remote_catalogue_md5: str
    iconik_storage_key_after: str
    iconik_storage_path_after: str
    file_id_after: str
    verify_reached_iconik_object: str
    verify_size_match: str
    verify_hash_match: str
    verify_fileset_points_elsewhere: str
    replacement_method: str
    diagnosis: str

    def as_report_fields(self) -> dict[str, object]:
        return {
            "local_cfx_filename": self.local_cfx_filename,
            "local_cfx_size": self.local_cfx_size,
            "local_cfx_md5": self.local_cfx_md5,
            "iconik_base_dir_before": self.iconik_base_dir_before,
            "iconik_file_name_before": self.iconik_file_name_before,
            "iconik_storage_path_before": self.iconik_storage_path_before,
            "catalogue_upload_key": self.catalogue_upload_key,
            "iconik_storage_key": self.iconik_storage_key,
            "remote_object_size": self.remote_object_size,
            "remote_object_md5": self.remote_object_md5,
            "remote_catalogue_size": self.remote_catalogue_size,
            "remote_catalogue_md5": self.remote_catalogue_md5,
            "iconik_storage_key_after": self.iconik_storage_key_after,
            "iconik_storage_path_after": self.iconik_storage_path_after,
            "verify_reached_iconik_object": self.verify_reached_iconik_object,
            "verify_size_match": self.verify_size_match,
            "verify_hash_match": self.verify_hash_match,
            "verify_fileset_points_elsewhere": self.verify_fileset_points_elsewhere,
            "cfx_diagnosis": self.diagnosis,
        }


def log_cfx_pre_replacement(
    *,
    target_path: Path,
    before: IconikAssetReference,
    emit: LogFn,
) -> ContentFingerprint:
    local_fp = fingerprint_file(target_path)
    emit(f"[CFX-AUDIT] Local CFX.mp4 filename: {target_path.name}")
    emit(f"[CFX-AUDIT] Local CFX.mp4 file size: {local_fp.size}")
    emit(f"[CFX-AUDIT] Local CFX.mp4 MD5: {local_fp.md5}")
    emit(f"[CFX-AUDIT] Iconik asset_id: {before.asset_id}")
    emit(f"[CFX-AUDIT] Iconik file_set_id: {before.file_set_id}")
    emit(f"[CFX-AUDIT] Iconik file_id: {before.file_id}")
    emit(f"[CFX-AUDIT] Iconik storage_id: {before.storage_id}")
    emit(f"[CFX-AUDIT] Iconik base_dir: {before.iconik_base_dir}")
    emit(f"[CFX-AUDIT] Iconik file name: {before.iconik_file_name}")
    emit(f"[CFX-AUDIT] Iconik resolved storage path: {before.storage_path or before.iconik_s3_key}")
    return local_fp


def audit_cfx_replacement(
    *,
    target_path: Path,
    catalogue: CatalogueDefinition,
    catalogue_s3_key: str,
    before: IconikAssetReference,
    after: IconikAssetReference | None,
    replacement_method: str,
    s3: S3Service,
    emit: LogFn,
    local_fp: ContentFingerprint | None = None,
) -> CfxReplacementAudit:
    local_fp = local_fp or fingerprint_file(target_path)
    iconik_key = before.iconik_s3_key

    emit(f"[CFX-AUDIT] Catalogue upload key: {catalogue_s3_key}")
    emit(f"[CFX-AUDIT] Iconik resolved storage key: {iconik_key or '(unknown)'}")

    iconik_remote_fp, iconik_etag, iconik_err = (
        s3.fingerprint_remote_object(catalogue.location, iconik_key)
        if iconik_key
        else (None, None, "no iconik storage key")
    )
    cat_remote_fp, cat_etag, cat_err = s3.fingerprint_remote_object(
        catalogue.location, catalogue_s3_key
    )

    remote_size = iconik_remote_fp.size if iconik_remote_fp else None
    remote_md5 = iconik_remote_fp.md5 if iconik_remote_fp else (etag_to_md5(iconik_etag) or "")
    cat_size = cat_remote_fp.size if cat_remote_fp else None
    cat_md5 = cat_remote_fp.md5 if cat_remote_fp else (etag_to_md5(cat_etag) or "")

    emit(f"[CFX-AUDIT] Remote object size (Iconik key): {remote_size if remote_size is not None else 'missing'}")
    emit(f"[CFX-AUDIT] Remote object MD5 (Iconik key): {remote_md5 or iconik_err or 'unavailable'}")
    if iconik_key != catalogue_s3_key:
        emit(f"[CFX-AUDIT] Remote object size (catalogue key): {cat_size if cat_size is not None else 'missing'}")
        emit(f"[CFX-AUDIT] Remote object MD5 (catalogue key): {cat_md5 or cat_err or 'unavailable'}")

    verify_a = _verify_reached_iconik_object(
        iconik_key=iconik_key,
        iconik_remote_fp=iconik_remote_fp,
        local_fp=local_fp,
    )
    verify_b = VERIFY_PASS if remote_size == local_fp.size else VERIFY_FAIL
    verify_c = (
        VERIFY_PASS
        if iconik_remote_fp and iconik_remote_fp.md5 == local_fp.md5
        else VERIFY_FAIL
    )
    verify_d = _verify_fileset_points_elsewhere(before=before, after=after)

    emit(f"[CFX-AUDIT] A — uploaded to Iconik file_set object: {verify_a}")
    emit(f"[CFX-AUDIT] B — remote size matches local CFX.mp4: {verify_b}")
    emit(f"[CFX-AUDIT] C — remote hash matches local CFX.mp4: {verify_c}")
    emit(f"[CFX-AUDIT] D — file_set points at different object after replacement: {verify_d}")

    diagnosis = _diagnose(
        verify_a=verify_a,
        verify_b=verify_b,
        verify_c=verify_c,
        verify_d=verify_d,
        iconik_key=iconik_key,
        catalogue_s3_key=catalogue_s3_key,
        replacement_method=replacement_method,
    )
    emit(f"[CFX-AUDIT] Diagnosis: {diagnosis}")

    after_key = after.iconik_s3_key if after else ""
    after_path = after.storage_path if after else ""

    return CfxReplacementAudit(
        local_cfx_filename=target_path.name,
        local_cfx_size=local_fp.size,
        local_cfx_md5=local_fp.md5,
        asset_id_before=before.asset_id,
        file_set_id_before=before.file_set_id,
        file_id_before=before.file_id,
        storage_id_before=before.storage_id,
        iconik_base_dir_before=before.iconik_base_dir,
        iconik_file_name_before=before.iconik_file_name,
        iconik_storage_path_before=before.storage_path or before.iconik_s3_key,
        catalogue_upload_key=catalogue_s3_key,
        iconik_storage_key=iconik_key,
        remote_object_size=remote_size,
        remote_object_md5=remote_md5,
        remote_catalogue_size=cat_size,
        remote_catalogue_md5=cat_md5,
        iconik_storage_key_after=after_key,
        iconik_storage_path_after=after_path or after_key,
        file_id_after=after.file_id if after else "",
        verify_reached_iconik_object=verify_a,
        verify_size_match=verify_b,
        verify_hash_match=verify_c,
        verify_fileset_points_elsewhere=verify_d,
        replacement_method=replacement_method,
        diagnosis=diagnosis,
    )


def _verify_reached_iconik_object(
    *,
    iconik_key: str,
    iconik_remote_fp: ContentFingerprint | None,
    local_fp: ContentFingerprint,
) -> str:
    if not iconik_key:
        return VERIFY_FAIL
    if iconik_remote_fp is None:
        return VERIFY_FAIL
    return VERIFY_PASS if iconik_remote_fp.matches(local_fp) else VERIFY_FAIL


def _verify_fileset_points_elsewhere(
    *,
    before: IconikAssetReference,
    after: IconikAssetReference | None,
) -> str:
    if after is None:
        return VERIFY_FAIL
    before_ref = before.storage_path or before.iconik_s3_key
    after_ref = after.storage_path or after.iconik_s3_key
    if before.file_id and after.file_id and before.file_id != after.file_id:
        return VERIFY_FAIL
    if before_ref and after_ref and before_ref != after_ref:
        return VERIFY_FAIL
    if before.iconik_s3_key and after.iconik_s3_key and before.iconik_s3_key != after.iconik_s3_key:
        return VERIFY_FAIL
    return VERIFY_PASS


def _diagnose(
    *,
    verify_a: str,
    verify_b: str,
    verify_c: str,
    verify_d: str,
    iconik_key: str,
    catalogue_s3_key: str,
    replacement_method: str,
) -> str:
    if verify_a == VERIFY_FAIL and iconik_key and iconik_key != catalogue_s3_key:
        return (
            "Upload reached catalogue key but not Iconik file_set storage object "
            f"({iconik_key})"
        )
    if verify_a == VERIFY_FAIL:
        return "New CFX.mp4 binary not present at Iconik-resolved storage object"
    if verify_d == VERIFY_FAIL:
        return "File_set now references a different storage object after replacement"
    if verify_c == VERIFY_FAIL and verify_b == VERIFY_PASS:
        return "Remote size matches but hash differs — partial or corrupted upload"
    if verify_a == VERIFY_PASS and verify_c == VERIFY_PASS:
        return "CFX.mp4 verified at Iconik storage object"
    return f"Verification incomplete (method={replacement_method})"
