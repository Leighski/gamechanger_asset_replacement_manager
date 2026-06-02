"""NAS mount availability check."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from engp_cfx_sync_monitor import config

logger = logging.getLogger(__name__)


def check_nas_mount(path: Path | None = None) -> tuple[bool, str]:
    target = path or config.NAS_PATH
    p = Path(target)

    if not p.exists():
        return False, f"Path not found: {p}"

    if not os.path.ismount(str(p)):
        # Parent volume may be mount; path can exist under mounted share
        vol = _volume_for_path(p)
        if vol and os.path.ismount(vol):
            if os.access(p, os.R_OK):
                return True, f"OK — under mounted volume {vol}"
            return False, f"Mounted at {vol} but not readable: {p}"
        if os.access(p, os.R_OK):
            return True, f"Accessible (not a mount point): {p}"
        return False, f"Not a mount point and not readable: {p}"

    if not os.access(p, os.R_OK):
        return False, f"Mounted but not readable: {p}"

    return True, f"Mounted and readable: {p}"


def _volume_for_path(p: Path) -> str | None:
    parts = p.parts
    if len(parts) >= 2 and parts[1] == "Volumes":
        return os.path.join("/", "Volumes", parts[2])
    return None
