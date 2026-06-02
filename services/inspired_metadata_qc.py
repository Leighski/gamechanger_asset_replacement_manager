"""
Inspired delivery metadata QC — goal / filename / action consistency rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

_ENGP_GOAL_EVENT_RE = re.compile(r"_G_\d", re.IGNORECASE)
_ENGP_NON_GOAL_EVENT_RE = re.compile(r"_O_\d", re.IGNORECASE)


@dataclass
class MetadataQcIssue:
    filename: str
    rule_id: str
    severity: str  # error | warning
    message: str
    field: str = ""
    value: str = ""


@dataclass
class MetadataQcResult:
    issues: list[MetadataQcIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def passed(self) -> bool:
        return self.error_count == 0


def _filename_is_goal_clip(filename: str) -> bool:
    name = Path(filename).name
    if _ENGP_NON_GOAL_EVENT_RE.search(name):
        return False
    return bool(_ENGP_GOAL_EVENT_RE.search(name))


def _filename_is_non_goal_clip(filename: str) -> bool:
    return bool(_ENGP_NON_GOAL_EVENT_RE.search(Path(filename).name))


def _goal_scored_is_true(value: object) -> bool:
    t = str(value or "").strip().upper()
    return t in {"TRUE", "YES", "1", "Y", "T"}


def _goal_scored_is_false(value: object) -> bool:
    t = str(value or "").strip().upper()
    return t in {"FALSE", "NO", "0", "N", "F", ""}


def _action_tokens(action: str) -> set[str]:
    return {p.strip().casefold() for p in action.split(",") if p.strip()}


def validate_inspired_metadata_row(filename: str, row: Mapping[str, str]) -> list[MetadataQcIssue]:
    """Apply Inspired goal/filename/action metadata rules to one row."""
    issues: list[MetadataQcIssue] = []
    fn = Path(filename).name
    goal_scored = str(row.get("Goal Scored", "")).strip()
    action = str(row.get("Action", "")).strip()
    goal_type = str(row.get("Goal Type", "")).strip()
    match_date = str(row.get("Match Date", "")).strip()

    is_g = _filename_is_goal_clip(fn)
    is_o = _filename_is_non_goal_clip(fn)

    # Rule 1: filename G → Goal Scored YES/TRUE
    if is_g and not _goal_scored_is_true(goal_scored):
        issues.append(
            MetadataQcIssue(
                filename=fn,
                rule_id="GOAL_FILENAME_G_REQUIRES_GOAL_SCORED_TRUE",
                severity="error",
                message="Filename contains _G_<n> but Goal Scored is not TRUE/YES",
                field="Goal Scored",
                value=goal_scored,
            )
        )

    # Rule 2: filename O → Goal Scored NO/FALSE
    if is_o and not _goal_scored_is_false(goal_scored):
        issues.append(
            MetadataQcIssue(
                filename=fn,
                rule_id="GOAL_FILENAME_O_REQUIRES_GOAL_SCORED_FALSE",
                severity="error",
                message="Filename contains _O_<n> but Goal Scored is not FALSE/NO",
                field="Goal Scored",
                value=goal_scored,
            )
        )

    action_tokens = _action_tokens(action)

    # Rule 3: Action Miss → Goal Scored FALSE
    if "miss" in action_tokens and not _goal_scored_is_false(goal_scored):
        issues.append(
            MetadataQcIssue(
                filename=fn,
                rule_id="GOAL_ACTION_MISS_REQUIRES_FALSE",
                severity="error",
                message="Action contains Miss but Goal Scored is not FALSE/NO",
                field="Goal Scored",
                value=goal_scored,
            )
        )

    # Rule 4: Action Save → Goal Scored FALSE
    if "save" in action_tokens and not _goal_scored_is_false(goal_scored):
        issues.append(
            MetadataQcIssue(
                filename=fn,
                rule_id="GOAL_ACTION_SAVE_REQUIRES_FALSE",
                severity="error",
                message="Action contains Save but Goal Scored is not FALSE/NO",
                field="Goal Scored",
                value=goal_scored,
            )
        )

    # Rule 5: Goal Scored YES → filename must contain G
    if _goal_scored_is_true(goal_scored) and not is_g:
        issues.append(
            MetadataQcIssue(
                filename=fn,
                rule_id="GOAL_SCORED_TRUE_REQUIRES_FILENAME_G",
                severity="error",
                message="Goal Scored is TRUE/YES but filename has no _G_<n> token",
                field="Goal Scored",
                value=goal_scored,
            )
        )

    # Rule 6: Goal Scored YES → Goal Type populated
    if _goal_scored_is_true(goal_scored) and not goal_type:
        issues.append(
            MetadataQcIssue(
                filename=fn,
                rule_id="GOAL_SCORED_TRUE_REQUIRES_GOAL_TYPE",
                severity="error",
                message="Goal Scored is TRUE/YES but Goal Type is blank",
                field="Goal Type",
                value=goal_type,
            )
        )

    # Rule 7: Goal Scored YES → Action must represent a Goal
    if _goal_scored_is_true(goal_scored):
        has_goal_action = "goal" in action_tokens or action.casefold() == "goal"
        if not has_goal_action:
            issues.append(
                MetadataQcIssue(
                    filename=fn,
                    rule_id="GOAL_SCORED_TRUE_REQUIRES_GOAL_ACTION",
                    severity="error",
                    message="Goal Scored is TRUE/YES but Action does not represent a Goal",
                    field="Action",
                    value=action,
                )
            )

    # Rule 8: Goal Type populated → Goal Scored YES/TRUE
    if goal_type and not _goal_scored_is_true(goal_scored):
        issues.append(
            MetadataQcIssue(
                filename=fn,
                rule_id="GOAL_TYPE_REQUIRES_GOAL_SCORED_TRUE",
                severity="error",
                message="Goal Type is populated but Goal Scored is not TRUE/YES",
                field="Goal Scored",
                value=goal_scored,
            )
        )

    # Date rule (QC summary): Match Date should be populated when row has team metadata
    home = str(row.get("Home Team", "")).strip()
    away = str(row.get("Away Team", "")).strip()
    if (home or away) and not match_date:
        issues.append(
            MetadataQcIssue(
                filename=fn,
                rule_id="DATE_MATCH_DATE_REQUIRED",
                severity="warning",
                message="Home/Away teams present but Match Date is blank",
                field="Match Date",
                value=match_date,
            )
        )

    return issues


def validate_inspired_metadata_batch(
    mp4_paths: list[Path],
    inspired_rows: list[dict[str, str]],
) -> MetadataQcResult:
    result = MetadataQcResult()
    for i, mp4 in enumerate(mp4_paths):
        row = inspired_rows[i] if i < len(inspired_rows) else {}
        result.issues.extend(validate_inspired_metadata_row(mp4.name, row))
    return result
