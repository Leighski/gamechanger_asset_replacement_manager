#!/usr/bin/env python3
"""Entry point for Gamechanger Asset Replacement Manager."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when launched as script
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.logging_setup import setup_logging
from gui.main_window import run_app


def main() -> int:
    setup_logging()
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
