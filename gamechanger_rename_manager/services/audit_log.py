"""Transaction audit logging."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gamechanger_rename_manager.config.settings import AppSettings

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(self, settings: AppSettings) -> None:
        self._dir = settings.effective_audit_dir()

    def log_transaction(self, record: dict[str, Any]) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        asset_id = record.get("asset_id", "unknown")
        path = self._dir / f"rename_{ts}_{asset_id}.json"
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            logger.info("Audit log written: %s", path)
        except OSError as exc:
            logger.error("Failed to write audit log: %s", exc)
        return path

    def append_daily_log(self, line: str) -> None:
        daily = self._dir / f"transactions_{datetime.now().strftime('%Y%m%d')}.log"
        try:
            with daily.open("a", encoding="utf-8") as f:
                f.write(line.rstrip() + "\n")
        except OSError as exc:
            logger.error("Failed to append daily log: %s", exc)
