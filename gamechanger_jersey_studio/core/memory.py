"""Runtime memory usage helper."""

from __future__ import annotations

import resource
import sys


def memory_usage_mb() -> float:
    """Return current process memory usage in megabytes."""
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return usage / (1024 * 1024)
        return usage / 1024
    except Exception:
        return 0.0
