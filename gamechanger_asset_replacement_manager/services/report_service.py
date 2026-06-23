"""Audit report generation (CSV and Excel)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from models.upload import AuditRecord, ReplacementVerificationRecord
from services.paths import REPORTS_DIR

logger = logging.getLogger(__name__)

VERIFICATION_REPORT_COLUMNS = [
    "filename",
    "type",
    "asset_id_before",
    "asset_id_after",
    "file_set_before",
    "file_set_after",
    "file_id_before",
    "file_id_after",
    "format_id_before",
    "format_id_after",
    "storage_id_before",
    "storage_id_after",
    "metadata_count_before",
    "metadata_count_after",
    "metadata_status",
    "metadata_status_after",
    "replacement_method",
    "resolution_method",
    "duplicate_count",
    "resolved_asset_id",
    "resolved_file_set_id",
    "resolved_iconik_s3_key",
    "governance_status",
    "resolved_asset_title",
    "resolved_file_set_name",
    "governance_warnings",
    "local_cfx_filename",
    "local_cfx_size",
    "local_cfx_md5",
    "iconik_base_dir_before",
    "iconik_file_name_before",
    "iconik_storage_path_before",
    "catalogue_upload_key",
    "iconik_storage_key",
    "remote_object_size",
    "remote_object_md5",
    "remote_catalogue_size",
    "remote_catalogue_md5",
    "iconik_storage_key_after",
    "iconik_storage_path_after",
    "verify_reached_iconik_object",
    "verify_size_match",
    "verify_hash_match",
    "verify_fileset_points_elsewhere",
    "cfx_diagnosis",
    "status",
    "message",
    "uploaded",
    "timestamp",
]

REPORT_COLUMNS = [
    "filename",
    "clean_filename",
    "catalogue",
    "s3_exists",
    "old_size",
    "new_size",
    "uploaded",
    "status",
    "governance_status",
    "resolution_method",
    "resolved_asset_id",
    "resolved_file_set_id",
    "resolved_iconik_s3_key",
    "metadata_status",
    "governance_warnings",
    "timestamp",
]


class ReportService:
    def __init__(self, reports_dir: Path | None = None) -> None:
        self._dir = reports_dir or REPORTS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def write_reports(
        self,
        records: list[AuditRecord],
        *,
        prefix: str = "replacement_report",
    ) -> tuple[Path, Path]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_path = self._dir / f"{prefix}_{stamp}.csv"
        xlsx_path = self._dir / f"{prefix}_{stamp}.xlsx"

        # Also write canonical names for latest run
        csv_latest = self._dir / "replacement_report.csv"
        xlsx_latest = self._dir / "replacement_report.xlsx"

        rows = [r.as_dict() for r in records]
        df = pd.DataFrame(rows, columns=REPORT_COLUMNS)

        df.to_csv(csv_path, index=False)
        df.to_csv(csv_latest, index=False)
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        df.to_excel(xlsx_latest, index=False, engine="openpyxl")

        logger.info("Wrote audit reports: %s, %s", csv_path, xlsx_path)
        return csv_path, xlsx_path

    def write_verification_reports(
        self,
        records: list[ReplacementVerificationRecord],
        *,
        prefix: str = "replacement_audit",
    ) -> tuple[Path, Path]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_path = self._dir / f"{prefix}_{stamp}.csv"
        xlsx_path = self._dir / f"{prefix}_{stamp}.xlsx"
        csv_latest = self._dir / "replacement_audit.csv"
        xlsx_latest = self._dir / "replacement_audit.xlsx"

        rows = [r.as_dict() for r in records]
        df = pd.DataFrame(rows, columns=VERIFICATION_REPORT_COLUMNS)

        df.to_csv(csv_path, index=False)
        df.to_csv(csv_latest, index=False)
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        df.to_excel(xlsx_latest, index=False, engine="openpyxl")

        logger.info("Wrote verification audit: %s, %s", csv_path, xlsx_path)
        return csv_path, xlsx_path

    def write_failure_reports(
        self,
        records: list[ReplacementVerificationRecord],
        *,
        prefix: str = "replacement_failure",
    ) -> tuple[Path, Path]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_path = self._dir / f"{prefix}_{stamp}.csv"
        xlsx_path = self._dir / f"{prefix}_{stamp}.xlsx"
        csv_latest = self._dir / "replacement_failure.csv"
        xlsx_latest = self._dir / "replacement_failure.xlsx"

        rows = [r.as_dict() for r in records]
        df = pd.DataFrame(rows, columns=VERIFICATION_REPORT_COLUMNS)

        df.to_csv(csv_path, index=False)
        df.to_csv(csv_latest, index=False)
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        df.to_excel(xlsx_latest, index=False, engine="openpyxl")

        logger.info("Wrote failure reports: %s, %s", csv_path, xlsx_path)
        return csv_path, xlsx_path
