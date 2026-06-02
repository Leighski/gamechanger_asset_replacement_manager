"""Local JSON settings persistence."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

APP_NAME = "Gamechanger Rename Manager"
SETTINGS_VERSION = 1


def default_settings_path() -> Path:
    support = Path.home() / "Library" / "Application Support" / APP_NAME
    try:
        support.mkdir(parents=True, exist_ok=True)
        return support / "settings.json"
    except OSError:
        return Path.home() / ".gamechanger_rename_manager_settings.json"


@dataclass
class AppSettings:
    settings_version: int = SETTINGS_VERSION
    iconik_base_url: str = ""
    iconik_app_id: str = ""
    iconik_auth_token: str = ""
    iconik_collection_uuid: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_region: str = "eu-west-1"
    s3_bucket: str = ""
    s3_prefix: str = ""
    s3_backup_prefix: str = "backups/rename-manager/"
    enable_s3_backup: bool = True
    ffprobe_path: str = "ffprobe"
    ffmpeg_path: str = "ffmpeg"
    thumbnail_cache_dir: str = ""
    audit_log_dir: str = ""

    def effective_audit_dir(self) -> Path:
        if self.audit_log_dir.strip():
            p = Path(self.audit_log_dir.strip())
        else:
            p = Path.home() / "Library" / "Logs" / APP_NAME
        p.mkdir(parents=True, exist_ok=True)
        return p

    def effective_thumbnail_cache(self) -> Path:
        if self.thumbnail_cache_dir.strip():
            p = Path(self.thumbnail_cache_dir.strip())
        else:
            p = Path.home() / "Library" / "Caches" / APP_NAME / "thumbnails"
        p.mkdir(parents=True, exist_ok=True)
        return p


def load_settings(path: Path | None = None) -> AppSettings:
    p = path or default_settings_path()
    if not p.is_file():
        return AppSettings()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return AppSettings()
        return AppSettings(
            settings_version=int(data.get("settings_version", SETTINGS_VERSION)),
            iconik_base_url=str(data.get("iconik_base_url", "")),
            iconik_app_id=str(data.get("iconik_app_id", "")),
            iconik_auth_token=str(data.get("iconik_auth_token", "")),
            iconik_collection_uuid=str(data.get("iconik_collection_uuid", "")),
            aws_access_key_id=str(data.get("aws_access_key_id", "")),
            aws_secret_access_key=str(data.get("aws_secret_access_key", "")),
            aws_session_token=str(data.get("aws_session_token", "")),
            aws_region=str(data.get("aws_region", "eu-west-1")),
            s3_bucket=str(data.get("s3_bucket", "")),
            s3_prefix=str(data.get("s3_prefix", "")),
            s3_backup_prefix=str(data.get("s3_backup_prefix", "backups/rename-manager/")),
            enable_s3_backup=bool(data.get("enable_s3_backup", True)),
            ffprobe_path=str(data.get("ffprobe_path", "ffprobe")),
            ffmpeg_path=str(data.get("ffmpeg_path", "ffmpeg")),
            thumbnail_cache_dir=str(data.get("thumbnail_cache_dir", "")),
            audit_log_dir=str(data.get("audit_log_dir", "")),
        )
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load settings from %s: %s", p, exc)
        return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> bool:
    p = path or default_settings_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(settings)
        payload["settings_version"] = SETTINGS_VERSION
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return True
    except OSError as exc:
        logger.error("Failed to save settings: %s", exc)
        return False
