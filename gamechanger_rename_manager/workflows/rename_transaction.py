"""Transactional rename workflow (6 phases)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from gamechanger_rename_manager.config.settings import AppSettings
from gamechanger_rename_manager.services.asset_model import (
    AssetRecord,
    IntegrityLevel,
    PlannedOperation,
    RenamePlan,
)
from gamechanger_rename_manager.services.audit_log import AuditLogger
from gamechanger_rename_manager.services.iconik_client import IconikClient
from gamechanger_rename_manager.services.integrity import analyze_rename_plan
from gamechanger_rename_manager.services.asset_model import FileSetRecord
from gamechanger_rename_manager.services.s3_service import S3Service, s3_key_from_file_set

logger = logging.getLogger(__name__)

LogFn = Callable[[str], None]


@dataclass
class TransactionResult:
    success: bool
    message: str
    plan: RenamePlan
    log_lines: list[str] = field(default_factory=list)
    dry_run: bool = False


class RenameTransactionEngine:
    def __init__(
        self,
        settings: AppSettings,
        *,
        iconik: IconikClient | None = None,
        s3: S3Service | None = None,
    ) -> None:
        self._settings = settings
        self._iconik = iconik or IconikClient(settings)
        self._s3 = s3 or S3Service(settings)
        self._audit = AuditLogger(settings)

    def _primary_file_set(self, asset: AssetRecord) -> FileSetRecord | None:
        for fs in asset.file_sets:
            if fs.fileset_id and fs.fileset_id == asset.fileset_id:
                return fs
        return asset.file_sets[0] if asset.file_sets else None

    def _resolve_s3_keys(
        self, asset: AssetRecord, old_filename: str, new_filename: str
    ) -> tuple[str, str, str | None]:
        fs = self._primary_file_set(asset)
        bucket = fs.bucket if fs and fs.bucket else self._s3.bucket()
        if fs and (fs.base_dir or fs.name):
            src_key = s3_key_from_file_set(fs.base_dir, fs.name or old_filename)
            dest_key = s3_key_from_file_set(fs.base_dir, new_filename)
        else:
            src_key = asset.s3_key or self._s3.resolve_key("", old_filename)
            dest_key = self._s3.resolve_key(asset.s3_key, new_filename)
        return src_key, dest_key, bucket or None

    def build_plan(self, asset: AssetRecord, new_filename: str) -> RenamePlan:
        old = asset.file_set_name or asset.title
        ops: list[PlannedOperation] = []
        src_key, dest_key, bucket = self._resolve_s3_keys(asset, old, new_filename)
        bucket = bucket or self._s3.bucket()

        if self._settings.enable_s3_backup and src_key:
            ops.append(
                PlannedOperation(
                    "PHASE 1",
                    f"S3 backup: s3://{bucket}/{src_key}",
                    "Optional copy to backup prefix",
                )
            )
        ops.append(
            PlannedOperation(
                "PHASE 2",
                f"S3 copy: s3://{bucket}/{src_key} -> s3://{bucket}/{dest_key}",
            )
        )
        ops.append(
            PlannedOperation(
                "PHASE 3",
                f"Iconik PATCH asset title -> {new_filename!r}",
                f"asset_id={asset.asset_id}",
            )
        )
        ops.append(
            PlannedOperation(
                "PHASE 4",
                "Iconik PATCH file_set name (CRITICAL)",
                (
                    f"PATCH /API/files/v1/assets/{asset.asset_id}/file_sets/"
                    f"{asset.fileset_id}/  payload={{\"name\": {new_filename!r}}}"
                ),
            )
        )
        ops.append(
            PlannedOperation(
                "PHASE 5",
                "Validate S3 object, file_set name, playback probe",
            )
        )
        ops.append(PlannedOperation("PHASE 6", "Write audit log"))

        warnings = analyze_rename_plan(asset, new_filename, self._s3)
        return RenamePlan(
            asset=asset,
            old_filename=old,
            new_filename=new_filename,
            variant=asset.variant,
            operations=ops,
            warnings=warnings,
        )

    def execute(
        self,
        asset: AssetRecord,
        new_filename: str,
        *,
        dry_run: bool = False,
        log: LogFn | None = None,
    ) -> TransactionResult:
        plan = self.build_plan(asset, new_filename)
        lines: list[str] = []

        def emit(msg: str) -> None:
            lines.append(msg)
            logger.info(msg)
            if log:
                log(msg)

        blocking = [w for w in plan.warnings if w.level == IntegrityLevel.ERROR]
        if blocking:
            msg = "; ".join(w.message for w in blocking)
            emit(f"ABORT: integrity errors — {msg}")
            return TransactionResult(False, msg, plan, lines, dry_run=dry_run)

        if not asset.fileset_id:
            msg = "No file_set ID on selected asset — cannot PATCH file_set"
            emit(f"ABORT: {msg}")
            return TransactionResult(False, msg, plan, lines, dry_run=dry_run)

        emit(f"=== Transaction {'DRY RUN' if dry_run else 'EXECUTE'} ===")
        emit(f"Asset {asset.asset_id} | {plan.old_filename} -> {plan.new_filename}")

        src_key, dest_key, bucket = self._resolve_s3_keys(asset, plan.old_filename, plan.new_filename)
        emit("SOURCE KEY:")
        emit(src_key)
        emit("DESTINATION KEY:")
        emit(dest_key)
        fs = self._primary_file_set(asset)
        if fs:
            emit(f"file_set base_dir={fs.base_dir!r} name={fs.name!r}")

        for op in plan.operations:
            emit(f"{op.phase}: {op.description}")
            if op.detail:
                emit(f"  {op.detail}")

        if dry_run:
            emit("DRY RUN complete — no changes applied")
            self._audit.append_daily_log(
                f"DRY-RUN asset={asset.asset_id} {plan.old_filename} -> {plan.new_filename}"
            )
            return TransactionResult(True, "Dry run complete", plan, lines, dry_run=True)

        s3_ops: list[str] = []
        patch_ops: list[str] = []

        # PHASE 1 — backup
        if self._settings.enable_s3_backup and src_key:
            ok, msg, backup_key = self._s3.backup_object(src_key, bucket=bucket, dry_run=False)
            emit(f"PHASE 1: {msg}")
            s3_ops.append(msg)
            if not ok:
                return self._fail(asset, plan, lines, s3_ops, patch_ops, "S3 backup failed")

        # PHASE 2 — copy to new key
        if src_key and dest_key and src_key != dest_key:
            ok, msg = self._s3.copy_object(src_key, dest_key, bucket=bucket, dry_run=False)
            emit(f"PHASE 2: {msg}")
            s3_ops.append(msg)
            if not ok:
                return self._fail(asset, plan, lines, s3_ops, patch_ops, "S3 copy failed")

        # PHASE 3 — asset title
        ok, msg = self._iconik.update_asset_title(asset.asset_id, plan.new_filename)
        emit(f"PHASE 3: {msg}")
        patch_ops.append(f"asset title: {msg}")
        if not ok:
            return self._fail(asset, plan, lines, s3_ops, patch_ops, "Asset title update failed")

        # PHASE 4 — file_set PATCH (production-validated endpoint)
        ok, msg = self._iconik.patch_file_set(
            asset.asset_id,
            asset.fileset_id,
            {"name": plan.new_filename},
        )
        emit(f"PHASE 4: {msg}")
        patch_ops.append(
            f"PATCH files/v1/assets/{asset.asset_id}/file_sets/{asset.fileset_id}/ : {msg}"
        )
        if not ok:
            return self._fail(asset, plan, lines, s3_ops, patch_ops, "file_set PATCH failed")

        # PHASE 5 — validation
        valid_ok, valid_msg = self._validate(asset, plan, bucket)
        emit(f"PHASE 5: {valid_msg}")
        if not valid_ok:
            return self._fail(asset, plan, lines, s3_ops, patch_ops, valid_msg)

        # PHASE 6 — audit
        record = {
            "asset_id": asset.asset_id,
            "fileset_id": asset.fileset_id,
            "old_filename": plan.old_filename,
            "new_filename": plan.new_filename,
            "variant_type": plan.variant.value,
            "s3_operations": s3_ops,
            "patch_operations": patch_ops,
            "success": True,
        }
        path = self._audit.log_transaction(record)
        self._audit.append_daily_log(
            f"OK asset={asset.asset_id} {plan.old_filename} -> {plan.new_filename}"
        )
        emit(f"PHASE 6: Audit log -> {path}")
        emit("=== Transaction SUCCESS ===")
        return TransactionResult(True, "Transaction completed", plan, lines, dry_run=False)

    def _validate(
        self,
        asset: AssetRecord,
        plan: RenamePlan,
        bucket: str | None,
    ) -> tuple[bool, str]:
        _, dest_key, _ = self._resolve_s3_keys(asset, plan.old_filename, plan.new_filename)
        logger.info("VALIDATE DESTINATION KEY: %s", dest_key)
        if dest_key:
            exists, detail = self._s3.object_exists(dest_key, bucket)
            if not exists:
                return False, f"S3 validation failed: {dest_key} ({detail})"

        fs, err = self._iconik.list_file_sets(asset.asset_id)
        if err:
            return False, f"file_set re-fetch failed: {err}"
        match = next((f for f in fs if f.fileset_id == asset.fileset_id), None)
        if match and match.name.strip() != plan.new_filename.strip():
            return False, f"file_set name still {match.name!r}, expected {plan.new_filename!r}"
        return True, "S3 + file_set validation OK"

    def _fail(
        self,
        asset: AssetRecord,
        plan: RenamePlan,
        lines: list[str],
        s3_ops: list[str],
        patch_ops: list[str],
        reason: str,
    ) -> TransactionResult:
        logger.error("Transaction failed: %s", reason)
        self._audit.log_transaction(
            {
                "asset_id": asset.asset_id,
                "fileset_id": asset.fileset_id,
                "old_filename": plan.old_filename,
                "new_filename": plan.new_filename,
                "variant_type": plan.variant.value,
                "s3_operations": s3_ops,
                "patch_operations": patch_ops,
                "success": False,
                "error": reason,
            }
        )
        self._audit.append_daily_log(
            f"FAIL asset={asset.asset_id} {plan.old_filename} -> {plan.new_filename}: {reason}"
        )
        lines.append(f"=== Transaction FAILED: {reason} ===")
        return TransactionResult(False, reason, plan, lines, dry_run=False)
