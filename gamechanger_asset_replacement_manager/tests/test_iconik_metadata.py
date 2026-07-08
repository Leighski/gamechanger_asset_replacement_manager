"""Unit tests for resilient Iconik metadata lookup."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.iconik_verification import (
    METADATA_STATUS_AVAILABLE,
    METADATA_STATUS_ERROR,
    METADATA_STATUS_MISSING,
    IconikAssetReference,
    IconikVerificationService,
    VERIFY_PASS,
    VERIFY_WARNING,
)


def _ref(
    *,
    asset_id: str = "asset-1",
    metadata_field_count: int = 5,
    metadata_status: str = METADATA_STATUS_AVAILABLE,
    file_set_id: str = "fs-1",
    file_id: str = "file-1",
) -> IconikAssetReference:
    return IconikAssetReference(
        asset_id=asset_id,
        file_set_id=file_set_id,
        file_id=file_id,
        format_id="fmt",
        storage_id="stor",
        filename="TEST_ENGP.mp4",
        original_filename="TEST_ENGP.mp4",
        file_size=1,
        metadata_field_count=metadata_field_count,
        metadata_status=metadata_status,
    )


class IconikMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = IconikVerificationService(
            base_url="https://example.test/API",
            app_id="app",
            auth_token="token",
            storage_id="storage",
        )

    def test_fetch_metadata_missing_on_404(self) -> None:
        response = MagicMock()
        response.status_code = 404
        response.text = '{"errors":["Values for asset_id x version_id y doesn\'t exist"]}'
        response.content = response.text.encode()
        response.json.return_value = {
            "errors": ["Values for asset_id x version_id y doesn't exist"]
        }

        with patch.object(self.service._session, "get", return_value=response):
            result = self.service.fetch_metadata("9f611b4a-485e-11f1-a3cf-5e0b558b8458")

        self.assertEqual(result.status, METADATA_STATUS_MISSING)
        self.assertEqual(result.field_count, 0)

    def test_fetch_metadata_available_counts_fields(self) -> None:
        response = MagicMock()
        response.status_code = 200
        response.text = "{}"
        response.content = b"{}"
        response.json.return_value = {
            "metadata_values": {"field_a": "1", "field_b": "2", "__internal": "x"}
        }

        with patch.object(self.service._session, "get", return_value=response):
            result = self.service.fetch_metadata("asset-1")

        self.assertEqual(result.status, METADATA_STATUS_AVAILABLE)
        self.assertEqual(result.field_count, 2)

    def test_fetch_metadata_error_on_timeout(self) -> None:
        import requests

        with patch.object(
            self.service._session,
            "get",
            side_effect=requests.Timeout("timed out"),
        ):
            result = self.service.fetch_metadata("asset-1")

        self.assertEqual(result.status, METADATA_STATUS_ERROR)

    def test_verify_preservation_passes_when_metadata_missing(self) -> None:
        before = _ref(metadata_field_count=0, metadata_status=METADATA_STATUS_MISSING)
        after = _ref(metadata_field_count=0, metadata_status=METADATA_STATUS_MISSING)

        result = self.service.verify_preservation(before, after, require_file_id=True)

        self.assertEqual(result.status, VERIFY_PASS)
        self.assertTrue(result.asset_preserved)
        self.assertTrue(result.file_set_preserved)

    def test_verify_preservation_warns_when_metadata_count_decreases(self) -> None:
        before = _ref(metadata_field_count=5, metadata_status=METADATA_STATUS_AVAILABLE)
        after = _ref(metadata_field_count=2, metadata_status=METADATA_STATUS_AVAILABLE)

        result = self.service.verify_preservation(before, after)

        self.assertEqual(result.status, VERIFY_WARNING)
        self.assertFalse(result.metadata_preserved)


if __name__ == "__main__":
    unittest.main()
