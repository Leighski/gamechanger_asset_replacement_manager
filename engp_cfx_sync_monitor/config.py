"""Configuration for ENGP_CFX Sync Monitor."""

from __future__ import annotations

import os
from pathlib import Path

# LaunchAgent
LAUNCH_AGENT_LABEL = "com.gcs.engp_cfx_sync"
LAUNCH_AGENT_PLIST = Path.home() / "Library/LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"

# Logs
LOGS_DIR = Path.home() / "sync_logs"
SYNC_LOG = LOGS_DIR / "engp_cfx_sync.log"
ERROR_LOG = LOGS_DIR / "engp_cfx_error.log"
MONITOR_LOG = LOGS_DIR / "engp_cfx_monitor.log"

# NAS
NAS_PATH = Path(
    "/Volumes/03_EDITORIAL/010_S3_AUTOMATION/"
    "01_CFX_FILES_TO_S3_ENGP_CFX_FOLDER/ENGP_CLEANFX/"
)

# Polling
POLL_INTERVAL_SEC = 10
LOG_TAIL_LINES = 250

# AWS S3 — optional override via env; otherwise sts-only check
S3_BUCKET = os.environ.get("ENGP_CFX_S3_BUCKET", "").strip()
S3_PREFIX = os.environ.get("ENGP_CFX_S3_PREFIX", "").strip()
AWS_CLI_TIMEOUT_SEC = 15

# UI
APP_TITLE = "ENGP_CFX Sync Monitor"
WINDOW_SIZE = "1100x780"
MIN_WINDOW_SIZE = (900, 640)

# Log parsing (flexible patterns for sync script output)
SUCCESS_PATTERNS = (
    r"sync\s+completed\s+successfully",
    r"sync\s+success",
    r"successfully\s+synced",
    r"\bSUCCESS\b",
    r"completed\s+ok",
    r"upload\s+complete",
)
FAILURE_PATTERNS = (
    r"sync\s+failed",
    r"\bFAILED\b",
    r"\bERROR\b",
    r"upload\s+failed",
    r"exception",
    r"traceback",
)
