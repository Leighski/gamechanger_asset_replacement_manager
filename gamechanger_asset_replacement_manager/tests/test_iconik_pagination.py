"""Unit tests for production-safe Iconik pagination."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.iconik_verification import (
    MAX_RATE_LIMIT_RETRIES,
    PAGINATION_OFFSET,
    PAGINATION_SEARCH_AFTER,
    SEARCH_AFTER_FALLBACK_WARNING,
    IconikVerificationService,
)


def _service() -> IconikVerificationService:
    return IconikVerificationService(
        base_url="https://app.iconik.io/API",
        app_id="app",
        auth_token="token",
        storage_id="storage",
    )


def _asset(asset_id: str, *, date_created: str = "2024-01-01T00:00:00Z") -> dict:
    return {
        "id": asset_id,
        "title": f"Asset {asset_id}",
        "date_created": date_created,
        "_sort": [date_created, asset_id],
    }


class SearchAfterProbeTests(unittest.TestCase):
    def test_probe_empty_library_supported(self) -> None:
        service = _service()
        with patch.object(service, "search_assets_cursor", return_value=([], 0)):
            result = service.probe_search_after_support()

        self.assertTrue(result["SEARCH_AFTER_SUPPORTED"])
        self.assertTrue(result["SORT_ID_SUPPORTED"])
        self.assertTrue(result["SORT_VALUES_PRESENT"])

    def test_probe_rejects_missing_sort_values(self) -> None:
        service = _service()
        batch = [{"id": "a1", "title": "A"}]
        with patch.object(service, "search_assets_cursor", return_value=(batch, 1)):
            result = service.probe_search_after_support()

        self.assertFalse(result["SEARCH_AFTER_SUPPORTED"])
        self.assertTrue(result["SORT_ID_SUPPORTED"])
        self.assertFalse(result["SORT_VALUES_PRESENT"])

    def test_probe_rejects_overlapping_cursor_page(self) -> None:
        service = _service()
        batch1 = [_asset("a1"), _asset("a2")]
        batch2 = [_asset("a2")]

        with patch.object(
            service,
            "search_assets_cursor",
            side_effect=[(batch1, 3), (batch2, 3)],
        ):
            result = service.probe_search_after_support()

        self.assertFalse(result["SEARCH_AFTER_SUPPORTED"])
        self.assertTrue(result["SORT_VALUES_PRESENT"])


class IterateAllAssetsSearchAfterTests(unittest.TestCase):
    def _supported_probe(self) -> dict[str, bool]:
        return {
            "SEARCH_AFTER_SUPPORTED": True,
            "SORT_ID_SUPPORTED": True,
            "SORT_VALUES_PRESENT": True,
        }

    def test_search_after_deduplicates_across_pages(self) -> None:
        service = _service()
        pages = [
            ([_asset("a1"), _asset("a2")], 3),
            ([_asset("a2"), _asset("a3")], 3),
            ([], 3),
        ]

        def fake_cursor(query: str = "", *, search_after=None, per_page: int = 100):
            if search_after is None:
                return pages[0]
            if search_after == pages[0][0][-1]["_sort"]:
                return pages[1]
            return pages[2]

        with patch.object(service, "probe_search_after_support", return_value=self._supported_probe()):
            with patch.object(service, "search_assets_cursor", side_effect=fake_cursor):
                result = service.iterate_all_assets(per_page=2)

        self.assertEqual(len(result.assets), 3)
        self.assertEqual(result.summary.assets_scanned, 3)
        self.assertEqual(result.summary.duplicate_asset_ids_filtered, 1)
        self.assertEqual(result.summary.pages_received, 3)
        self.assertEqual(result.summary.pagination_method, PAGINATION_SEARCH_AFTER)
        self.assertEqual(result.summary.first_asset_id, "a1")
        self.assertEqual(result.summary.last_asset_id, "a3")
        self.assertFalse(result.summary.terminated_by_page_limit)

    def test_search_after_terminates_on_empty_batch_only(self) -> None:
        service = _service()
        pages = [([_asset(f"a{i}") for i in range(5)], 1000)]

        def fake_cursor(query: str = "", *, search_after=None, per_page: int = 100):
            if search_after is None:
                return pages[0]
            return ([], 1000)

        with patch.object(service, "probe_search_after_support", return_value=self._supported_probe()):
            with patch.object(service, "search_assets_cursor", side_effect=fake_cursor):
                result = service.iterate_all_assets(per_page=5, max_pages=1)

        self.assertEqual(result.summary.assets_scanned, 5)
        self.assertEqual(result.summary.pages_received, 2)
        self.assertFalse(result.summary.terminated_by_page_limit)

    def test_search_after_count_mismatch_warning(self) -> None:
        service = _service()
        pages = [
            ([_asset("a1"), _asset("a2")], 5),
            ([], 5),
        ]

        with patch.object(service, "probe_search_after_support", return_value=self._supported_probe()):
            with patch.object(
                service,
                "search_assets_cursor",
                side_effect=lambda *a, **k: pages[0] if k.get("search_after") is None else pages[1],
            ):
                result = service.iterate_all_assets(per_page=2)

        self.assertEqual(result.summary.assets_scanned, 2)
        self.assertEqual(result.summary.assets_reported_by_iconik, 5)
        self.assertTrue(any("Asset count mismatch" in w for w in result.summary.warnings))

    def test_search_after_progress_after_page_fetch(self) -> None:
        service = _service()
        pages = [
            ([_asset("a1")], 1),
            ([], 1),
        ]
        snapshots: list[int] = []

        def on_page(progress) -> None:
            snapshots.append(progress.running_total)

        with patch.object(service, "probe_search_after_support", return_value=self._supported_probe()):
            with patch.object(
                service,
                "search_assets_cursor",
                side_effect=lambda *a, **k: pages[0] if k.get("search_after") is None else pages[1],
            ):
                service.iterate_all_assets(per_page=10, on_page=on_page)

        self.assertEqual(snapshots, [1])

    def test_search_after_audit_summary_timing_fields(self) -> None:
        service = _service()
        pages = [
            ([_asset("a1")], 1),
            ([], 1),
        ]

        with patch.object(service, "probe_search_after_support", return_value=self._supported_probe()):
            with patch.object(
                service,
                "search_assets_cursor",
                side_effect=lambda *a, **k: pages[0] if k.get("search_after") is None else pages[1],
            ):
                result = service.iterate_all_assets(per_page=10)

        self.assertTrue(result.summary.scan_started)
        self.assertTrue(result.summary.scan_completed)
        self.assertGreaterEqual(result.summary.scan_duration_seconds, 0.0)


class IterateAllAssetsOffsetFallbackTests(unittest.TestCase):
    def test_fallback_when_search_after_unsupported(self) -> None:
        service = _service()
        unsupported = {
            "SEARCH_AFTER_SUPPORTED": False,
            "SORT_ID_SUPPORTED": False,
            "SORT_VALUES_PRESENT": False,
        }
        pages = [
            ([_asset("a1")], 1),
            ([], 1),
        ]

        with patch.object(service, "probe_search_after_support", return_value=unsupported):
            with patch.object(
                service,
                "search_assets_page",
                side_effect=lambda *a, **k: pages[k["page"] - 1],
            ):
                result = service.iterate_all_assets(per_page=10)

        self.assertEqual(result.summary.pagination_method, PAGINATION_OFFSET)
        self.assertTrue(any(SEARCH_AFTER_FALLBACK_WARNING in w for w in result.summary.warnings))

    def test_offset_max_page_limit_warning(self) -> None:
        service = _service()
        unsupported = {
            "SEARCH_AFTER_SUPPORTED": False,
            "SORT_ID_SUPPORTED": True,
            "SORT_VALUES_PRESENT": True,
        }

        def fake_search(query: str, *, page: int, per_page: int = 100):
            return ([_asset(f"a{page}-{i}") for i in range(per_page)], 1000)

        with patch.object(service, "probe_search_after_support", return_value=unsupported):
            with patch.object(service, "search_assets_page", side_effect=fake_search):
                result = service.iterate_all_assets(per_page=2, max_pages=3)

        self.assertEqual(result.summary.pages_received, 3)
        self.assertEqual(result.summary.assets_scanned, 6)
        self.assertTrue(result.summary.terminated_by_page_limit)
        self.assertTrue(any("page limit" in w.lower() for w in result.summary.warnings))


class RateLimitRetryTests(unittest.TestCase):
    @patch("services.iconik_verification.time.sleep")
    def test_rate_limit_retries_with_backoff(self, sleep_mock: MagicMock) -> None:
        service = _service()
        responses = [(429, None, "rate limited")] * MAX_RATE_LIMIT_RETRIES + [(200, {"objects": [], "total": 0}, "")]
        service._post = MagicMock(side_effect=responses)

        code, data, text = service._post_with_rate_limit_retry("search/v1/search/")

        self.assertEqual(code, 200)
        self.assertEqual(service._post.call_count, MAX_RATE_LIMIT_RETRIES + 1)
        self.assertEqual(sleep_mock.call_count, MAX_RATE_LIMIT_RETRIES)

    @patch("services.iconik_verification.time.sleep")
    def test_rate_limit_aborts_after_max_retries(self, sleep_mock: MagicMock) -> None:
        service = _service()
        service._post = MagicMock(return_value=(429, None, "rate limited"))

        code, data, text = service._post_with_rate_limit_retry("search/v1/search/")

        self.assertEqual(code, 429)
        self.assertEqual(service._post.call_count, MAX_RATE_LIMIT_RETRIES + 1)
        self.assertEqual(sleep_mock.call_count, MAX_RATE_LIMIT_RETRIES)


if __name__ == "__main__":
    unittest.main()
