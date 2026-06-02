"""Production logging setup for the monitor app."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from engp_cfx_sync_monitor import config


def setup_logging(level: int = logging.INFO) -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        config.MONITOR_LOG,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(logging.WARNING)

    root.addHandler(file_handler)
    root.addHandler(console)

    logging.getLogger("engp_cfx_sync_monitor").setLevel(level)
