"""Tests for scan summary warning finalization."""

from __future__ import annotations

import unittest

from models.housekeeping import AssetScanSummary


class AssetScanSummaryTests(unittest.TestCase):
    def test_finalize_page_limit_warning(self) -> None:
        summary = AssetScanSummary(terminated_by_page_limit=True)
        summary.finalize_warnings()
        self.assertTrue(
            any("page limit" in w.lower() for w in summary.warnings),
        )

    def test_finalize_count_mismatch_warning(self) -> None:
        summary = AssetScanSummary(
            assets_reported_by_iconik=100,
            assets_scanned=95,
        )
        summary.finalize_warnings()
        self.assertTrue(
            any("Asset count mismatch" in w for w in summary.warnings),
        )


if __name__ == "__main__":
    unittest.main()
