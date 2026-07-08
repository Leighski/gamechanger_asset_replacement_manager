"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app import APP_NAME

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_dir: Path | None = None, level: int = logging.INFO) -> Path:
    """Configure root logger with console and rotating file handlers."""
    root = Path(__file__).resolve().parents[1]
    logs_path = log_dir or (root / "logs")
    logs_path.mkdir(parents=True, exist_ok=True)
    log_file = logs_path / "replacement.log"

    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, force=True)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    file_handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    logging.getLogger(__name__).info("Started %s", APP_NAME)
    return log_file
