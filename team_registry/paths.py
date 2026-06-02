"""Resolve canonical ``team_registry.json`` path for all consumers."""

from __future__ import annotations

import os
from pathlib import Path


def inspired_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def kiron_project_root() -> Path:
    return inspired_project_root().parent / "kiron_export_pipeline"


def default_registry_path() -> Path:
    """
    Canonical registry file (maintained under Kiron):

    ``kiron_export_pipeline/config/team_registry.json``

    Override with environment variable ``TEAM_REGISTRY_PATH``.
    """
    env = os.environ.get("TEAM_REGISTRY_PATH", "").strip()
    if env:
        return Path(env).expanduser()

    kiron_cfg = kiron_project_root() / "config" / "team_registry.json"
    if kiron_cfg.is_file():
        return kiron_cfg

    # Fallback when package is imported from within kiron_export_pipeline tree.
    local_cfg = Path(__file__).resolve().parents[2] / "config" / "team_registry.json"
    if local_cfg.is_file():
        return local_cfg

    return kiron_cfg
