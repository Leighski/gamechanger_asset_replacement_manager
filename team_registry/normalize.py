"""
Deterministic team abbreviation normalization for delivery metadata and Kiron templates.

Resolution order (Inspired + Kiron export when abbreviating):
1. Known 3-letter registry abbreviation (passthrough)
2. Registry lookup (alias enrichment when enabled — deterministic normalized-key match)
3. Legacy ``LEGACY_TEAM_MAP`` fallback
4. Preserve original value + record unknown (no silent guess)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, MutableMapping

from team_registry.legacy_team_map import LEGACY_TEAM_MAP
from team_registry.service import TeamRegistryService

# Inspired / Kiron metadata columns normalized to 3-letter codes.
TEAM_METADATA_COLUMNS_ENGP: tuple[str, ...] = (
    "Attacking_Team_ENGP",
    "Defending_Team_ENGP",
    "Home_Team_ENGP",
    "Away_Team_ENGP",
)

INSPIRED_TEAM_COLUMNS: frozenset[str] = frozenset(
    {"Home Team", "Away Team", "Attacking Team", "Defending Team"}
)


@dataclass
class TeamNormalizationResult:
  """Outcome of a single team value normalization."""

  output_value: str
  original_value: str
  resolved: bool
  resolution_source: str = ""  # registry | legacy_team_map | passthrough | unresolved
  warning: str = ""


@dataclass
class TeamNormalizationBatchReport:
    registry_hits: int = 0
    legacy_team_map_hits: int = 0
    passthrough_hits: int = 0
    unresolved_count: int = 0
    resolved_examples: dict[str, str] = field(default_factory=dict)
    legacy_fallback_examples: dict[str, str] = field(default_factory=dict)
    unresolved_examples: list[str] = field(default_factory=list)


def _blankish(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.lower() in {"nan", "none", "null"}


def normalize_team_value_to_abbreviation(
    value: object,
    *,
    registry: TeamRegistryService | None,
    allow_alias_enrichment: bool = True,
    legacy_team_map: Mapping[str, str] | None = None,
    transition_report: MutableMapping[str, Any] | None = None,
) -> TeamNormalizationResult:
    """
    Resolve one team field to a 3-letter abbreviation or preserve the original on failure.
    """
    raw = "" if _blankish(value) else str(value).strip()
    if not raw:
        return TeamNormalizationResult(output_value="", original_value="", resolved=True)

    legacy = legacy_team_map if legacy_team_map is not None else LEGACY_TEAM_MAP

    def bump(key: str, amount: int = 1) -> None:
        if transition_report is not None:
            transition_report[key] = int(transition_report.get(key, 0) or 0) + amount

    token_upper = raw.upper()
    if len(token_upper) == 3 and token_upper.isalpha() and registry and registry.is_known_abbreviation(token_upper):
        bump("passthrough_hits")
        if transition_report is not None:
            transition_report.setdefault("resolved_examples", {})
            if isinstance(transition_report["resolved_examples"], dict):
                transition_report["resolved_examples"].setdefault(raw, token_upper)
        return TeamNormalizationResult(
            output_value=token_upper,
            original_value=raw,
            resolved=True,
            resolution_source="passthrough",
        )

    resolved_abbr: str | None = None
    if registry is not None:
        if allow_alias_enrichment:
            team = registry.resolve_team_reference(raw)
        else:
            team = registry.resolve_team_reference_safe(raw, allow_alias_enrichment=False)
        if team:
            resolved_abbr = str(team.get("abbreviation", "")).strip() or None

    if resolved_abbr:
        bump("registry_hits")
        if transition_report is not None:
            transition_report.setdefault("resolved_examples", {})
            if isinstance(transition_report["resolved_examples"], dict):
                transition_report["resolved_examples"].setdefault(raw, resolved_abbr)
        return TeamNormalizationResult(
            output_value=resolved_abbr,
            original_value=raw,
            resolved=True,
            resolution_source="registry",
        )

    fallback = legacy.get(raw)
    if fallback:
        bump("team_map_fallbacks")
        if transition_report is not None:
            transition_report.setdefault("fallback_examples", {})
            if isinstance(transition_report["fallback_examples"], dict):
                transition_report["fallback_examples"].setdefault(raw, fallback)
        return TeamNormalizationResult(
            output_value=fallback,
            original_value=raw,
            resolved=True,
            resolution_source="legacy_team_map",
        )

    bump("unresolved_inputs")
    if transition_report is not None:
        unresolved = transition_report.setdefault("unresolved_examples", [])
        if isinstance(unresolved, set):
            unresolved.add(raw)
        elif isinstance(unresolved, list) and raw not in unresolved:
            unresolved.append(raw)

    warning = f"unknown team (no registry match): {raw!r}"
    return TeamNormalizationResult(
        output_value=raw,
        original_value=raw,
        resolved=False,
        resolution_source="unresolved",
        warning=warning,
    )


def resolve_team_abbreviation_with_bridge(
    value: object,
    *,
    registry_service: TeamRegistryService | None,
    allow_alias_enrichment: bool,
    transition_report: dict[str, Any],
    legacy_team_map: Mapping[str, str] | None = None,
) -> object:
    """
    Kiron templating-compatible wrapper (pandas cell in → abbreviated str out).
    """
    result = normalize_team_value_to_abbreviation(
        value,
        registry=registry_service,
        allow_alias_enrichment=allow_alias_enrichment,
        legacy_team_map=legacy_team_map,
        transition_report=transition_report,
    )
    return result.output_value


def canonical_team_code_set(codes: Iterable[object]) -> frozenset[str]:
    """Uppercase 3-letter (or any non-blank) team tokens for unordered set comparison."""
    out: set[str] = set()
    for code in codes:
        token = str(code or "").strip().upper()
        if token:
            out.add(token)
    return frozenset(out)


def metadata_home_away_team_set(row: Mapping[str, str]) -> frozenset[str]:
    """Canonical unordered pair from Home/Away metadata (actual match semantics)."""
    return canonical_team_code_set(
        (
            row.get("Home Team", ""),
            row.get("Away Team", ""),
        )
    )


def filename_team_set_from_parsed(parsed: Mapping[str, Any]) -> frozenset[str]:
    """Unordered team pair encoded in filename (alphabetical positions, not Home/Away)."""
    teams = parsed.get("team_abbreviations")
    if isinstance(teams, list) and teams:
        return canonical_team_code_set(teams)
    return canonical_team_code_set(
        (
            parsed.get("first_team_abbreviation", ""),
            parsed.get("second_team_abbreviation", ""),
        )
    )


def validate_inspired_row_teams_vs_filename(
    filename: str,
    row: Mapping[str, str],
    *,
    registry: TeamRegistryService,
) -> list[str]:
    """
  After normalization, verify the filename's two team codes match metadata Home/Away as an
  **unordered set**. Filename order is alphabetical only and must not be compared positionally
  to Home vs Away.
    """
    parsed = registry.parse_filename_metadata(filename)
    if not parsed.get("is_valid"):
        return []

    warnings: list[str] = []
    fn_teams = filename_team_set_from_parsed(parsed)
    home_away_teams = metadata_home_away_team_set(row)

    if not parsed.get("alphabetical_order_ok", True):
        first = str(parsed.get("first_team_abbreviation", "")).strip().upper()
        second = str(parsed.get("second_team_abbreviation", "")).strip().upper()
        warnings.append(
            f"filename team codes not in alphabetical order ({first!r} before {second!r}); "
            "expected deterministic ALPHABETICAL_TEAM_A_TEAM_B ordering"
        )

    if home_away_teams and fn_teams and home_away_teams != fn_teams:
        warnings.append(
            "filename team pair "
            f"{sorted(fn_teams)!r} does not match metadata Home/Away pair {sorted(home_away_teams)!r} "
            "(filename uses alphabetical team order, not Home/Away position)"
        )

    for col in ("Attacking Team", "Defending Team"):
        val = str(row.get(col, "")).strip().upper()
        if val and fn_teams and val not in fn_teams:
            warnings.append(f"{col} {val!r} is not one of the filename teams {sorted(fn_teams)!r}")

    return warnings


def new_transition_report() -> dict[str, Any]:
    return {
        "registry_hits": 0,
        "team_map_fallbacks": 0,
        "passthrough_hits": 0,
        "unresolved_inputs": 0,
        "resolved_examples": {},
        "fallback_examples": {},
        "unresolved_examples": [],
    }
