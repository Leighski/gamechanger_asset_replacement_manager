"""Read and parse sync / error logs."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from engp_cfx_sync_monitor import config

logger = logging.getLogger(__name__)

# Common timestamp prefixes: ISO, syslog-style, bracketed
_TS_PATTERNS = (
    re.compile(r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)"),
    re.compile(r"^(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})"),
    re.compile(r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]"),
)


@dataclass(frozen=True)
class LogSnapshot:
    sync_tail: str
    error_tail: str
    last_success: str | None
    last_failure: str | None
    sync_exists: bool
    error_exists: bool


def _compile_patterns(patterns: tuple[str, ...]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.I) for p in patterns]


_SUCCESS_RES = _compile_patterns(config.SUCCESS_PATTERNS)
_FAILURE_RES = _compile_patterns(config.FAILURE_PATTERNS)


def _extract_timestamp(line: str) -> str | None:
    for pat in _TS_PATTERNS:
        m = pat.match(line.strip())
        if m:
            return m.group(1).replace("T", " ")
    return None


def _normalize_ts(raw: str) -> str:
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(raw[:26].strip(), fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return raw


def _scan_file(
    path: Path,
    matchers: list[re.Pattern[str]],
    *,
    reverse: bool = True,
) -> str | None:
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None

    iterable = reversed(lines) if reverse else lines
    for line in iterable:
        if not line.strip():
            continue
        if not any(m.search(line) for m in matchers):
            continue
        ts = _extract_timestamp(line)
        if ts:
            return _normalize_ts(ts)
        return line.strip()[:120]
    return None


def tail_file(path: Path, max_lines: int) -> tuple[str, bool]:
    if not path.is_file():
        return f"(log not found: {path})", False
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as exc:
        return f"(cannot read log: {exc})", True

    if not lines:
        return "(empty log)", True

    tail = lines[-max_lines:]
    return "".join(tail), True


def read_log_snapshot() -> LogSnapshot:
    sync_tail, sync_ok = tail_file(config.SYNC_LOG, config.LOG_TAIL_LINES)
    err_tail, err_ok = tail_file(config.ERROR_LOG, config.LOG_TAIL_LINES)

    last_success = _scan_file(config.SYNC_LOG, _SUCCESS_RES)
    last_failure = _scan_file(config.ERROR_LOG, _FAILURE_RES)
    if not last_failure:
        last_failure = _scan_file(config.SYNC_LOG, _FAILURE_RES)

    return LogSnapshot(
        sync_tail=sync_tail,
        error_tail=err_tail,
        last_success=last_success,
        last_failure=last_failure,
        sync_exists=sync_ok and config.SYNC_LOG.is_file(),
        error_exists=err_ok and config.ERROR_LOG.is_file(),
    )
