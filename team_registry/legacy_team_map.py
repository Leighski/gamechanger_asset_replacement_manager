"""
Legacy English PL team map — staged migration fallback only.

Canonical source: ``team_registry.json`` via :class:`TeamRegistryService`.

Keep in sync with ``kiron_export_pipeline/config/mappings.py`` → ``TEAM_MAP`` until
that dict is generated from the registry or removed. See ``docs/TEAM_REGISTRY_MIGRATION.md``.
"""

from __future__ import annotations

# LEGACY_TEAM_MAP — do not extend for new teams; update team_registry.json instead.
LEGACY_TEAM_MAP: dict[str, str] = {
    "Arsenal": "ARS",
    "Aston Villa": "AST",
    "Bournemouth": "BOU",
    "Brentford": "BRE",
    "Brighton": "BHA",
    "Burnley": "BUR",
    "Chelsea": "CHE",
    "Crystal Palace": "CRY",
    "Everton": "EVE",
    "Fulham": "FUL",
    "Ipswich": "IPS",
    "Leeds": "LEE",
    "Leicester": "LEI",
    "Liverpool": "LIV",
    "Luton": "LUT",
    "Manchester City": "MNC",
    "Manchester Utd": "MNU",
    "Newcastle": "NEW",
    "Nottingham Forest": "NOT",
    "Sheffield Utd": "SHU",
    "Southampton": "SOU",
    "Stoke": "STO",
    "Sunderland": "SUN",
    "Tottenham": "TOT",
    "West Ham": "WHU",
    "Wolverhampton": "WOL",
}
