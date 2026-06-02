"""
Shared team registry — canonical normalization for Kiron and Inspired delivery tools.

Registry JSON (source of truth):
``kiron_export_pipeline/config/team_registry.json``
"""

from team_registry.legacy_team_map import LEGACY_TEAM_MAP
from team_registry.normalize import (
    INSPIRED_TEAM_COLUMNS,
    TEAM_METADATA_COLUMNS_ENGP,
    TeamNormalizationBatchReport,
    TeamNormalizationResult,
    canonical_team_code_set,
    filename_team_set_from_parsed,
    metadata_home_away_team_set,
    new_transition_report,
    normalize_team_value_to_abbreviation,
    resolve_team_abbreviation_with_bridge,
    validate_inspired_row_teams_vs_filename,
)
from team_registry.paths import default_registry_path, inspired_project_root, kiron_project_root
from team_registry.service import TeamRegistryService, normalize_team_key, team_registry_service_from_app_settings

__all__ = [
    "INSPIRED_TEAM_COLUMNS",
    "LEGACY_TEAM_MAP",
    "TEAM_METADATA_COLUMNS_ENGP",
    "TeamNormalizationBatchReport",
    "TeamNormalizationResult",
    "TeamRegistryService",
    "canonical_team_code_set",
    "default_registry_path",
    "filename_team_set_from_parsed",
    "metadata_home_away_team_set",
    "inspired_project_root",
    "kiron_project_root",
    "new_transition_report",
    "normalize_team_key",
    "normalize_team_value_to_abbreviation",
    "resolve_team_abbreviation_with_bridge",
    "team_registry_service_from_app_settings",
    "validate_inspired_row_teams_vs_filename",
]
