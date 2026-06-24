#!/usr/bin/env python3
"""Tenant diagnostic for Iconik search_after cursor pagination support."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services.iconik_verification import IconikVerificationService
from services.settings_service import SettingsService


def build_iconik_service() -> IconikVerificationService:
    settings = SettingsService()
    return IconikVerificationService(
        base_url=settings.iconik_base_url(),
        app_id=settings.iconik_app_id(),
        auth_token=settings.iconik_auth_token(),
        storage_id=settings.iconik_storage_id(),
    )


def run_validation(*, query: str = "", per_page: int = 2) -> dict[str, bool]:
    service = build_iconik_service()
    if not service.configured():
        raise RuntimeError(
            "Iconik credentials are not configured. Set app ID, auth token, and storage ID in settings."
        )
    return service.probe_search_after_support(query=query, per_page=per_page)


def main() -> int:
    try:
        result = run_validation()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for key in ("SEARCH_AFTER_SUPPORTED", "SORT_ID_SUPPORTED", "SORT_VALUES_PRESENT"):
        print(f"{key}={str(result[key]).lower()}")
    return 0 if result["SEARCH_AFTER_SUPPORTED"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
