#!/usr/bin/env python3
"""Entry point for ENGP_CFX Sync Monitor."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python3 engp_cfx_sync_monitor/main.py` without pip install
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engp_cfx_sync_monitor.ui.app import main  # noqa: E402

if __name__ == "__main__":
    main()
