"""Excel export for Iconik housekeeping audit results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from models.housekeeping import DuplicateGroup, HousekeepingAuditResult, OrphanAssetRecord
from services.paths import REPORTS_DIR

logger = logging.getLogger(__name__)

FILENAME_AUDIT = "duplicate_filename_audit.xlsx"
STORAGE_AUDIT = "duplicate_storage_audit.xlsx"
TITLE_AUDIT = "duplicate_title_audit.xlsx"
ORPHAN_AUDIT = "orphan_asset_audit.xlsx"
COMBINED_REPORT = "iconik_housekeeping_report.xlsx"

DUPLICATE_COLUMNS = ["group_key", "duplicate_count", "asset_ids", "titles"]
ORPHAN_COLUMNS = [
    "asset_id",
    "title",
    "status",
    "file_set_id",
    "file_set_name",
    "storage_id",
    "storage_key",
    "date_created",
    "date_modified",
    "metadata_status",
    "orphan_reasons",
]
ASSET_COLUMNS = [
    "asset_id",
    "title",
    "status",
    "file_set_id",
    "file_set_name",
    "storage_id",
    "storage_key",
    "date_created",
    "date_modified",
    "metadata_status",
]


class HousekeepingReportService:
    def __init__(self, reports_dir: Path | None = None) -> None:
        self._dir = reports_dir or REPORTS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _log_write_start(filename: str) -> None:
        logger.warning("[HOUSEKEEPING] writing %s", filename)

    @staticmethod
    def _log_write_done(filename: str, path: Path) -> None:
        logger.warning("[HOUSEKEEPING] wrote %s path=%s", filename, path)

    def write_reports(self, result: HousekeepingAuditResult) -> dict[str, Path]:
        """Write all housekeeping Excel reports. Audit-only — no Iconik mutations."""
        paths: dict[str, Path] = {}
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        paths["filename"] = self._write_duplicate_report(
            result.duplicate_filename_groups,
            FILENAME_AUDIT,
            stamp,
            warnings=result.warnings,
        )
        paths["storage"] = self._write_duplicate_report(
            result.duplicate_storage_groups,
            STORAGE_AUDIT,
            stamp,
            warnings=result.warnings,
        )
        paths["title"] = self._write_duplicate_report(
            result.duplicate_title_groups,
            TITLE_AUDIT,
            stamp,
            warnings=result.warnings,
        )
        paths["orphan"] = self._write_orphan_report(result.orphan_assets, stamp, warnings=result.warnings)
        paths["combined"] = self._write_combined_report(result, stamp)
        return paths

    def _write_duplicate_report(
        self,
        groups: list[DuplicateGroup],
        latest_name: str,
        stamp: str,
        *,
        warnings: list[str] | None = None,
    ) -> Path:
        self._log_write_start(latest_name)
        rows = [g.as_summary_dict() for g in groups]
        df = pd.DataFrame(rows, columns=DUPLICATE_COLUMNS)
        stamped = self._dir / f"{latest_name.replace('.xlsx', '')}_{stamp}.xlsx"
        latest = self._dir / latest_name
        warning_rows = pd.DataFrame({"warning": warnings or []})
        with pd.ExcelWriter(stamped, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Findings", index=False)
            if warnings:
                warning_rows.to_excel(writer, sheet_name="Warnings", index=False)
        with pd.ExcelWriter(latest, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Findings", index=False)
            if warnings:
                warning_rows.to_excel(writer, sheet_name="Warnings", index=False)
        self._log_write_done(latest_name, latest)
        return latest

    def _write_orphan_report(
        self,
        orphans: list[OrphanAssetRecord],
        stamp: str,
        *,
        warnings: list[str] | None = None,
    ) -> Path:
        self._log_write_start(ORPHAN_AUDIT)
        rows = [o.as_dict() for o in orphans]
        df = pd.DataFrame(rows, columns=ORPHAN_COLUMNS)
        stamped = self._dir / f"orphan_asset_audit_{stamp}.xlsx"
        latest = self._dir / ORPHAN_AUDIT
        warning_rows = pd.DataFrame({"warning": warnings or []})
        with pd.ExcelWriter(stamped, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Findings", index=False)
            if warnings:
                warning_rows.to_excel(writer, sheet_name="Warnings", index=False)
        with pd.ExcelWriter(latest, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Findings", index=False)
            if warnings:
                warning_rows.to_excel(writer, sheet_name="Warnings", index=False)
        self._log_write_done(ORPHAN_AUDIT, latest)
        return latest

    def _write_combined_report(self, result: HousekeepingAuditResult, stamp: str) -> Path:
        self._log_write_start(COMBINED_REPORT)
        stamped = self._dir / f"iconik_housekeeping_report_{stamp}.xlsx"
        latest = self._dir / COMBINED_REPORT
        scan = result.scan_summary
        summary_row = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_assets_scanned": result.total_scanned,
            "duplicate_filename_groups": len(result.duplicate_filename_groups),
            "duplicate_storage_groups": len(result.duplicate_storage_groups),
            "duplicate_title_groups": len(result.duplicate_title_groups),
            "orphan_assets": len(result.orphan_assets),
            "pages_requested": scan.pages_requested if scan else 0,
            "pages_received": scan.pages_received if scan else 0,
            "assets_reported_by_iconik": scan.assets_reported_by_iconik if scan else 0,
            "duplicate_asset_ids_filtered": scan.duplicate_asset_ids_filtered if scan else 0,
            "scan_started": scan.scan_started if scan else "",
            "scan_completed": scan.scan_completed if scan else "",
            "scan_duration_seconds": scan.scan_duration_seconds if scan else 0.0,
            "first_asset_id": scan.first_asset_id if scan else "",
            "last_asset_id": scan.last_asset_id if scan else "",
            "pagination_method": scan.pagination_method if scan else "",
            "warnings": "; ".join(result.warnings),
            "cancelled": result.cancelled,
            "error": result.error,
        }
        summary = pd.DataFrame([summary_row])
        all_assets = pd.DataFrame(
            [r.as_dict() for r in result.all_records],
            columns=ASSET_COLUMNS,
        )
        warnings_df = pd.DataFrame({"warning": result.warnings})
        with pd.ExcelWriter(latest, engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="Summary", index=False)
            if not warnings_df.empty:
                warnings_df.to_excel(writer, sheet_name="Warnings", index=False)
            all_assets.to_excel(writer, sheet_name="All Assets", index=False)
            pd.DataFrame(
                [g.as_summary_dict() for g in result.duplicate_filename_groups],
                columns=DUPLICATE_COLUMNS,
            ).to_excel(writer, sheet_name="Duplicate Filenames", index=False)
            pd.DataFrame(
                [g.as_summary_dict() for g in result.duplicate_storage_groups],
                columns=DUPLICATE_COLUMNS,
            ).to_excel(writer, sheet_name="Duplicate Storage", index=False)
            pd.DataFrame(
                [g.as_summary_dict() for g in result.duplicate_title_groups],
                columns=DUPLICATE_COLUMNS,
            ).to_excel(writer, sheet_name="Duplicate Titles", index=False)
            pd.DataFrame(
                [o.as_dict() for o in result.orphan_assets],
                columns=ORPHAN_COLUMNS,
            ).to_excel(writer, sheet_name="Orphan Assets", index=False)
        with pd.ExcelWriter(stamped, engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="Summary", index=False)
            if not warnings_df.empty:
                warnings_df.to_excel(writer, sheet_name="Warnings", index=False)
            all_assets.to_excel(writer, sheet_name="All Assets", index=False)
        self._log_write_done(COMBINED_REPORT, latest)
        return latest
