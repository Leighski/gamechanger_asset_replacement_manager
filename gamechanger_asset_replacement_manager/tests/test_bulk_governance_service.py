"""Unit tests for Source Files bulk governance (Phase 2 governance-first)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.discovery import DiscoveredFile, PreflightRow, PreflightStatus, S3Status
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
    is_ready_to_replace,
    preserve_catalogue_s3_preflight,
    recompute_row_readiness,
    resolve_governance_for_preflight,
    validate_s3_against_resolved_keys,
    write_governance_verification_report,
)
from services.replacement_variant import ReplacementAssetType
from services.s3_service import S3ObjectInfo


def _media_row(
    clean_name: str,
    *,
    s3_exists: bool = False,
    action: str = UploadAction.SKIP.value,
    status: PreflightStatus = PreflightStatus.SKIP,
) -> PreflightRow:
    path = Path(f"/tmp/{clean_name}")
    return PreflightRow(
        discovered=DiscoveredFile(
            path=path,
            original_filename=clean_name,
            clean_filename=clean_name,
            size_bytes=100,
        ),
        s3_exists=s3_exists,
        s3_size=90 if s3_exists else None,
        size_mismatch=False,
        action=action,
        status=status,
        status_message="Not in catalogue S3 — pending governance resolution",
        s3_key=f"ENGP_CFX/{clean_name}",
        s3_status=S3Status.EXISTS.value if s3_exists else S3Status.MISSING.value,
        catalogue_s3_exists=s3_exists,
        catalogue_s3_status=S3Status.EXISTS.value if s3_exists else S3Status.MISSING.value,
    )


def _verified_resolution(clean_name: str, *, iconik_key: str) -> AssetResolutionResult:
    path = Path(f"/tmp/{clean_name}")
    return AssetResolutionResult(
        local_filename=clean_name,
        asset_type=ReplacementAssetType.ENGP,
        status=GovernanceStatus.VERIFIED,
        target=ResolvedAssetTarget(
            asset_id="asset-che",
            file_set_id="fs-che",
            file_id="file-che",
            iconik_filename=clean_name,
            iconik_s3_key=iconik_key,
            local_path=path,
            resolution_method="BY_EXACT_TITLE",
            metadata_status="AVAILABLE",
        ),
        resolution_method="BY_EXACT_TITLE",
        resolved_asset_id="asset-che",
        resolved_file_set_id="fs-che",
        resolved_iconik_s3_key=iconik_key,
    )


class BulkGovernanceServiceTests(unittest.TestCase):
    def test_apply_governance_marks_verified_row(self) -> None:
        row = _media_row("CHE_EVE_20060208_G_01_ENGP.mp4", s3_exists=True, action=UploadAction.REPLACE.value)
        resolution = _verified_resolution(
            "CHE_EVE_20060208_G_01_ENGP.mp4",
            iconik_key="ENGLAND/ENGP/CHE_EVE_20060208_G_01_ENGP.mp4",
        )
        apply_governance_results([row], [resolution])
        self.assertEqual(row.governance_status, GovernanceStatus.VERIFIED.value)
        self.assertEqual(row.resolved_asset_id, "asset-che")

    def test_governance_runs_for_catalogue_s3_missing_skip_row(self) -> None:
        """CHE_TOT scenario: governance must run even when catalogue S3 is missing."""
        row = _media_row("CHE_TOT_20170422_G_02_ENGP.mp4")
        resolution = _verified_resolution(
            "CHE_TOT_20170422_G_02_ENGP.mp4",
            iconik_key="ENGLAND/ENGP/CHE_TOT_20170422_G_02_ENGP.mp4",
        )
        apply_governance_results([row], [resolution])
        self.assertEqual(row.governance_status, GovernanceStatus.VERIFIED.value)
        self.assertEqual(row.catalogue_s3_status, S3Status.MISSING.value)
        self.assertFalse(row.catalogue_s3_exists)

    def test_recompute_readiness_verified_with_resolved_key_despite_s3_missing(self) -> None:
        row = _media_row("CHE_TOT_20170422_G_02_ENGP.mp4")
        row.governance_status = GovernanceStatus.VERIFIED.value
        row.resolved_iconik_s3_key = "ENGLAND/ENGP/CHE_TOT_20170422_G_02_ENGP.mp4"
        row.s3_exists = False
        row.s3_status = S3Status.MISSING.value
        recompute_row_readiness(row)
        self.assertTrue(is_ready_to_replace(row))
        self.assertEqual(row.action, UploadAction.REPLACE.value)

    def test_build_governed_upload_jobs_only_verified_with_resolved_key(self) -> None:
        verified = _media_row("CHE_EVE_20060208_G_01_ENGP.mp4", s3_exists=True)
        verified.governance_status = GovernanceStatus.VERIFIED.value
        verified.resolved_iconik_s3_key = "ENGLAND/ENGP/CHE_EVE_20060208_G_01_ENGP.mp4"
        blocked = _media_row("AST_TOT_19810822_G_03_ENGP.mp4")
        blocked.governance_status = GovernanceStatus.NOT_FOUND.value
        jobs = build_governed_upload_jobs([verified, blocked])
        by_name = {j.clean_filename: j.action for j in jobs}
        self.assertEqual(by_name["CHE_EVE_20060208_G_01_ENGP.mp4"], UploadAction.REPLACE)
        self.assertEqual(by_name["AST_TOT_19810822_G_03_ENGP.mp4"], UploadAction.SKIP)

    def test_all_replace_candidates_verified(self) -> None:
        ok = _media_row("CHE_EVE_20060208_G_01_ENGP.mp4")
        ok.governance_status = GovernanceStatus.VERIFIED.value
        ok.resolved_iconik_s3_key = "ENGLAND/ENGP/CHE_EVE_20060208_G_01_ENGP.mp4"
        ok.action = UploadAction.REPLACE.value
        bad = _media_row("AST_TOT_19810822_G_03_ENGP.mp4")
        bad.governance_status = GovernanceStatus.DUPLICATE.value
        bad.resolved_iconik_s3_key = "ENGLAND/ENGP/AST_TOT_19810822_G_03_ENGP.mp4"
        bad.action = UploadAction.REPLACE.value
        self.assertFalse(all_replace_candidates_verified([ok, bad]))
        self.assertTrue(all_replace_candidates_verified([ok]))

    def test_validate_s3_against_resolved_keys_independent_of_governance(self) -> None:
        row = _media_row("CHE_TOT_20170422_G_02_ENGP.mp4")
        row.governance_status = GovernanceStatus.VERIFIED.value
        row.resolved_iconik_s3_key = "ENGLAND/ENGP/CHE_TOT_20170422_G_02_ENGP.mp4"
        preserve_catalogue_s3_preflight([row])

        s3 = MagicMock()
        catalogue = MagicMock()
        catalogue.location = MagicMock()
        s3.head_object.return_value = S3ObjectInfo(exists=False, size=None, etag=None)

        validate_s3_against_resolved_keys([row], s3, catalogue)
        self.assertEqual(row.governance_status, GovernanceStatus.VERIFIED.value)
        self.assertFalse(row.s3_exists)
        self.assertEqual(row.s3_status, S3Status.MISSING.value)
        self.assertEqual(row.catalogue_s3_status, S3Status.MISSING.value)

    def test_write_governance_verification_report(self) -> None:
        row = _media_row("CHE_TOT_20170422_G_02_ENGP.mp4")
        row.governance_status = GovernanceStatus.VERIFIED.value
        row.resolved_asset_id = "asset-che"
        row.resolved_file_set_id = "fs-che"
        row.resolved_iconik_s3_key = "ENGLAND/ENGP/CHE_TOT_20170422_G_02_ENGP.mp4"
        row.resolution_method = "BY_EXACT_TITLE"
        row.s3_exists = False
        row.s3_status = S3Status.MISSING.value

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "governance_phase2_verification.json"
            with patch(
                "services.bulk_governance_service.GOVERNANCE_VERIFICATION_REPORT",
                report_path,
            ):
                write_governance_verification_report([row])
            data = json.loads(report_path.read_text(encoding="utf-8"))
            record = data["files"][0]
            self.assertEqual(record["filename"], "CHE_TOT_20170422_G_02_ENGP.mp4")
            self.assertEqual(record["governance_status"], "VERIFIED")
            self.assertFalse(record["s3_exists"])

    def test_resolve_governance_includes_skip_preflight_rows(self) -> None:
        row = _media_row("CHE_TOT_20170422_G_02_ENGP.mp4")
        iconik = MagicMock()
        iconik.configured.return_value = True
        catalogue = MagicMock()

        with patch(
            "services.bulk_governance_service.AssetResolutionService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.resolve_batch.return_value = [
                _verified_resolution(
                    "CHE_TOT_20170422_G_02_ENGP.mp4",
                    iconik_key="ENGLAND/ENGP/CHE_TOT_20170422_G_02_ENGP.mp4",
                )
            ]
            results = resolve_governance_for_preflight(
                [row],
                catalogue=catalogue,
                iconik=iconik,
            )

        self.assertEqual(len(results), 1)
        mock_service.resolve_batch.assert_called_once()
        self.assertEqual(results[0].status, GovernanceStatus.VERIFIED)


    def test_compute_governance_stats(self) -> None:
        verified = _media_row("CHE_EVE_20060208_G_01_ENGP.mp4")
        verified.governance_status = GovernanceStatus.VERIFIED.value
        verified.resolved_iconik_s3_key = "ENGLAND/ENGP/CHE_EVE_20060208_G_01_ENGP.mp4"
        verified.s3_status = S3Status.EXISTS.value

        missing = _media_row("CHE_TOT_20170422_G_02_ENGP.mp4")
        missing.governance_status = GovernanceStatus.VERIFIED.value
        missing.resolved_iconik_s3_key = "ENGLAND/ENGP/CHE_TOT_20170422_G_02_ENGP.mp4"
        missing.s3_status = S3Status.MISSING.value

        not_found = _media_row("AST_TOT_19810822_G_03_ENGP.mp4")
        not_found.governance_status = GovernanceStatus.NOT_FOUND.value

        duplicate = _media_row("DUP_TOT_19810822_G_03_ENGP.mp4")
        duplicate.governance_status = GovernanceStatus.DUPLICATE.value

        error = _media_row("BAD_TOT_19810822_G_03_ENGP.mp4")
        error.governance_status = GovernanceStatus.TYPE_MISMATCH.value

        from services.bulk_governance_service import compute_governance_stats

        stats = compute_governance_stats([verified, missing, not_found, duplicate, error])
        self.assertEqual(stats.verified, 2)
        self.assertEqual(stats.not_found, 1)
        self.assertEqual(stats.duplicate, 1)
        self.assertEqual(stats.errors, 1)
        self.assertEqual(stats.s3_missing, 1)
        self.assertEqual(stats.ready_to_replace, 2)


if __name__ == "__main__":
    unittest.main()
