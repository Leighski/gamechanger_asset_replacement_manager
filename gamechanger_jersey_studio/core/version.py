"""Application version and release metadata."""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from PySide6.QtCore import qVersion
except ImportError:  # pragma: no cover
    qVersion = None  # type: ignore[assignment,misc]

from core.paths import APPLICATION_LOG_PATH, CONFIG_DIR, PROJECT_ROOT

APP_NAME = "Gamechanger Jersey Studio"
APP_VERSION = "1.0.0-alpha.9"
VERSION_LABEL = "Version 1.0 Alpha"
BUILD_NUMBER = "009"
BUILD_LABEL = f"Build {BUILD_NUMBER}"
COPYRIGHT = "© Gamechanger Sports"
WORK_PACKAGE = "GJS-009"
RELEASE_DATE = "2026-06-30"

VERSION_HISTORY = {
    "1.0.0-alpha.1": "Application Foundation",
    "1.0.0-alpha.2": "Project Management",
    "1.0.0-alpha.3": "User Experience Polish",
    "1.0.0-alpha.4": "Design Specification Engine",
    "1.0.0-alpha.5": "Reference Image Management",
    "1.0.0-alpha.6": "Vision Engine Phase 1 — Image Analysis Foundation",
    "1.0.0-alpha.7": "AI Interpretation & Operator Review Engine",
    "1.0.0-alpha.8": "Component Library & Asset Catalogue System",
    "1.0.0-alpha.9": "Live Renderer & Component Assembly Engine",
}


@dataclass(frozen=True)
class VersionInfo:
    application_name: str
    version: str
    version_label: str
    build_number: str
    build_label: str
    copyright: str
    work_package: str
    release_date: str
    python_version: str
    qt_version: str
    application_path: str
    configuration_path: str
    log_path: str

    @property
    def display_version(self) -> str:
        return self.version_label

    @property
    def full_title(self) -> str:
        return f"{self.application_name} {self.version_label} ({self.build_label})"

    @property
    def branding_line(self) -> str:
        return f"{self.version_label} · {self.build_label}"


def get_python_version() -> str:
    return platform.python_version()


def get_qt_version() -> str:
    if qVersion is not None:
        return qVersion()
    return "—"


def get_version_info() -> VersionInfo:
    return VersionInfo(
        application_name=APP_NAME,
        version=APP_VERSION,
        version_label=VERSION_LABEL,
        build_number=BUILD_NUMBER,
        build_label=BUILD_LABEL,
        copyright=COPYRIGHT,
        work_package=WORK_PACKAGE,
        release_date=RELEASE_DATE,
        python_version=get_python_version(),
        qt_version=get_qt_version(),
        application_path=str(PROJECT_ROOT),
        configuration_path=str(CONFIG_DIR),
        log_path=str(APPLICATION_LOG_PATH),
    )
