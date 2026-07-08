#!/usr/bin/env python3
"""Gamechanger Jersey Studio — application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.controller import ApplicationController


def main() -> int:
    return ApplicationController(sys.argv).run()


if __name__ == "__main__":
    raise SystemExit(main())
