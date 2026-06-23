"""Load and persist user settings and path presets."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from app import SELECT_FOLDER_PLACEHOLDER
from models.discovery import SanitisationOptions
from services.paths import (
    AWS_SETTINGS_PATH,
    CATALOGUES_PATH,
    PATH_PRESETS_PATH,
    USER_SETTINGS_PATH,
)

logger = logging.getLogger(__name__)

DEFAULT_USER_SETTINGS: dict[str, Any] = {
    "replacement_source_folder": SELECT_FOLDER_PLACEHOLDER,
    "last_catalogue": "SERIE_C",
    "sanitisation_options": {
        "remove_apple_double": True,
        "remove_trailing_spaces": True,
        "remove_duplicate_spaces": True,
        "remove_invisible_characters": True,
        "standardise_extension_case": True,
    },
    "safety_replace_existing_only": True,
    "custom_s3_path": "",
    "upload_max_workers": 4,
    "aws_region": "eu-west-1",
    "iconik_base_url": "https://app.iconik.io/API",
    "iconik_app_id": "",
    "iconik_auth_token": "",
    "iconik_storage_id": "",
    "replacement_engp_file": "",
    "replacement_cfx_file": "",
    "preserve_iconik_asset_ids": True,
}

DEFAULT_AWS_SETTINGS: dict[str, str] = {
    "aws_access_key_id": "",
    "aws_secret_access_key": "",
    "aws_session_token": "",
    "aws_region": "eu-west-1",
}


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(default)
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            merged = deepcopy(default)
            merged.update(data)
            return merged
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
    return deepcopy(default)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    logger.info("Saved settings to %s", path)


class SettingsService:
    def __init__(self) -> None:
        self._user = _read_json(USER_SETTINGS_PATH, DEFAULT_USER_SETTINGS)
        self._aws = _read_json(AWS_SETTINGS_PATH, DEFAULT_AWS_SETTINGS)
        self._presets = _read_json(PATH_PRESETS_PATH, {})

    @property
    def user(self) -> dict[str, Any]:
        return self._user

    @property
    def aws(self) -> dict[str, str]:
        return {k: str(self._aws.get(k, "")) for k in DEFAULT_AWS_SETTINGS}

    @property
    def presets(self) -> dict[str, str]:
        return dict(self._presets)

    def source_folder(self) -> str:
        return str(self._user.get("replacement_source_folder", SELECT_FOLDER_PLACEHOLDER))

    def set_source_folder(self, path: str) -> None:
        self._user["replacement_source_folder"] = path
        self.save_user()

    def last_catalogue(self) -> str:
        return str(self._user.get("last_catalogue", "SERIE_C"))

    def set_last_catalogue(self, name: str) -> None:
        self._user["last_catalogue"] = name
        self.save_user()

    def custom_s3_path(self) -> str:
        return str(self._user.get("custom_s3_path", ""))

    def set_custom_s3_path(self, path: str) -> None:
        self._user["custom_s3_path"] = path
        self.save_user()

    def upload_max_workers(self) -> int:
        try:
            return max(1, min(16, int(self._user.get("upload_max_workers", 4))))
        except (TypeError, ValueError):
            return 4

    def set_upload_max_workers(self, workers: int) -> None:
        self._user["upload_max_workers"] = max(1, min(16, workers))
        self.save_user()

    def safety_replace_existing_only(self) -> bool:
        return bool(self._user.get("safety_replace_existing_only", True))

    def set_safety_replace_existing_only(self, enabled: bool) -> None:
        self._user["safety_replace_existing_only"] = enabled
        self.save_user()

    def sanitisation_options(self) -> SanitisationOptions:
        raw = self._user.get("sanitisation_options", {})
        if not isinstance(raw, dict):
            raw = {}
        defaults = DEFAULT_USER_SETTINGS["sanitisation_options"]
        return SanitisationOptions(
            remove_apple_double=bool(raw.get("remove_apple_double", defaults["remove_apple_double"])),
            remove_trailing_spaces=bool(raw.get("remove_trailing_spaces", defaults["remove_trailing_spaces"])),
            remove_duplicate_spaces=bool(raw.get("remove_duplicate_spaces", defaults["remove_duplicate_spaces"])),
            remove_invisible_characters=bool(
                raw.get("remove_invisible_characters", defaults["remove_invisible_characters"])
            ),
            standardise_extension_case=bool(
                raw.get("standardise_extension_case", defaults["standardise_extension_case"])
            ),
        )

    def set_sanitisation_options(self, options: SanitisationOptions) -> None:
        self._user["sanitisation_options"] = {
            "remove_apple_double": options.remove_apple_double,
            "remove_trailing_spaces": options.remove_trailing_spaces,
            "remove_duplicate_spaces": options.remove_duplicate_spaces,
            "remove_invisible_characters": options.remove_invisible_characters,
            "standardise_extension_case": options.standardise_extension_case,
        }
        self.save_user()

    def save_user(self) -> None:
        _write_json(USER_SETTINGS_PATH, self._user)

    def save_aws(self) -> None:
        _write_json(AWS_SETTINGS_PATH, self._aws)

    def update_aws(self, **kwargs: str) -> None:
        for key, value in kwargs.items():
            if key in DEFAULT_AWS_SETTINGS:
                self._aws[key] = value
        self.save_aws()

    def save_presets(self, presets: dict[str, str]) -> None:
        self._presets = dict(presets)
        _write_json(PATH_PRESETS_PATH, self._presets)

    def reload(self) -> None:
        self._user = _read_json(USER_SETTINGS_PATH, DEFAULT_USER_SETTINGS)
        self._aws = _read_json(AWS_SETTINGS_PATH, DEFAULT_AWS_SETTINGS)
        self._presets = _read_json(PATH_PRESETS_PATH, {})

    def iconik_base_url(self) -> str:
        return str(self._user.get("iconik_base_url", "https://app.iconik.io/API"))

    def iconik_app_id(self) -> str:
        return str(self._user.get("iconik_app_id", ""))

    def iconik_auth_token(self) -> str:
        return str(self._user.get("iconik_auth_token", ""))

    def iconik_storage_id(self) -> str:
        return str(self._user.get("iconik_storage_id", ""))

    def set_iconik_settings(
        self,
        *,
        base_url: str,
        app_id: str,
        auth_token: str,
        storage_id: str,
    ) -> None:
        self._user["iconik_base_url"] = base_url.strip()
        self._user["iconik_app_id"] = app_id.strip()
        self._user["iconik_auth_token"] = auth_token.strip()
        self._user["iconik_storage_id"] = storage_id.strip()
        self.save_user()

    def replacement_engp_file(self) -> str:
        return str(self._user.get("replacement_engp_file", ""))

    def replacement_cfx_file(self) -> str:
        return str(self._user.get("replacement_cfx_file", ""))

    def set_replacement_engp_file(self, path: str) -> None:
        self._user["replacement_engp_file"] = path.strip()
        self.save_user()

    def set_replacement_cfx_file(self, path: str) -> None:
        self._user["replacement_cfx_file"] = path.strip()
        self.save_user()

    def preserve_iconik_asset_ids(self) -> bool:
        return bool(self._user.get("preserve_iconik_asset_ids", True))

    def set_preserve_iconik_asset_ids(self, enabled: bool) -> None:
        self._user["preserve_iconik_asset_ids"] = enabled
        self.save_user()

    def is_valid_source_folder(self, path: str | None = None) -> bool:
        folder = path or self.source_folder()
        if not folder or folder == SELECT_FOLDER_PLACEHOLDER:
            return False
        p = Path(folder)
        return p.is_dir()

    @staticmethod
    def catalogues_path() -> Path:
        return CATALOGUES_PATH
