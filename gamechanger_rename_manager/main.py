#!/usr/bin/env python3
"""Entry point for Gamechanger Rename Manager."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python main.py` from this directory without installing the package.
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from gamechanger_rename_manager.ui.app import run_app

if __name__ == "__main__":
    run_app()
