"""Version information service."""

from __future__ import annotations

from core.version import VersionInfo, get_version_info


class VersionManager:
    """Expose application and platform version metadata."""

    def __init__(self) -> None:
        self._info = get_version_info()

    @property
    def info(self) -> VersionInfo:
        return self._info

    def refresh(self) -> VersionInfo:
        self._info = get_version_info()
        return self._info

    def summary_line(self) -> str:
        info = self._info
        return f"{info.application_name} {info.display_version} ({info.build_label})"
