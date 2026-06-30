"""Version manager tests."""

from __future__ import annotations

from core.version import (
    APP_NAME,
    APP_VERSION,
    BUILD_NUMBER,
    BUILD_LABEL,
    VERSION_LABEL,
    WORK_PACKAGE,
)
from services.version_manager import VersionManager


def test_version_info_values() -> None:
    mgr = VersionManager()
    info = mgr.info
    assert info.application_name == APP_NAME
    assert info.version == APP_VERSION
    assert info.build_number == BUILD_NUMBER
    assert info.build_label == BUILD_LABEL
    assert info.version_label == VERSION_LABEL
    assert info.display_version == VERSION_LABEL
    assert info.work_package == WORK_PACKAGE
    assert info.application_path
    assert info.configuration_path
    assert info.log_path
    assert "." in info.python_version


def test_summary_line() -> None:
    mgr = VersionManager()
    line = mgr.summary_line()
    assert APP_NAME in line
    assert VERSION_LABEL in line
    assert BUILD_LABEL in line


def test_branding_line() -> None:
    mgr = VersionManager()
    assert BUILD_LABEL in mgr.info.branding_line
    assert VERSION_LABEL in mgr.info.branding_line


def test_refresh_returns_new_info() -> None:
    mgr = VersionManager()
    first = mgr.info
    second = mgr.refresh()
    assert first.application_name == second.application_name
    assert first.version == second.version
