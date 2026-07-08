"""Iconik housekeeping audit models — read-only library diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssetScanSummary:
    """Pagination integrity metrics for a full-library Iconik search."""

    pages_requested: int = 0
    pages_received: int = 0
    assets_reported_by_iconik: int = 0
    assets_scanned: int = 0
    duplicate_asset_ids_filtered: int = 0
    warnings: list[str] = field(default_factory=list)
    terminated_by_page_limit: bool = False
    cancelled: bool = False
    scan_started: str = ""
    scan_completed: str = ""
    scan_duration_seconds: float = 0.0
    first_asset_id: str = ""
    last_asset_id: str = ""
    pagination_method: str = ""

    def finalize_warnings(self) -> None:
        if self.terminated_by_page_limit:
            msg = "Audit terminated due to page limit before full library scan completed."
            if msg not in self.warnings:
                self.warnings.append(msg)
        if (
            self.assets_reported_by_iconik > 0
            and self.assets_scanned != self.assets_reported_by_iconik
        ):
            msg = (
                f"Asset count mismatch: Iconik reported {self.assets_reported_by_iconik} "
                f"but {self.assets_scanned} unique assets were scanned."
            )
            if msg not in self.warnings:
                self.warnings.append(msg)


@dataclass
class AssetPageProgress:
    page: int
    returned: int
    running_total: int
    duplicates_filtered: int
    pages_received: int
    assets_reported_by_iconik: int


@dataclass
class AssetScanResult:
    assets: list[Any] = field(default_factory=list)
    summary: AssetScanSummary = field(default_factory=AssetScanSummary)


@dataclass
class HousekeepingAssetRecord:
    asset_id: str
    title: str
    status: str
    file_set_id: str
    file_set_name: str
    storage_id: str
    storage_key: str
    date_created: str
    date_modified: str
    metadata_status: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "asset_id": self.asset_id,
            "title": self.title,
            "status": self.status,
            "file_set_id": self.file_set_id,
            "file_set_name": self.file_set_name,
            "storage_id": self.storage_id,
            "storage_key": self.storage_key,
            "date_created": self.date_created,
            "date_modified": self.date_modified,
            "metadata_status": self.metadata_status,
        }


@dataclass
class DuplicateGroup:
    """Assets sharing the same grouping key (filename, storage key, or title)."""

    group_key: str
    count: int
    asset_ids: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)

    def as_summary_dict(self) -> dict[str, str | int]:
        return {
            "group_key": self.group_key,
            "duplicate_count": self.count,
            "asset_ids": ", ".join(self.asset_ids),
            "titles": " | ".join(self.titles),
        }


@dataclass
class OrphanAssetRecord:
    asset_id: str
    title: str
    status: str
    file_set_id: str
    file_set_name: str
    storage_id: str
    storage_key: str
    date_created: str
    date_modified: str
    metadata_status: str
    orphan_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, str]:
        return {
            "asset_id": self.asset_id,
            "title": self.title,
            "status": self.status,
            "file_set_id": self.file_set_id,
            "file_set_name": self.file_set_name,
            "storage_id": self.storage_id,
            "storage_key": self.storage_key,
            "date_created": self.date_created,
            "date_modified": self.date_modified,
            "metadata_status": self.metadata_status,
            "orphan_reasons": ", ".join(self.orphan_reasons),
        }


@dataclass
class HousekeepingProgress:
    phase: str
    current: int
    total: int
    message: str = ""
    pages_scanned: int = 0
    duplicates_filtered: int = 0
    assets_reported: int = 0


@dataclass
class HousekeepingAuditResult:
    total_scanned: int = 0
    duplicate_filename_groups: list[DuplicateGroup] = field(default_factory=list)
    duplicate_storage_groups: list[DuplicateGroup] = field(default_factory=list)
    duplicate_title_groups: list[DuplicateGroup] = field(default_factory=list)
    orphan_assets: list[OrphanAssetRecord] = field(default_factory=list)
    all_records: list[HousekeepingAssetRecord] = field(default_factory=list)
    scan_summary: AssetScanSummary | None = None
    warnings: list[str] = field(default_factory=list)
    cancelled: bool = False
    error: str = ""

    @property
    def duplicate_filename_count(self) -> int:
        return sum(g.count for g in self.duplicate_filename_groups)

    @property
    def duplicate_storage_count(self) -> int:
        return sum(g.count for g in self.duplicate_storage_groups)

    @property
    def duplicate_title_count(self) -> int:
        return sum(g.count for g in self.duplicate_title_groups)

    @property
    def orphan_count(self) -> int:
        return len(self.orphan_assets)
