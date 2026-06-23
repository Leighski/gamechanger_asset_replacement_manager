"""Unit tests for Source Files bulk governance."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from models.discovery import DiscoveredFile, PreflightRow, PreflightStatus
from models.upload import UploadAction
from services.asset_resolution_service import (
    AssetResolutionResult,
    GovernanceStatus,
    ResolvedAssetTarget,
)
from services.bulk_governance_service import (
    all_replace_candidates_verified,
    apply_governance_results,
    build_governed_summary,
    build_governed_upload_jobs,
)
from services.replacement_variant import ReplacementAssetType


def _replace_row(clean_name: str) -> PreflightRow:
    path = Path(f"/tmp/{clean_name}")
    return PreflightRow(
        discovered=DiscoveredFile(
            path=path,
            original_filename=clean_name,
            clean_filename=clean_name,
            size_bytes=100,
        ),
        s3_exists=True,
        s3_size=90,
        size_mismatch=True,
        action=UploadAction.REPLACE.value,
        status=PreflightStatus.READY,
        status_message="Ready to replace",
        s3_key=f"ENGP/{clean_name}",
    )


class BulkGovernanceServiceTests(unittest.TestCase):
    def test_apply_governance_marks_verified_row(self) -> None:
        row = _replace_row("CHE_EVE_20060208_G_01_ENGP.mp4")
        resolution = AssetResolutionResult(
            local_filename=row.discovered.clean_filename,
            asset_type=ReplacementAssetType.ENGP,
            status=GovernanceStatus.VERIFIED,
            target=ResolvedAssetTarget(
                asset_id="asset-1",
                file_set_id="fs-1",
                file_id="file-1",
                iconik_filename=row.discovered.clean_filename,
                iconik_s3_key=f"dir/{row.discovered.clean_filename}",
                local_path=row.discovered.path,
                resolution_method="BY_EXACT_TITLE",
                metadata_status="AVAILABLE",
            ),
            resolution_method="BY_EXACT_TITLE",
            resolved_asset_id="asset-1",
            resolved_file_set_id="fs-1",
            resolved_iconik_s3_key=f"dir/{row.discovered.clean_filename}",
        )
        apply_governance_results([row], [resolution])
        self.assertEqual(row.governance_status, GovernanceStatus.VERIFIED.value)
        self.assertEqual(row.resolved_asset_id, "asset-1")

    def test_build_governed_upload_jobs_only_verified_replace(self) -> None:
        verified = _replace_row("CHE_EVE_20060208_G_01_ENGP.mp4")
        verified.governance_status = GovernanceStatus.VERIFIED.value
        blocked = _replace_row("AST_TOT_19810822_G_03_ENGP.mp4")
        blocked.governance_status = GovernanceStatus.NOT_FOUND.value
        jobs = build_governed_upload_jobs([verified, blocked])
        by_name = {j.clean_filename: j.action for j in jobs}
        self.assertEqual(by_name["CHE_EVE_20060208_G_01_ENGP.mp4"], UploadAction.REPLACE)
        self.assertEqual(by_name["AST_TOT_19810822_G_03_ENGP.mp4"], UploadAction.SKIP)

    def test_all_replace_candidates_verified(self) -> None:
        ok = _replace_row("CHE_EVE_20060208_G_01_ENGP.mp4")
        ok.governance_status = GovernanceStatus.VERIFIED.value
        bad = _replace_row("AST_TOT_19810822_G_03_ENGP.mp4")
        bad.governance_status = GovernanceStatus.DUPLICATE.value
        self.assertFalse(all_replace_candidates_verified([ok, bad]))
        self.assertTrue(all_replace_candidates_verified([ok]))


if __name__ == "__main__":
    unittest.main()
