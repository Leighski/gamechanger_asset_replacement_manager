"""Development-only feature flags."""

from __future__ import annotations

import os


def is_developer_diagnostics_enabled() -> bool:
    """Return True when the developer diagnostics panel should be visible."""
    explicit = os.environ.get("GJS_DEV_DIAGNOSTICS")
    if explicit is not None:
        return explicit == "1"
    from core.version import APP_VERSION

    lowered = APP_VERSION.lower()
    return any(tag in lowered for tag in ("alpha", "beta", "rc"))
