"""
Central team registry — canonical implementation shared across Kiron and Inspired tools.

Registry data file (maintained in Kiron repo):
``kiron_export_pipeline/config/team_registry.json``
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from team_registry.paths import default_registry_path

logger = logging.getLogger(__name__)


def normalize_team_key(value: str) -> str:
    """Case-insensitive team key normalization for aliases and names."""
    text = str(value or "").strip().lower()
    return "".join(ch for ch in text if ch.isalnum())


class TeamRegistryService:
    """Centralized registry loading, resolution, parsing, and validation."""

    def __init__(self, registry_path: Optional[str | Path] = None) -> None:
        self.registry_path = Path(registry_path) if registry_path else default_registry_path()
        self._registry_doc: dict[str, Any] = {}
        self._teams: dict[str, dict[str, Any]] = {}
        self._abbr_index: dict[str, str] = {}
        self._normalized_lookup: dict[str, str] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        if self.registry_path.exists():
            try:
                self._registry_doc = json.loads(self.registry_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to load team registry %s: %s", self.registry_path, exc)
                self._registry_doc = {}
        else:
            logger.warning("Team registry not found: %s", self.registry_path)
            self._registry_doc = {}

        raw_teams = self._registry_doc.get("teams")
        if isinstance(raw_teams, dict):
            source = raw_teams
        else:
            source = {k: v for k, v in self._registry_doc.items() if not str(k).startswith("_") and isinstance(v, dict)}

        self._teams = {}
        self._abbr_index = {}
        self._normalized_lookup = {}

        for code, team in source.items():
            team_code = str(team.get("abbreviation") or code).upper().strip()
            normalized_team = {
                "abbreviation": team_code,
                "full_name": str(team.get("full_name", "")).strip(),
                "aliases": list(team.get("aliases") or []),
                "country": str(team.get("country", "")).strip(),
                "league": str(team.get("league", "")).strip(),
                "normalized_keys": list(team.get("normalized_keys") or []),
            }
            self._teams[team_code] = normalized_team
            self._abbr_index[team_code] = team_code

        self._rebuild_normalized_lookup()

    def reload_registry(self) -> None:
        self._load_registry()

    def _rebuild_normalized_lookup(self) -> None:
        lookup: dict[str, str] = {}
        for team_code, team in self._teams.items():
            for key in self._keys_for_team(team):
                if key and key not in lookup:
                    lookup[key] = team_code
        self._normalized_lookup = lookup

    def _keys_for_team(self, team: dict[str, Any]) -> set[str]:
        keys = {
            normalize_team_key(team.get("abbreviation", "")),
            normalize_team_key(team.get("full_name", "")),
        }
        for alias in team.get("aliases") or []:
            keys.add(normalize_team_key(alias))
        for declared in team.get("normalized_keys") or []:
            keys.add(normalize_team_key(declared))
        return {k for k in keys if k}

    def all_teams(self) -> dict[str, dict[str, Any]]:
        return {code: dict(team) for code, team in self._teams.items()}

    def get_team_by_abbreviation(self, abbreviation: str) -> Optional[dict[str, Any]]:
        code = str(abbreviation or "").upper().strip()
        team_code = self._abbr_index.get(code)
        return dict(self._teams[team_code]) if team_code and team_code in self._teams else None

    def resolve_team_reference(self, value: str) -> Optional[dict[str, Any]]:
        key = normalize_team_key(value)
        team_code = self._normalized_lookup.get(key)
        return dict(self._teams[team_code]) if team_code and team_code in self._teams else None

    def resolve_team_reference_safe(
        self,
        value: str,
        *,
        allow_alias_enrichment: bool = False,
    ) -> Optional[dict[str, Any]]:
        token = str(value or "").strip()
        if not token:
            return None
        if allow_alias_enrichment:
            return self.resolve_team_reference(token)

        upper = token.upper()
        if upper in self._teams:
            return dict(self._teams[upper])

        lowered = token.casefold()
        for team in self._teams.values():
            if str(team.get("full_name", "")).strip().casefold() == lowered:
                return dict(team)
        return None

    def resolve_abbreviation(self, value: str) -> Optional[str]:
        team = self.resolve_team_reference(value)
        return str(team.get("abbreviation")) if team else None

    def normalize_team_reference(self, value: str, *, output: str = "abbreviation") -> Optional[str]:
        team = self.resolve_team_reference(value)
        if not team:
            return None
        if output == "full_name":
            return str(team.get("full_name", "")).strip() or None
        return str(team.get("abbreviation", "")).strip() or None

    def build_full_name_to_abbreviation_map(self, *, include_aliases: bool = False) -> dict[str, str]:
        output: dict[str, str] = {}
        for team in self._teams.values():
            full_name = str(team.get("full_name", "")).strip()
            abbreviation = str(team.get("abbreviation", "")).strip()
            if full_name and abbreviation:
                output[full_name] = abbreviation
            if include_aliases:
                for alias in team.get("aliases") or []:
                    alias_value = str(alias).strip()
                    if alias_value and abbreviation:
                        output[alias_value] = abbreviation
        return output

    def is_known_abbreviation(self, abbreviation: str) -> bool:
        return self.get_team_by_abbreviation(abbreviation) is not None

    def detect_unknown_abbreviations(self, abbreviations: list[str]) -> list[str]:
        unknown: list[str] = []
        seen: set[str] = set()
        for abbr in abbreviations:
            token = str(abbr or "").upper().strip()
            if not token or token in seen:
                continue
            seen.add(token)
            if not self.is_known_abbreviation(token):
                unknown.append(token)
        return unknown

    def detect_unresolved_team_references(self, values: list[str]) -> list[str]:
        unresolved: list[str] = []
        seen: set[str] = set()
        for value in values:
            token = str(value or "").strip()
            key = normalize_team_key(token)
            if not token or key in seen:
                continue
            seen.add(key)
            if self.resolve_team_reference(token) is None:
                unresolved.append(token)
        return unresolved

    def detect_duplicate_aliases(self) -> list[dict[str, Any]]:
        collisions: dict[str, set[str]] = {}
        for team_code, team in self._teams.items():
            for key in self._keys_for_team(team):
                collisions.setdefault(key, set()).add(team_code)
        return [
            {"normalized_key": key, "team_codes": sorted(codes)}
            for key, codes in sorted(collisions.items())
            if len(codes) > 1
        ]

    def validate_registry(self) -> dict[str, Any]:
        invalid_abbreviations: list[dict[str, Any]] = []
        unresolved_entries: list[dict[str, Any]] = []
        for team_code, team in self._teams.items():
            abbr = str(team.get("abbreviation", "")).strip()
            if len(abbr) != 3 or not abbr.isalpha():
                invalid_abbreviations.append({"team_code": team_code, "abbreviation": abbr})
            if not team.get("full_name"):
                unresolved_entries.append({"team_code": team_code, "issue": "missing_full_name"})
            if not team.get("country"):
                unresolved_entries.append({"team_code": team_code, "issue": "missing_country"})

        duplicates = self.detect_duplicate_aliases()
        return {
            "registry_path": str(self.registry_path),
            "team_count": len(self._teams),
            "invalid_abbreviations": invalid_abbreviations,
            "duplicate_aliases": duplicates,
            "unresolved_team_entries": unresolved_entries,
            "is_valid": not invalid_abbreviations and not duplicates and not unresolved_entries,
        }

    def parse_filename_metadata(self, filename: str) -> dict[str, Any]:
        """
        Parse ENGP-style filenames:

        ``ALPHABETICAL_TEAM_A_ALPHABETICAL_TEAM_B_YYYYMMDD_EVENT_SEQUENCE_SUFFIX``

        The two leading team tokens are in **alphabetical abbreviation order**. They do
        **not** represent Home vs Away — use metadata ``Home_Team`` / ``Away_Team`` for that.
        """
        stem = Path(filename).stem
        parts = stem.split("_")
        parsed: dict[str, Any] = {
            "filename": filename,
            "stem": stem,
            "parts": parts,
            "team_abbreviations": [],
            "team_abbreviations_sorted": [],
            "first_team_abbreviation": "",
            "second_team_abbreviation": "",
            "first_team": None,
            "second_team": None,
            # Back-compat keys (alphabetical slots — not Home/Away):
            "home_team_abbreviation": "",
            "away_team_abbreviation": "",
            "home_team": None,
            "away_team": None,
            "alphabetical_order_ok": True,
            "match_date_raw": "",
            "match_date_iso": "",
            "event_marker": "",
            "sequence": "",
            "league_suffix": "",
            "unknown_abbreviations": [],
            "is_valid": False,
        }
        if len(parts) < 6:
            parsed["parse_error"] = (
                "Filename does not match expected "
                "TEAM_A_TEAM_B_YYYYMMDD_EVENT_SEQUENCE_SUFFIX pattern "
                "(teams in alphabetical abbreviation order)."
            )
            return parsed

        first_code = parts[0].upper().strip()
        second_code = parts[1].upper().strip()
        match_date_raw = parts[2].strip()
        event_marker = parts[3].strip()
        sequence = parts[4].strip()
        league_suffix = "_".join(parts[5:]).strip()

        first_team = self.get_team_by_abbreviation(first_code)
        second_team = self.get_team_by_abbreviation(second_code)
        unknown = self.detect_unknown_abbreviations([first_code, second_code])
        alphabetical_order_ok = first_code <= second_code

        parsed.update(
            {
                "team_abbreviations": [first_code, second_code],
                "team_abbreviations_sorted": sorted([first_code, second_code]),
                "first_team_abbreviation": first_code,
                "second_team_abbreviation": second_code,
                "first_team": first_team,
                "second_team": second_team,
                "home_team_abbreviation": first_code,
                "away_team_abbreviation": second_code,
                "home_team": first_team,
                "away_team": second_team,
                "alphabetical_order_ok": alphabetical_order_ok,
                "match_date_raw": match_date_raw,
                "match_date_iso": self._format_match_date(match_date_raw),
                "event_marker": event_marker,
                "sequence": sequence,
                "league_suffix": league_suffix,
                "unknown_abbreviations": unknown,
            }
        )
        parsed["is_valid"] = bool(
            first_team
            and second_team
            and parsed["match_date_iso"]
            and event_marker
            and sequence
            and league_suffix
        )
        return parsed

    @staticmethod
    def _format_match_date(raw: str) -> str:
        token = str(raw or "").strip()
        if len(token) == 8 and token.isdigit():
            return f"{token[:4]}-{token[4:6]}-{token[6:8]}"
        return ""


def team_registry_service_from_app_settings() -> TeamRegistryService:
    """Construct using Kiron ``config.settings`` when available."""
    try:
        from config.settings import load_settings  # type: ignore[import-not-found]
    except ImportError:
        return TeamRegistryService()

    cfg = load_settings().get("team_registry") or {}
    path = str(cfg.get("registry_path", "")).strip()
    return TeamRegistryService(registry_path=path if path else None)
