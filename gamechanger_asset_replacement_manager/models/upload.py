"""Upload and audit models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class UploadAction(str, Enum):
    REPLACE = "REPLACE"
    SKIP = "SKIP"


class UploadResultStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class UploadJob:
    local_path: Path
    filename: str
    clean_filename: str
    s3_key: str
    action: UploadAction
    s3_exists: bool
    old_size: int | None
    governance_status: str = ""
    resolution_method: str = ""
    resolved_asset_id: str = ""
    resolved_file_set_id: str = ""
    resolved_iconik_s3_key: str = ""
    metadata_status: str = ""
    governance_warnings: str = ""


@dataclass
class UploadProgress:
    current_file: str = ""
    completed: int = 0
    remaining: int = 0
    total: int = 0
    bytes_uploaded: int = 0
    success_count: int = 0
    failure_count: int = 0
    skipped_count: int = 0
    elapsed_seconds: float = 0.0
    speed_mbps: float = 0.0
    cancelled: bool = False


@dataclass
class UploadSummary:
    files_scanned: int = 0
    files_to_replace: int = 0
    files_to_skip: int = 0
    validation_errors: int = 0
    s3_replace_candidates: int = 0
    governance_blocked: int = 0


@dataclass
class AuditRecord:
    filename: str
    clean_filename: str
    catalogue: str
    s3_exists: bool
    old_size: int | None
    new_size: int | None
    uploaded: bool
    status: str
    governance_status: str = ""
    resolution_method: str = ""
    resolved_asset_id: str = ""
    resolved_file_set_id: str = ""
    resolved_iconik_s3_key: str = ""
    metadata_status: str = ""
    governance_warnings: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def as_dict(self) -> dict[str, object]:
        return {
            "filename": self.filename,
            "clean_filename": self.clean_filename,
            "catalogue": self.catalogue,
            "s3_exists": self.s3_exists,
            "old_size": self.old_size,
            "new_size": self.new_size,
            "uploaded": self.uploaded,
            "status": self.status,
            "governance_status": self.governance_status,
            "resolution_method": self.resolution_method,
            "resolved_asset_id": self.resolved_asset_id,
            "resolved_file_set_id": self.resolved_file_set_id,
            "resolved_iconik_s3_key": self.resolved_iconik_s3_key,
            "metadata_status": self.metadata_status,
            "governance_warnings": self.governance_warnings,
            "timestamp": self.timestamp,
        }


@dataclass
class ReplacementVerificationRecord:
    """Iconik preservation audit row for direct ENGP/CFX replacement."""

    filename: str
    asset_type: str
    asset_id_before: str
    asset_id_after: str
    file_set_before: str
    file_set_after: str
    file_id_before: str = ""
    file_id_after: str = ""
    format_id_before: str = ""
    format_id_after: str = ""
    storage_id_before: str = ""
    storage_id_after: str = ""
    metadata_count_before: int = 0
    metadata_count_after: int = 0
    metadata_status: str = ""
    metadata_status_after: str = ""
    replacement_method: str = "SCAN_FALLBACK"
    status: str = ""
    message: str = ""
    uploaded: bool = True
    resolution_method: str = ""
    duplicate_count: int = 0
    resolved_asset_id: str = ""
    resolved_file_set_id: str = ""
    resolved_iconik_s3_key: str = ""
    governance_status: str = ""
    resolved_asset_title: str = ""
    resolved_file_set_name: str = ""
    governance_warnings: str = ""
    local_cfx_filename: str = ""
    local_cfx_size: int | None = None
    local_cfx_md5: str = ""
    iconik_base_dir_before: str = ""
    iconik_file_name_before: str = ""
    iconik_storage_path_before: str = ""
    catalogue_upload_key: str = ""
    iconik_storage_key: str = ""
    remote_object_size: int | None = None
    remote_object_md5: str = ""
    remote_catalogue_size: int | None = None
    remote_catalogue_md5: str = ""
    iconik_storage_key_after: str = ""
    iconik_storage_path_after: str = ""
    verify_reached_iconik_object: str = ""
    verify_size_match: str = ""
    verify_hash_match: str = ""
    verify_fileset_points_elsewhere: str = ""
    cfx_diagnosis: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def as_dict(self) -> dict[str, object]:
        return {
            "filename": self.filename,
            "type": self.asset_type,
            "asset_id_before": self.asset_id_before,
            "asset_id_after": self.asset_id_after,
            "file_set_before": self.file_set_before,
            "file_set_after": self.file_set_after,
            "file_id_before": self.file_id_before,
            "file_id_after": self.file_id_after,
            "format_id_before": self.format_id_before,
            "format_id_after": self.format_id_after,
            "storage_id_before": self.storage_id_before,
            "storage_id_after": self.storage_id_after,
            "metadata_count_before": self.metadata_count_before,
            "metadata_count_after": self.metadata_count_after,
            "metadata_status": self.metadata_status,
            "metadata_status_after": self.metadata_status_after,
            "replacement_method": self.replacement_method,
            "resolution_method": self.resolution_method,
            "duplicate_count": self.duplicate_count,
            "resolved_asset_id": self.resolved_asset_id,
            "resolved_file_set_id": self.resolved_file_set_id,
            "resolved_iconik_s3_key": self.resolved_iconik_s3_key,
            "governance_status": self.governance_status,
            "resolved_asset_title": self.resolved_asset_title,
            "resolved_file_set_name": self.resolved_file_set_name,
            "governance_warnings": self.governance_warnings,
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
            "cfx_diagnosis": self.cfx_diagnosis,
            "status": self.status,
            "message": self.message,
            "uploaded": self.uploaded,
            "timestamp": self.timestamp,
        }
