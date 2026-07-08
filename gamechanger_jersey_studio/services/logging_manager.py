"""Loguru-based application logging."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from core.paths import APPLICATION_LOG_PATH, LOGS_DIR

if TYPE_CHECKING:
    from loguru import Record

_CONFIGURED = False


def _format_record(record: Record) -> str:
    level = record["level"].name
    message = record["message"]
    return f"{level}: {message}\n"


def configure_logging(log_path: Path | None = None) -> Path:
    """Configure Loguru for console and rotating application log file."""
    global _CONFIGURED
    target = log_path or APPLICATION_LOG_PATH
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        enqueue=True,
    )
    logger.add(
        target,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="10 MB",
        retention=10,
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    _CONFIGURED = True
    return target


def get_logger():
    return logger


def flush_logging() -> None:
    """Wait for enqueued log messages to be written."""
    logger.complete()


def log_application_started(version_line: str) -> None:
    logger.info("Application Started — {}", version_line)


def log_application_closed() -> None:
    logger.info("Application Closed")


def log_settings_loaded(path: Path) -> None:
    logger.info("Settings Loaded — {}", path)


def log_settings_saved(path: Path) -> None:
    logger.info("Settings Saved — {}", path)


def log_window_restored(width: int, height: int, x: int, y: int, maximised: bool) -> None:
    logger.info(
        "Window Restored — {}x{} at ({}, {}), maximised={}",
        width,
        height,
        x,
        y,
        maximised,
    )


def log_design_spec_changed(property_name: str, old_value: str, new_value: str, user: str) -> None:
    logger.info(
        "Design Specification changed — {}: {} → {} (user={})",
        property_name,
        old_value,
        new_value,
        user,
    )


def log_unexpected_error(exc: BaseException, *, context: str = "") -> None:
    prefix = f"{context}: " if context else ""
    logger.exception("{}{}", prefix, exc)


def install_exception_hooks() -> None:
    """Route uncaught exceptions to the application log."""

    def _sys_hook(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).error(
            "Uncaught exception"
        )

    sys.excepthook = _sys_hook
