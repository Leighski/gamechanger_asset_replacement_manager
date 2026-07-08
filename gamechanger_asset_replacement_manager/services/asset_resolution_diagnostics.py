"""TEMPORARY diagnostics for asset resolution NOT_FOUND investigations.

Remove before production release. Mirrors resolution validation rules for tracing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.asset_resolution_service import (
    GOVERNANCE_WARNING_TITLE_FILENAME_MISMATCH,
)
from services.paths import REPORTS_DIR
from services.replacement_variant import ReplacementAssetType, detect_replacement_type

logger = logging.getLogger(__name__)


@dataclass
class CandidateDiagnostic:
    asset_id: str
    asset_title: str
    file_set_name: str
    title_matches_filename: bool
    file_set_matches_filename: bool
    in_raw_search: bool
    passes_file_set_filter: bool
    governance_warnings: list[str] = field(default_factory=list)
    rejection_rules: list[str] = field(default_factory=list)


@dataclass
class ResolutionDiagnosticReport:
    timestamp: str
    expected_filename: str
    asset_type: str
    search_payload: dict[str, Any]
    search_http_status: int
    raw_response_count: int
    raw_total: int | None
    raw_asset_ids: list[str]
    raw_titles: list[str]
    post_filter_file_set_count: int
    post_filter_file_set_ids: list[str]
    known_asset_id: str
    known_asset_in_raw_response: bool
    known_asset_in_file_set_filter: bool
    known_asset_direct_get_ok: bool
    asset_title: str
    file_set_name: str
    title_matches_filename: bool
    file_set_matches_filename: bool
    known_asset_direct_validation_rules: list[str]
    known_asset_governance_warnings: list[str]
    candidate_diagnostics: list[CandidateDiagnostic]
    alternative_searches: dict[str, dict[str, Any]]
    precise_rejection_point: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def diagnose_resolution(
    iconik: Any,
    *,
    expected_filename: str,
    asset_type: ReplacementAssetType,
    known_asset_id: str = "",
) -> ResolutionDiagnosticReport:
    """Trace the exact resolution path without modifying governance rules."""
    from services.iconik_verification import IconikVerificationService

    assert isinstance(iconik, IconikVerificationService)

    filename = expected_filename.strip()
    probe_id = known_asset_id.strip()

    payload = {"doc_types": ["assets"], "query": filename}
    code, raw_data, _text = iconik._post("search/v1/search/", json_body=payload)
    raw_objects: list[dict] = []
    raw_total: int | None = None
    if code == 200 and isinstance(raw_data, dict):
        raw_objects = raw_data.get("objects") or []
        raw_total = raw_data.get("total")

    raw_ids = [str(o.get("id") or "") for o in raw_objects]
    raw_titles = [str(o.get("title") or o.get("name") or "") for o in raw_objects]

    valid_ids: list[str] = []
    for obj in raw_objects:
        aid = str(obj.get("id") or "")
        rules, _file_set_name, _warnings = _validation_rules(
            iconik,
            asset_id=aid,
            hit=obj,
            expected_filename=filename,
            asset_type=asset_type,
        )
        if not any(rule.startswith("REJECT") for rule in rules):
            valid_ids.append(aid)

    alt_searches: dict[str, dict[str, Any]] = {}
    for query in (filename, f'title:"{filename}"', f'"{filename}"'):
        alt_payload = {"doc_types": ["assets"], "query": query}
        alt_code, alt_data, _ = iconik._post("search/v1/search/", json_body=alt_payload)
        alt_objs = alt_data.get("objects") or [] if isinstance(alt_data, dict) else []
        alt_searches[query] = {
            "http_status": alt_code,
            "count": len(alt_objs),
            "asset_ids": [str(o.get("id") or "") for o in alt_objs],
            "titles": [str(o.get("title") or o.get("name") or "") for o in alt_objs],
            "known_asset_present": (
                bool(probe_id) and any(str(o.get("id") or "") == probe_id for o in alt_objs)
            ),
        }

    candidate_diagnostics: list[CandidateDiagnostic] = []
    for obj in raw_objects:
        aid = str(obj.get("id") or "")
        title = str(obj.get("title") or obj.get("name") or "")
        rules, file_set_name, warnings = _validation_rules(
            iconik,
            asset_id=aid,
            hit=obj,
            expected_filename=filename,
            asset_type=asset_type,
        )
        candidate_diagnostics.append(
            CandidateDiagnostic(
                asset_id=aid,
                asset_title=title,
                file_set_name=file_set_name,
                title_matches_filename=_matches_filename(title, filename),
                file_set_matches_filename=_matches_filename(file_set_name, filename),
                in_raw_search=True,
                passes_file_set_filter=aid in valid_ids,
                governance_warnings=warnings,
                rejection_rules=rules,
            )
        )

    known_direct_ok = False
    known_title = ""
    known_file_set = ""
    known_title_matches = False
    known_file_set_matches = False
    known_direct_rules: list[str] = []
    known_warnings: list[str] = []
    if probe_id:
        try:
            asset_doc = iconik.get_asset(probe_id)
            known_direct_ok = True
            known_title = str(asset_doc.get("title") or asset_doc.get("name") or "")
            known_direct_rules, known_file_set, known_warnings = _validation_rules(
                iconik,
                asset_id=probe_id,
                hit=asset_doc,
                expected_filename=filename,
                asset_type=asset_type,
            )
            known_title_matches = _matches_filename(known_title, filename)
            known_file_set_matches = _matches_filename(known_file_set, filename)
        except Exception as exc:
            known_direct_rules = [f"DIRECT_GET_FAILED: {exc}"]

    rejection_point, summary = _summarize(
        filename=filename,
        raw_count=len(raw_objects),
        file_set_count=len(valid_ids),
        probe_id=probe_id,
        probe_in_raw=probe_id in raw_ids,
        probe_in_file_set=probe_id in valid_ids,
        known_title=known_title,
        known_file_set=known_file_set,
        known_direct_rules=known_direct_rules,
        alt_searches=alt_searches,
    )

    return ResolutionDiagnosticReport(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        expected_filename=filename,
        asset_type=asset_type.value,
        search_payload=payload,
        search_http_status=code,
        raw_response_count=len(raw_objects),
        raw_total=raw_total,
        raw_asset_ids=raw_ids,
        raw_titles=raw_titles,
        post_filter_file_set_count=len(valid_ids),
        post_filter_file_set_ids=valid_ids,
        known_asset_id=probe_id,
        known_asset_in_raw_response=probe_id in raw_ids,
        known_asset_in_file_set_filter=probe_id in valid_ids,
        known_asset_direct_get_ok=known_direct_ok,
        asset_title=known_title,
        file_set_name=known_file_set,
        title_matches_filename=known_title_matches,
        file_set_matches_filename=known_file_set_matches,
        known_asset_direct_validation_rules=known_direct_rules,
        known_asset_governance_warnings=known_warnings,
        candidate_diagnostics=candidate_diagnostics,
        alternative_searches=alt_searches,
        precise_rejection_point=rejection_point,
        summary=summary,
    )


def _matches_filename(value: str, expected_filename: str) -> bool:
    return value.strip().lower() == expected_filename.strip().lower()


def _validation_rules(
    iconik: Any,
    *,
    asset_id: str,
    hit: dict[str, Any],
    expected_filename: str,
    asset_type: ReplacementAssetType,
) -> tuple[list[str], str, list[str]]:
    """Mirror _validate_candidate checks for diagnostic output only."""
    rules: list[str] = []
    warnings: list[str] = []
    title = str(hit.get("title") or hit.get("name") or "").strip()
    if _matches_filename(title, expected_filename):
        rules.append("PASS title_matches_filename")
    else:
        rules.append(
            f"INFO title_differs_from_filename: asset_title={title!r} "
            f"expected={expected_filename!r}"
        )

    detected = detect_replacement_type(expected_filename)
    if detected != asset_type:
        rules.append(f"REJECT type_mismatch: detected={detected} expected={asset_type.value}")
    else:
        rules.append("PASS type_match")

    try:
        details = iconik.resolve_file_details(asset_id)
    except Exception as exc:
        rules.append(f"REJECT file_details_error: {exc}")
        return rules, "", warnings

    file_set_name = str(details.get("iconik_file_name") or details.get("original_filename") or "")
    if _matches_filename(file_set_name, expected_filename):
        rules.append(f"PASS file_set_matches_filename: {file_set_name!r}")
    else:
        rules.append(f"REJECT file_set_name_mismatch: file_set_name={file_set_name!r}")
        return rules, file_set_name, warnings

    if title.strip() != file_set_name.strip():
        warnings.append(GOVERNANCE_WARNING_TITLE_FILENAME_MISMATCH)
        rules.append(
            f"WARN {GOVERNANCE_WARNING_TITLE_FILENAME_MISMATCH}: "
            f"asset_title={title!r} file_set_name={file_set_name!r}"
        )
    else:
        rules.append("PASS title_matches_file_set_name")

    iconik_s3_key = str(details.get("iconik_s3_key") or "")
    if not iconik_s3_key:
        rules.append("REJECT empty_iconik_s3_key")
    else:
        rules.append(f"PASS iconik_s3_key={iconik_s3_key}")

    return rules, file_set_name, warnings


def _summarize(
    *,
    filename: str,
    raw_count: int,
    file_set_count: int,
    probe_id: str,
    probe_in_raw: bool,
    probe_in_file_set: bool,
    known_title: str,
    known_file_set: str,
    known_direct_rules: list[str],
    alt_searches: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    if raw_count == 0:
        plain = alt_searches.get(filename, {})
        if plain.get("known_asset_present"):
            rejection = "SEARCH_STAGE: primary filename query returned 0 results"
            summary = (
                f"Iconik search for {filename!r} returned zero objects in the primary "
                f"query, but alternative queries find asset {probe_id}."
            )
            return rejection, summary

        return (
            "SEARCH_STAGE: zero results from filename query and alternatives",
            f"No Iconik search variant returned asset {probe_id} for {filename!r}.",
        )

    if file_set_count == 0:
        reject_rules = [r for r in known_direct_rules if r.startswith("REJECT")]
        if reject_rules:
            return (
                f"VALIDATION_STAGE: {reject_rules[0]}",
                "Search returned objects but none passed file_set.name validation.",
            )
        return (
            "FILTER_STAGE: raw hits present but file_set.name validation removed all",
            "Search returned objects but no candidate had a matching file_set.name.",
        )

    if probe_in_file_set or not probe_id:
        reject_rules = [r for r in known_direct_rules if r.startswith("REJECT")]
        if reject_rules:
            return f"VALIDATION_STAGE: {reject_rules[0]}", "; ".join(known_direct_rules)
        summary = "At least one asset passes file_set.name validation."
        if known_title and known_file_set and known_title != known_file_set:
            summary += (
                f" Asset title {known_title!r} differs from file set name "
                f"{known_file_set!r} ({GOVERNANCE_WARNING_TITLE_FILENAME_MISMATCH})."
            )
        return "VALIDATION_STAGE: would pass", summary

    return (
        "UNKNOWN: asset in search but not in file_set filter",
        f"probe_in_raw={probe_in_raw} probe_in_file_set={probe_in_file_set}",
    )


def write_diagnostic_report(
    report: ResolutionDiagnosticReport,
    *,
    reports_dir: Path | None = None,
) -> Path:
    out_dir = reports_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = report.expected_filename.replace("/", "_")
    path = out_dir / f"resolution_diagnostic_{safe_name}_{stamp}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    latest = out_dir / "resolution_diagnostic_latest.json"
    latest.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    logger.warning("[RESOLUTION-DIAG] Wrote %s — %s", path, report.summary)
    return path


def log_diagnostic_report(report: ResolutionDiagnosticReport) -> None:
    """Emit structured diagnostics to application log."""
    logger.warning("[RESOLUTION-DIAG] %s", report.summary)
    logger.warning("[RESOLUTION-DIAG] payload=%s", json.dumps(report.search_payload))
    logger.warning(
        "[RESOLUTION-DIAG] raw_count=%s file_set_count=%s "
        "asset_title=%r file_set_name=%r title_matches_filename=%s "
        "file_set_matches_filename=%s",
        report.raw_response_count,
        report.post_filter_file_set_count,
        report.asset_title,
        report.file_set_name,
        report.title_matches_filename,
        report.file_set_matches_filename,
    )
    for cand in report.candidate_diagnostics:
        logger.warning(
            "[RESOLUTION-DIAG] candidate %s asset_title=%r file_set_name=%r "
            "title_matches_filename=%s file_set_matches_filename=%s rules=%s",
            cand.asset_id,
            cand.asset_title,
            cand.file_set_name,
            cand.title_matches_filename,
            cand.file_set_matches_filename,
            cand.rejection_rules,
        )
    if report.known_asset_direct_validation_rules:
        logger.warning(
            "[RESOLUTION-DIAG] known_asset %s asset_title=%r file_set_name=%r rules=%s",
            report.known_asset_id,
            report.asset_title,
            report.file_set_name,
            report.known_asset_direct_validation_rules,
        )
