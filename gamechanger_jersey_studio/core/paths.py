"""Canonical project paths."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
CORE_DIR = PROJECT_ROOT / "core"
UI_DIR = PROJECT_ROOT / "ui"
MODELS_DIR = PROJECT_ROOT / "models"
SERVICES_DIR = PROJECT_ROOT / "services"
LIBRARIES_DIR = PROJECT_ROOT / "libraries"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
PROJECTS_DIR = PROJECT_ROOT / "projects"
RESOURCES_DIR = PROJECT_ROOT / "resources"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"
DOCS_DIR = PROJECT_ROOT / "docs"
TESTS_DIR = PROJECT_ROOT / "tests"
WORK_PACKAGES_DIR = PROJECT_ROOT / "work_packages"
CONFIG_DIR = PROJECT_ROOT / "config"
COMPONENT_LIBRARY_DIR = CONFIG_DIR / "component_library"
CACHE_DIR = PROJECT_ROOT / "cache"

WORKSPACE_DIR = CACHE_DIR / "workspace"
SESSION_STATE_PATH = CACHE_DIR / "session_state.json"

SETTINGS_PATH = CONFIG_DIR / "settings.json"
SETTINGS_EXAMPLE_PATH = CONFIG_DIR / "settings.example.json"
APPLICATION_LOG_PATH = LOGS_DIR / "application.log"
