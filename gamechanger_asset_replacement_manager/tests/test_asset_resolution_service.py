"""Unit tests for governed asset resolution (no live Iconik calls)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from services.asset_resolution_service import (
    AssetResolutionService,
    GOVERNANCE_WARNING_TITLE_FILENAME_MISMATCH,
    GovernanceStatus,
    RESOLUTION_BY_EXACT_TITLE,
)
from services.iconik_verification import MetadataLookupResult
from services.replacement_variant import ReplacementAssetType


def _available_metadata() -> MetadataLookupResult:
    return MetadataLookupResult(status="AVAILABLE", field_count=5)


class AssetResolutionServiceTests(unittest.TestCase):
    def test_duplicate_candidates_block_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "CHE_EVE_20060208_G_01_ENGP.mp4"
            local.write_bytes(b"x")

            iconik = MagicMock()
            iconik.search_exact_title.return_value = [
                {"id": "asset-a", "title": "CHE_EVE_20060208_G_01_ENGP.mp4"},
                {"id": "asset-b", "title": "CHE_EVE_20060208_G_01_ENGP.mp4"},
            ]
            iconik.resolve_file_details.side_effect = [
                {
                    "file_set_id": "fs-a",
                    "file_id": "f-a",
                    "format_id": "fmt",
                    "storage_id": "stor",
                    "file_size": 1,
                    "iconik_base_dir": "dir/a",
                    "iconik_file_name": "CHE_EVE_20060208_G_01_ENGP.mp4",
                    "original_filename": "CHE_EVE_20060208_G_01_ENGP.mp4",
                    "iconik_s3_key": "dir/a/CHE_EVE_20060208_G_01_ENGP.mp4",
                    "storage_path": "",
                },
                {
                    "file_set_id": "fs-b",
                    "file_id": "f-b",
                    "format_id": "fmt",
                    "storage_id": "stor",
                    "file_size": 1,
                    "iconik_base_dir": "dir/b",
                    "iconik_file_name": "CHE_EVE_20060208_G_01_ENGP.mp4",
                    "original_filename": "CHE_EVE_20060208_G_01_ENGP.mp4",
                    "iconik_s3_key": "dir/b/CHE_EVE_20060208_G_01_ENGP.mp4",
                    "storage_path": "",
                },
            ]
            iconik.fetch_metadata.return_value = _available_metadata()

            service = AssetResolutionService(iconik)
            result = service.resolve_target(
                local_path=local,
                expected_filename=local.name,
                asset_type=ReplacementAssetType.ENGP,
            )

            self.assertEqual(result.status, GovernanceStatus.DUPLICATE)
            self.assertEqual(result.duplicate_count, 2)
            self.assertIsNone(result.target)

    def test_exact_title_single_match_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "CHE_EVE_20060208_G_01_ENGP.mp4"
            local.write_bytes(b"x")

            iconik = MagicMock()
            iconik.search_exact_title.return_value = [
                {"id": "asset-a", "title": "CHE_EVE_20060208_G_01_ENGP.mp4"},
            ]
            iconik.resolve_file_details.return_value = {
                "file_set_id": "fs-a",
                "file_id": "f-a",
                "format_id": "fmt",
                "storage_id": "stor",
                "file_size": 1,
                "iconik_base_dir": "dir/a",
                "iconik_file_name": "CHE_EVE_20060208_G_01_ENGP.mp4",
                "original_filename": "CHE_EVE_20060208_G_01_ENGP.mp4",
                "iconik_s3_key": "dir/a/CHE_EVE_20060208_G_01_ENGP.mp4",
                "storage_path": "",
            }
            iconik.fetch_metadata.return_value = _available_metadata()

            service = AssetResolutionService(iconik)
            result = service.resolve_target(
                local_path=local,
                expected_filename=local.name,
                asset_type=ReplacementAssetType.ENGP,
            )

            self.assertEqual(result.status, GovernanceStatus.VERIFIED)
            self.assertIsNotNone(result.target)
            assert result.target is not None
            self.assertEqual(result.target.asset_id, "asset-a")
            self.assertEqual(result.resolution_method, RESOLUTION_BY_EXACT_TITLE)

    def test_file_set_name_match_with_title_missing_extension(self) -> None:
        """AST_TOT-style assets: title omits .mp4 but file_set.name is authoritative."""
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "AST_TOT_19810822_G_03_ENGP.mp4"
            local.write_bytes(b"x")

            iconik = MagicMock()
            iconik.search_exact_title.return_value = [
                {"id": "43b686c6-49f4-11f1-a569-aac47ae32774", "title": "AST_TOT_19810822_G_03_ENGP"},
            ]
            iconik.resolve_file_details.return_value = {
                "file_set_id": "fs-tot",
                "file_id": "f-tot",
                "format_id": "fmt",
                "storage_id": "stor",
                "file_size": 1,
                "iconik_base_dir": "dir/tot",
                "iconik_file_name": "AST_TOT_19810822_G_03_ENGP.mp4",
                "original_filename": "AST_TOT_19810822_G_03_ENGP.mp4",
                "iconik_s3_key": "dir/tot/AST_TOT_19810822_G_03_ENGP.mp4",
                "storage_path": "",
            }
            iconik.fetch_metadata.return_value = _available_metadata()

            service = AssetResolutionService(iconik)
            result = service.resolve_target(
                local_path=local,
                expected_filename=local.name,
                asset_type=ReplacementAssetType.ENGP,
            )

            self.assertEqual(result.status, GovernanceStatus.VERIFIED)
            self.assertIsNotNone(result.target)
            assert result.target is not None
            self.assertEqual(result.target.asset_id, "43b686c6-49f4-11f1-a569-aac47ae32774")
            self.assertEqual(result.target.iconik_filename, "AST_TOT_19810822_G_03_ENGP.mp4")
            self.assertEqual(result.target.asset_title, "AST_TOT_19810822_G_03_ENGP")
            self.assertIn(GOVERNANCE_WARNING_TITLE_FILENAME_MISMATCH, result.governance_warnings)

    def test_known_asset_id_resolves_when_title_omits_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "AST_TOT_19810822_G_03_ENGP.mp4"
            local.write_bytes(b"x")

            iconik = MagicMock()
            iconik.get_asset.return_value = {
                "id": "43b686c6-49f4-11f1-a569-aac47ae32774",
                "title": "AST_TOT_19810822_G_03_ENGP",
            }
            iconik.resolve_file_details.return_value = {
                "file_set_id": "fs-tot",
                "file_id": "f-tot",
                "format_id": "fmt",
                "storage_id": "stor",
                "file_size": 1,
                "iconik_base_dir": "dir/tot",
                "iconik_file_name": "AST_TOT_19810822_G_03_ENGP.mp4",
                "original_filename": "AST_TOT_19810822_G_03_ENGP.mp4",
                "iconik_s3_key": "dir/tot/AST_TOT_19810822_G_03_ENGP.mp4",
                "storage_path": "",
            }
            iconik.fetch_metadata.return_value = _available_metadata()

            service = AssetResolutionService(iconik)
            result = service.resolve_target(
                local_path=local,
                expected_filename=local.name,
                asset_type=ReplacementAssetType.ENGP,
                known_asset_id="43b686c6-49f4-11f1-a569-aac47ae32774",
            )

            self.assertEqual(result.status, GovernanceStatus.VERIFIED)
            self.assertIn(GOVERNANCE_WARNING_TITLE_FILENAME_MISMATCH, result.governance_warnings)
            iconik.search_exact_title.assert_not_called()


if __name__ == "__main__":
    unittest.main()
