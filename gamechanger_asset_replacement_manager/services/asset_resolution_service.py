"""Deterministic Iconik asset resolution for governed replacement."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from models.catalogue import CatalogueDefinition
from services.paths import REPORTS_DIR
from services.replacement_variant import ReplacementAssetType, detect_replacement_type
from services.s3_service import S3Service

if TYPE_CHECKING:
    from services.dual_replacement_service import ReplacementTarget
    from services.iconik_verification import IconikVerificationService

logger = logging.getLogger(__name__)

RESOLUTION_BY_ASSET_ID = "BY_ASSET_ID"
RESOLUTION_BY_EXACT_TITLE = "BY_EXACT_TITLE"

DUPLICATE_CSV_COLUMNS = [
    "timestamp",
    "local_filename",
    "asset_type",
    "query_filename",
    "candidate_asset_id",
    "candidate_title",
    "candidate_file_set_id",
    "candidate_file_set_name",
    "candidate_s3_key",
    "candidate_storage_path",
    "duplicate_count",
    "governance_status",
]


class GovernanceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    DUPLICATE = "DUPLICATE"
    NOT_FOUND = "NOT_FOUND"
    PATH_MISMATCH = "PATH_MISMATCH"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    FILESET_MISMATCH = "FILESET_MISMATCH"
    ERROR = "ERROR"


GOVERNANCE_WARNING_TITLE_FILENAME_MISMATCH = "TITLE_FILENAME_MISMATCH"


@dataclass(frozen=True)
class AssetResolutionCandidate:
    asset_id: str
    title: str
    file_set_id: str
    file_set_name: str
    s3_key: str
    storage_path: str


@dataclass(frozen=True)
class ResolvedAssetTarget:
    asset_id: str
    file_set_id: str
    file_id: str
    iconik_filename: str
    iconik_s3_key: str
    local_path: Path
    resolution_method: str
    governance_status: GovernanceStatus = GovernanceStatus.VERIFIED
    format_id: str = ""
    storage_id: str = ""
    file_size: int = 0
    metadata_field_count: int = 0
    metadata_status: str = "AVAILABLE"
    iconik_base_dir: str = ""
    storage_path: str = ""
    catalogue_s3_key: str = ""
    asset_title: str = ""
    governance_warnings: tuple[str, ...] = ()

    def to_iconik_reference(self):
        from services.iconik_verification import IconikAssetReference

        return IconikAssetReference(
            asset_id=self.asset_id,
            file_set_id=self.file_set_id,
            file_id=self.file_id,
            format_id=self.format_id,
            storage_id=self.storage_id,
            filename=self.iconik_filename,
            original_filename=self.iconik_filename,
            file_size=self.file_size,
            metadata_field_count=self.metadata_field_count,
            metadata_status=self.metadata_status,
            iconik_base_dir=self.iconik_base_dir,
            iconik_file_name=self.iconik_filename,
            iconik_s3_key=self.iconik_s3_key,
            storage_path=self.storage_path,
        )


@dataclass(frozen=True)
class AssetResolutionResult:
    local_filename: str
    asset_type: ReplacementAssetType
    status: GovernanceStatus
    target: ResolvedAssetTarget | None
    candidates: tuple[AssetResolutionCandidate, ...] = ()
    duplicate_count: int = 0
    message: str = ""
    resolution_method: str = ""
    resolved_asset_id: str = ""
    resolved_file_set_id: str = ""
    resolved_iconik_s3_key: str = ""
    governance_warnings: tuple[str, ...] = ()


class DuplicateAssetResolutionError(Exception):
    """Raised when more than one valid Iconik asset matches a replacement target."""

    def __init__(
        self,
        message: str,
        *,
        local_filename: str,
        candidates: list[AssetResolutionCandidate],
    ) -> None:
        super().__init__(message)
        self.local_filename = local_filename
        self.candidates = candidates


class AssetResolutionService:
    def __init__(self, iconik: IconikVerificationService) -> None:
        self._iconik = iconik

    def resolve_batch(
        self,
        targets: list[ReplacementTarget],
        *,
        catalogue: CatalogueDefinition | None = None,
        known_asset_ids: dict[str, str] | None = None,
        strict_catalogue_path: bool = False,
    ) -> list[AssetResolutionResult]:
        results: list[AssetResolutionResult] = []
        for target in targets:
            known_id = (known_asset_ids or {}).get(target.iconik_filename, "").strip()
            result = self.resolve_target(
                local_path=target.local_path,
                expected_filename=target.iconik_filename,
                asset_type=target.asset_type,
                catalogue_s3_key=target.s3_key if catalogue else "",
                known_asset_id=known_id,
                strict_catalogue_path=strict_catalogue_path,
            )
            results.append(result)
            if result.status == GovernanceStatus.DUPLICATE:
                self._append_duplicate_report(result)
        return results

    def resolve_target(
        self,
        *,
        local_path: Path,
        expected_filename: str,
        asset_type: ReplacementAssetType,
        catalogue_s3_key: str = "",
        known_asset_id: str = "",
        strict_catalogue_path: bool = False,
    ) -> AssetResolutionResult:
        filename = expected_filename.strip()
        if not filename:
            return self._failure(
                local_filename=local_path.name,
                asset_type=asset_type,
                status=GovernanceStatus.NOT_FOUND,
                message="Expected filename is empty",
            )

        if known_asset_id:
            result = self._resolve_by_asset_id(
                asset_id=known_asset_id,
                local_path=local_path,
                expected_filename=filename,
                asset_type=asset_type,
                catalogue_s3_key=catalogue_s3_key,
                strict_catalogue_path=strict_catalogue_path,
            )
            if result.status == GovernanceStatus.VERIFIED:
                return result

        return self._resolve_by_exact_title(
            local_path=local_path,
            expected_filename=filename,
            asset_type=asset_type,
            catalogue_s3_key=catalogue_s3_key,
            strict_catalogue_path=strict_catalogue_path,
        )

    def _resolve_by_asset_id(
        self,
        *,
        asset_id: str,
        local_path: Path,
        expected_filename: str,
        asset_type: ReplacementAssetType,
        catalogue_s3_key: str,
        strict_catalogue_path: bool,
    ) -> AssetResolutionResult:
        try:
            asset_doc = self._iconik.get_asset(asset_id)
        except Exception as exc:
            logger.warning("Asset ID lookup failed for %s: %s", asset_id, exc)
            return self._failure(
                local_filename=expected_filename,
                asset_type=asset_type,
                status=GovernanceStatus.NOT_FOUND,
                message=f"Known asset_id not found: {asset_id}",
            )

        title = str(asset_doc.get("title") or asset_doc.get("name") or "").strip()
        return self._build_verified_from_asset_id(
            asset_id=asset_id,
            local_path=local_path,
            expected_filename=expected_filename,
            asset_type=asset_type,
            catalogue_s3_key=catalogue_s3_key,
            strict_catalogue_path=strict_catalogue_path,
            resolution_method=RESOLUTION_BY_ASSET_ID,
            asset_title=title,
        )

    def _resolve_by_exact_title(
        self,
        *,
        local_path: Path,
        expected_filename: str,
        asset_type: ReplacementAssetType,
        catalogue_s3_key: str,
        strict_catalogue_path: bool,
    ) -> AssetResolutionResult:
        try:
            hits = self._iconik.search_exact_title(expected_filename)
        except Exception as exc:
            logger.exception("Exact title search failed for %s", expected_filename)
            return self._failure(
                local_filename=expected_filename,
                asset_type=asset_type,
                status=GovernanceStatus.NOT_FOUND,
                message=f"Iconik search failed: {exc}",
            )

        valid: list[tuple[str, ResolvedAssetTarget, AssetResolutionCandidate]] = []
        for hit in hits:
            asset_id = str(hit.get("id") or hit.get("asset_id") or "")
            if not asset_id:
                continue
            validated = self._validate_candidate(
                asset_id=asset_id,
                hit=hit,
                local_path=local_path,
                expected_filename=expected_filename,
                asset_type=asset_type,
                catalogue_s3_key=catalogue_s3_key,
                strict_catalogue_path=strict_catalogue_path,
            )
            if validated is None:
                continue
            target, candidate = validated
            valid.append((asset_id, target, candidate))

        if not valid:
            result = self._failure(
                local_filename=expected_filename,
                asset_type=asset_type,
                status=GovernanceStatus.NOT_FOUND,
                message=f"No valid Iconik asset found for {expected_filename!r}",
            )
            self._emit_not_found_diagnostics(expected_filename, asset_type)
            return result

        if len(valid) > 1:
            candidates = tuple(item[2] for item in valid)
            return AssetResolutionResult(
                local_filename=expected_filename,
                asset_type=asset_type,
                status=GovernanceStatus.DUPLICATE,
                target=None,
                candidates=candidates,
                duplicate_count=len(candidates),
                message=(
                    f"Ambiguous resolution: {len(candidates)} assets match "
                    f"{expected_filename!r}"
                ),
                resolution_method=RESOLUTION_BY_EXACT_TITLE,
            )

        _, target, _ = valid[0]
        return AssetResolutionResult(
            local_filename=expected_filename,
            asset_type=asset_type,
            status=GovernanceStatus.VERIFIED,
            target=target,
            candidates=(),
            duplicate_count=0,
            message="Asset resolution verified",
            resolution_method=target.resolution_method,
            resolved_asset_id=target.asset_id,
            resolved_file_set_id=target.file_set_id,
            resolved_iconik_s3_key=target.iconik_s3_key,
            governance_warnings=target.governance_warnings,
        )

    @staticmethod
    def _file_set_matches_filename(file_set_name: str, expected_filename: str) -> bool:
        return file_set_name.strip().lower() == expected_filename.strip().lower()

    @staticmethod
    def _title_matches_filename(asset_title: str, expected_filename: str) -> bool:
        return asset_title.strip().lower() == expected_filename.strip().lower()

    @staticmethod
    def _governance_warnings(asset_title: str, file_set_name: str) -> tuple[str, ...]:
        if asset_title.strip() != file_set_name.strip():
            return (GOVERNANCE_WARNING_TITLE_FILENAME_MISMATCH,)
        return ()

    def _validate_candidate(
        self,
        *,
        asset_id: str,
        hit: dict[str, Any],
        local_path: Path,
        expected_filename: str,
        asset_type: ReplacementAssetType,
        catalogue_s3_key: str,
        strict_catalogue_path: bool,
    ) -> tuple[ResolvedAssetTarget, AssetResolutionCandidate] | None:
        title = str(hit.get("title") or hit.get("name") or "").strip()

        detected = detect_replacement_type(expected_filename)
        if detected != asset_type:
            return None

        details = self._iconik.resolve_file_details(asset_id)
        file_set_name = str(
            details.get("iconik_file_name") or details.get("original_filename") or ""
        )
        if not self._file_set_matches_filename(file_set_name, expected_filename):
            return None

        iconik_s3_key = str(details.get("iconik_s3_key") or "")
        if not iconik_s3_key:
            return None

        if strict_catalogue_path and catalogue_s3_key:
            if iconik_s3_key != catalogue_s3_key:
                return None

        storage_path = str(details.get("storage_path") or "")
        warnings = self._governance_warnings(title, file_set_name)
        metadata = self._iconik.fetch_metadata(asset_id)
        candidate = AssetResolutionCandidate(
            asset_id=asset_id,
            title=title,
            file_set_id=str(details.get("file_set_id") or ""),
            file_set_name=file_set_name,
            s3_key=iconik_s3_key,
            storage_path=storage_path,
        )
        target = ResolvedAssetTarget(
            asset_id=asset_id,
            file_set_id=str(details.get("file_set_id") or ""),
            file_id=str(details.get("file_id") or ""),
            iconik_filename=file_set_name,
            iconik_s3_key=iconik_s3_key,
            local_path=local_path,
            resolution_method=RESOLUTION_BY_EXACT_TITLE,
            governance_status=GovernanceStatus.VERIFIED,
            format_id=str(details.get("format_id") or ""),
            storage_id=str(details.get("storage_id") or ""),
            file_size=int(details.get("file_size") or 0),
            metadata_field_count=metadata.field_count,
            metadata_status=metadata.status,
            iconik_base_dir=str(details.get("iconik_base_dir") or ""),
            storage_path=storage_path,
            catalogue_s3_key=catalogue_s3_key,
            asset_title=title,
            governance_warnings=warnings,
        )
        return target, candidate

    def _build_verified_from_asset_id(
        self,
        *,
        asset_id: str,
        local_path: Path,
        expected_filename: str,
        asset_type: ReplacementAssetType,
        catalogue_s3_key: str,
        strict_catalogue_path: bool,
        resolution_method: str,
        asset_title: str = "",
    ) -> AssetResolutionResult:
        detected = detect_replacement_type(expected_filename)
        if detected != asset_type:
            return self._failure(
                local_filename=expected_filename,
                asset_type=asset_type,
                status=GovernanceStatus.TYPE_MISMATCH,
                message=f"Filename type does not match expected {asset_type.value}",
            )

        details = self._iconik.resolve_file_details(asset_id)
        file_set_name = str(details.get("iconik_file_name") or details.get("original_filename") or "")
        if file_set_name.lower() != expected_filename.lower():
            return self._failure(
                local_filename=expected_filename,
                asset_type=asset_type,
                status=GovernanceStatus.FILESET_MISMATCH,
                message=(
                    f"File set name {file_set_name!r} does not match "
                    f"expected {expected_filename!r}"
                ),
            )

        iconik_s3_key = str(details.get("iconik_s3_key") or "")
        if not iconik_s3_key:
            return self._failure(
                local_filename=expected_filename,
                asset_type=asset_type,
                status=GovernanceStatus.FILESET_MISMATCH,
                message="Iconik asset has no resolvable S3 key",
            )

        if strict_catalogue_path and catalogue_s3_key and iconik_s3_key != catalogue_s3_key:
            return self._failure(
                local_filename=expected_filename,
                asset_type=asset_type,
                status=GovernanceStatus.PATH_MISMATCH,
                message=(
                    f"Iconik S3 key {iconik_s3_key} does not match "
                    f"catalogue key {catalogue_s3_key}"
                ),
            )

        storage_path = str(details.get("storage_path") or "")
        resolved_title = asset_title.strip()
        if not resolved_title:
            try:
                asset_doc = self._iconik.get_asset(asset_id)
                resolved_title = str(
                    asset_doc.get("title") or asset_doc.get("name") or ""
                ).strip()
            except Exception:
                resolved_title = ""

        warnings = self._governance_warnings(resolved_title, file_set_name)
        metadata = self._iconik.fetch_metadata(asset_id)
        target = ResolvedAssetTarget(
            asset_id=asset_id,
            file_set_id=str(details.get("file_set_id") or ""),
            file_id=str(details.get("file_id") or ""),
            iconik_filename=file_set_name,
            iconik_s3_key=iconik_s3_key,
            local_path=local_path,
            resolution_method=resolution_method,
            governance_status=GovernanceStatus.VERIFIED,
            format_id=str(details.get("format_id") or ""),
            storage_id=str(details.get("storage_id") or ""),
            file_size=int(details.get("file_size") or 0),
            metadata_field_count=metadata.field_count,
            metadata_status=metadata.status,
            iconik_base_dir=str(details.get("iconik_base_dir") or ""),
            storage_path=storage_path,
            catalogue_s3_key=catalogue_s3_key,
            asset_title=resolved_title,
            governance_warnings=warnings,
        )
        return AssetResolutionResult(
            local_filename=expected_filename,
            asset_type=asset_type,
            status=GovernanceStatus.VERIFIED,
            target=target,
            candidates=(),
            duplicate_count=0,
            message="Asset resolution verified",
            resolution_method=resolution_method,
            resolved_asset_id=target.asset_id,
            resolved_file_set_id=target.file_set_id,
            resolved_iconik_s3_key=target.iconik_s3_key,
            governance_warnings=warnings,
        )

    @staticmethod
    def _failure(
        *,
        local_filename: str,
        asset_type: ReplacementAssetType,
        status: GovernanceStatus,
        message: str,
    ) -> AssetResolutionResult:
        return AssetResolutionResult(
            local_filename=local_filename,
            asset_type=asset_type,
            status=status,
            target=None,
            candidates=(),
            duplicate_count=0,
            message=message,
            resolution_method="",
        )

    def _append_duplicate_report(self, result: AssetResolutionResult) -> Path:
        path = REPORTS_DIR / "duplicate_assets.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists() or path.stat().st_size == 0
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=DUPLICATE_CSV_COLUMNS)
            if write_header:
                writer.writeheader()
            for candidate in result.candidates:
                writer.writerow(
                    {
                        "timestamp": timestamp,
                        "local_filename": result.local_filename,
                        "asset_type": result.asset_type.value,
                        "query_filename": result.local_filename,
                        "candidate_asset_id": candidate.asset_id,
                        "candidate_title": candidate.title,
                        "candidate_file_set_id": candidate.file_set_id,
                        "candidate_file_set_name": candidate.file_set_name,
                        "candidate_s3_key": candidate.s3_key,
                        "candidate_storage_path": candidate.storage_path,
                        "duplicate_count": result.duplicate_count,
                        "governance_status": result.status.value,
                    }
                )
        logger.info("Appended duplicate asset report: %s", path)
        return path

    @staticmethod
    def iconik_s3_key(base_dir: str, name: str) -> str:
        return S3Service.iconik_key_from_file_set(base_dir, name)

    def _emit_not_found_diagnostics(
        self,
        expected_filename: str,
        asset_type: ReplacementAssetType,
    ) -> None:
        """TEMPORARY: trace NOT_FOUND without altering resolution rules."""
        try:
            from services.asset_resolution_diagnostics import (
                diagnose_resolution,
                log_diagnostic_report,
                write_diagnostic_report,
            )

            report = diagnose_resolution(
                self._iconik,
                expected_filename=expected_filename,
                asset_type=asset_type,
            )
            log_diagnostic_report(report)
            write_diagnostic_report(report)
        except Exception as exc:
            logger.warning("Resolution diagnostics failed: %s", exc)
