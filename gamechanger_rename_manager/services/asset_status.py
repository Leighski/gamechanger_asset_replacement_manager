"""Iconik asset lifecycle helpers (soft-delete detection)."""

from __future__ import annotations

from typing import Any


def _has_deleted_date(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        s = value.strip().lower()
        return bool(s) and s not in ("null", "none", "0", "false")
    return True


def is_deleted_iconik_doc(doc: dict | None) -> bool:
    """
    True when Iconik marks an asset as soft-deleted.

    Rules:
    - status == DELETED (case-insensitive)
    - OR any known date_deleted field is set
    """
    if not doc or not isinstance(doc, dict):
        return False

    for key in ("status", "asset_status", "state", "lifecycle_status"):
        raw = doc.get(key)
        if isinstance(raw, str) and raw.strip().upper() == "DELETED":
            return True

    for key in (
        "date_deleted",
        "deleted_date",
        "system_date_deleted",
        "date_deleted_utc",
        "deleted_at",
    ):
        if _has_deleted_date(doc.get(key)):
            return True

    return False
