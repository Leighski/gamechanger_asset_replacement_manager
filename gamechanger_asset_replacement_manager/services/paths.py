"""Project path helpers."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"

USER_SETTINGS_PATH = CONFIG_DIR / "user_settings.json"
PATH_PRESETS_PATH = CONFIG_DIR / "path_presets.json"
CATALOGUES_PATH = CONFIG_DIR / "catalogues.json"
AWS_SETTINGS_PATH = CONFIG_DIR / "aws_settings.json"
