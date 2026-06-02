"""Generate INSPIRED QC SUMMARY text report for delivery runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass
class InspiredQcSummary:
    files_processed: int = 0
    audio_codec_ok: bool = True
    audio_sample_rate_ok: bool = True
    audio_channels_ok: bool = True
    audio_bit_depth_ok: bool = True
    metadata_filename_rules_ok: bool = True
    metadata_goal_rules_ok: bool = True
    metadata_team_rules_ok: bool = True
    metadata_date_rules_ok: bool = True
    parity_frame_alignment_ok: bool = True
    video_container_ok: bool = True
    video_codec_ok: bool = True
    video_no_audio_ok: bool = True
    video_fps_ok: bool = True
    video_fps_consistency_ok: bool = True
    audio_duration_ok: bool = True
    warnings: int = 0
    errors: int = 0
    delivery_status: str = "PASS"
    detail_lines: list[str] = field(default_factory=list)

    def compute_status(self) -> None:
        checks = [
            self.audio_codec_ok,
            self.audio_sample_rate_ok,
            self.audio_channels_ok,
            self.audio_bit_depth_ok,
            self.audio_duration_ok,
            self.video_container_ok,
            self.video_codec_ok,
            self.video_no_audio_ok,
            self.video_fps_ok,
            self.video_fps_consistency_ok,
            self.metadata_filename_rules_ok,
            self.metadata_goal_rules_ok,
            self.parity_frame_alignment_ok,
        ]
        self.delivery_status = "PASS" if all(checks) and self.errors == 0 else "FAIL"


def render_inspired_qc_summary(summary: InspiredQcSummary) -> str:
    summary.compute_status()
    tick = lambda ok: "✓" if ok else "✗"

    lines = [
        "INSPIRED QC SUMMARY",
        "",
        f"FILES PROCESSED: {summary.files_processed}",
        "",
        "Audio",
        f"{tick(summary.audio_codec_ok)} PCM_S16LE",
        f"{tick(summary.audio_sample_rate_ok)} 48000 Hz",
        f"{tick(summary.audio_channels_ok)} Mono",
        f"{tick(summary.audio_bit_depth_ok)} 16-bit",
        f"{tick(summary.audio_duration_ok)} Audio Duration ≤ Video",
        "",
        "Video",
        f"{tick(summary.video_container_ok)} MP4 Container",
        f"{tick(summary.video_codec_ok)} H264",
        f"{tick(summary.video_no_audio_ok)} No Audio Streams",
        f"{tick(summary.video_fps_ok)} 25fps or 50fps",
        f"{tick(summary.video_fps_consistency_ok)} Consistent Frame Rate",
        "",
        "Metadata",
        f"{tick(summary.metadata_filename_rules_ok)} Filename Rules",
        f"{tick(summary.metadata_goal_rules_ok)} Goal Rules",
        f"{tick(summary.metadata_team_rules_ok)} Team Rules",
        f"{tick(summary.metadata_date_rules_ok)} Date Rules",
        "",
        "Parity",
        f"{tick(summary.parity_frame_alignment_ok)} MP4 / COM / CFX Matching",
        "",
        f"Warnings: {summary.warnings}",
        f"Errors: {summary.errors}",
        "",
        f"DELIVERY STATUS: {summary.delivery_status}",
    ]
    if summary.detail_lines:
        lines.extend(["", "Details:", *summary.detail_lines])
    return "\n".join(lines) + "\n"


def build_inspired_qc_summary_from_run(
    *,
    files_processed: int,
    media_rows: list[dict[str, object]],
    metadata_qc_result: object | None,
    video_spec_ok: bool,
    audio_spec_ok: bool,
    frame_alignment_ok: bool,
    warnings_by_filename: dict[str, list[str]],
    unknown_team_count: int,
) -> InspiredQcSummary:
    summary = InspiredQcSummary(files_processed=files_processed)

    def _any_wav_validation_failed(prefix: str) -> bool:
        for row in media_rows:
            if str(row.get(f"{prefix}_ok", "")).strip().casefold() != "yes":
                continue
            if str(row.get(f"{prefix}_validation_ok", "")).lower() != "yes":
                return True
        return False

    wav_ok = (
        audio_spec_ok
        and not _any_wav_validation_failed("com_wav")
        and not _any_wav_validation_failed("cfx_wav")
    )
    summary.audio_codec_ok = wav_ok
    summary.audio_sample_rate_ok = wav_ok
    summary.audio_channels_ok = wav_ok
    summary.audio_bit_depth_ok = wav_ok
    summary.audio_duration_ok = audio_spec_ok and wav_ok
    summary.video_container_ok = video_spec_ok
    summary.video_codec_ok = video_spec_ok
    summary.video_no_audio_ok = video_spec_ok
    summary.video_fps_ok = video_spec_ok
    summary.video_fps_consistency_ok = video_spec_ok
    summary.parity_frame_alignment_ok = frame_alignment_ok

    if metadata_qc_result is not None:
        issues = getattr(metadata_qc_result, "issues", []) or []
        filename_rule_ids = {
            "GOAL_FILENAME_G_REQUIRES_GOAL_SCORED_TRUE",
            "GOAL_FILENAME_O_REQUIRES_GOAL_SCORED_FALSE",
            "GOAL_SCORED_TRUE_REQUIRES_FILENAME_G",
        }
        goal_rule_ids = {
            "GOAL_ACTION_MISS_REQUIRES_FALSE",
            "GOAL_ACTION_SAVE_REQUIRES_FALSE",
            "GOAL_SCORED_TRUE_REQUIRES_GOAL_TYPE",
            "GOAL_SCORED_TRUE_REQUIRES_GOAL_ACTION",
            "GOAL_TYPE_REQUIRES_GOAL_SCORED_TRUE",
        }
        date_rule_ids = {"DATE_MATCH_DATE_REQUIRED"}
        errors = [i for i in issues if getattr(i, "severity", "") == "error"]
        warnings = [i for i in issues if getattr(i, "severity", "") == "warning"]
        summary.errors += len(errors)
        summary.warnings += len(warnings)
        summary.metadata_filename_rules_ok = not any(
            getattr(i, "rule_id", "") in filename_rule_ids and getattr(i, "severity", "") == "error" for i in issues
        )
        summary.metadata_goal_rules_ok = not any(
            getattr(i, "rule_id", "") in goal_rule_ids and getattr(i, "severity", "") == "error" for i in issues
        )
        summary.metadata_date_rules_ok = not any(
            getattr(i, "rule_id", "") in date_rule_ids and getattr(i, "severity", "") == "error" for i in issues
        )
    else:
        summary.metadata_filename_rules_ok = True
        summary.metadata_goal_rules_ok = True
        summary.metadata_date_rules_ok = True

    team_warns = sum(
        1
        for msgs in warnings_by_filename.values()
        for m in msgs
        if "team" in m.casefold() or "Home/Away" in m or "filename team pair" in m
    )
    summary.metadata_team_rules_ok = team_warns == 0 and unknown_team_count == 0
    summary.warnings += team_warns + unknown_team_count

    if not audio_spec_ok:
        summary.errors += 1
        summary.detail_lines.append("Audio specification QC failed.")
    if not video_spec_ok:
        summary.errors += 1
        summary.detail_lines.append("Video specification QC failed.")
    if not frame_alignment_ok:
        summary.errors += 1
        summary.detail_lines.append("Frame alignment parity QC failed.")

    summary.compute_status()
    return summary


def write_inspired_qc_summary(path: Path, summary: InspiredQcSummary) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_inspired_qc_summary(summary), encoding="utf-8")
        return True
    except OSError:
        return False
