"""Unit tests for Iconik housekeeping audit logic."""

from __future__ import annotations

import unittest

from models.housekeeping import HousekeepingAssetRecord
from services.housekeeping_service import _find_duplicate_groups, _find_orphans


def _record(
    asset_id: str,
    *,
    title: str = "",
    file_set_name: str = "",
    storage_key: str = "",
    file_set_id: str = "fs-1",
    status: str = "ACTIVE",
    metadata_status: str = "AVAILABLE",
) -> HousekeepingAssetRecord:
    return HousekeepingAssetRecord(
        asset_id=asset_id,
        title=title or asset_id,
        status=status,
        file_set_id=file_set_id,
        file_set_name=file_set_name,
        storage_id="storage-1",
        storage_key=storage_key,
        date_created="2024-01-01",
        date_modified="2024-06-01",
        metadata_status=metadata_status,
    )


class HousekeepingServiceTests(unittest.TestCase):
    def test_duplicate_filename_groups(self) -> None:
        records = [
            _record("a1", file_set_name="CHE_TOT_20170422_G_02_ENGP.mp4"),
            _record("a2", file_set_name="CHE_TOT_20170422_G_02_ENGP.mp4"),
            _record("a3", file_set_name="OTHER.mp4"),
        ]
        groups = _find_duplicate_groups(
            records,
            key_fn=lambda r: r.file_set_name.strip(),
            skip_empty=True,
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].group_key, "CHE_TOT_20170422_G_02_ENGP.mp4")
        self.assertEqual(groups[0].count, 2)

    def test_duplicate_storage_groups(self) -> None:
        records = [
            _record("a1", storage_key="ENGLAND/ENGP/file.mp4"),
            _record("a2", storage_key="ENGLAND/ENGP/file.mp4"),
        ]
        groups = _find_duplicate_groups(
            records,
            key_fn=lambda r: r.storage_key.strip(),
            skip_empty=True,
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].count, 2)

    def test_duplicate_title_groups(self) -> None:
        records = [
            _record("a1", title="Same Title"),
            _record("a2", title="Same Title", file_set_name="one.mp4"),
            _record("a3", title="Same Title", file_set_name="two.mp4"),
        ]
        groups = _find_duplicate_groups(
            records,
            key_fn=lambda r: r.title.strip(),
            skip_empty=False,
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].count, 3)

    def test_orphan_detection(self) -> None:
        records = [
            _record("ok", file_set_id="fs", storage_key="path/file.mp4"),
            _record("no-fs", file_set_id="", storage_key="path/file.mp4"),
            _record("no-key", file_set_id="fs", storage_key=""),
            _record("inactive", status="ARCHIVED"),
            _record("no-meta", metadata_status="MISSING"),
        ]
        orphans = _find_orphans(records)
        by_id = {o.asset_id: o.orphan_reasons for o in orphans}
        self.assertIn("no-fs", by_id)
        self.assertIn("no_file_set", by_id["no-fs"])
        self.assertIn("no-key", by_id)
        self.assertIn("no_storage_key", by_id["no-key"])
        self.assertIn("inactive", by_id)
        self.assertTrue(any("inactive_status" in r for r in by_id["inactive"]))
        self.assertIn("no-meta", by_id)
        self.assertIn("missing_metadata_view", by_id["no-meta"])
        self.assertNotIn("ok", by_id)


if __name__ == "__main__":
    unittest.main()
