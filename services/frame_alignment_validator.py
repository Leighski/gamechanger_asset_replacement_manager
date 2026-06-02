"""
Frame alignment QC for Inspired delivery — compare rendered MP4 frame count vs COM/CFX WAV lengths.

Used after all media renders complete and before delivery outputs are finalized.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Inspired delivery standard (matches goal-time conversion and packaged video).
INSPIRED_DELIVERY_FPS = 25.0
DEFAULT_FRAME_TOLERANCE = 1
FFPROBE_TIMEOUT_SEC = 180


@dataclass
class ClipFrameAlignment:
    """Per-clip probe results and pass/fail for frame alignment QC."""

    filename: str
    mp4_path: Path
    com_wav_path: Path | None
    cfx_wav_path: Path | None
    mp4_frames: int | None = None
    com_wav_frames: int | None = None
    cfx_wav_frames: int | None = None
    mp4_error: str = ""
    com_error: str = ""
    cfx_error: str = ""
    skipped_reason: str = ""
    passed: bool = True

    def format_mismatch_block(self) -> str:
        """Operator log block matching product spec."""
        lines = [
            "[ERROR] FRAME MISMATCH:",
            self.filename,
            "",
            f"MP4 Frames: {self.mp4_frames if self.mp4_frames is not None else 'n/a'}",
            f"CFX WAV Frames: {self.cfx_wav_frames if self.cfx_wav_frames is not None else 'n/a'}",
            f"COM WAV Frames: {self.com_wav_frames if self.com_wav_frames is not None else 'n/a'}",
        ]
        if self.mp4_error:
            lines.append(f"MP4 probe: {self.mp4_error}")
        if self.com_error:
            lines.append(f"COM probe: {self.com_error}")
        if self.cfx_error:
            lines.append(f"CFX probe: {self.cfx_error}")
        return "\n".join(lines)


@dataclass
class FrameAlignmentBatchResult:
    """Aggregate QC outcome for a full delivery run."""

    passed: bool
    clips: list[ClipFrameAlignment] = field(default_factory=list)
    log_blocks: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def mismatch_count(self) -> int:
        return sum(1 for c in self.clips if not c.passed and not c.skipped_reason)


def parse_frame_rate(value: object) -> float | None:
    if value is None:
        return None
    t = str(value).strip()
    if not t or t.upper() in ("N/A", "0/0", "NAN"):
        return None
    if "/" in t:
        a, _, b = t.partition("/")
        try:
            aa, bb = float(a), float(b)
            if bb == 0:
                return None
            out = aa / bb
            return out if out > 0 else None
        except ValueError:
            return None
    try:
        out = float(t)
        return out if out > 0 else None
    except ValueError:
        return None


def _ffprobe_json(path: Path, *, timeout_sec: float = FFPROBE_TIMEOUT_SEC) -> dict | None:
    if not shutil.which("ffprobe") or not path.is_file():
        return None
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-hide_banner",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        doc = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None
    return doc if isinstance(doc, dict) else None


def _duration_seconds_from_probe(doc: dict) -> tuple[float | None, str]:
    fmt = doc.get("format")
    if not isinstance(fmt, dict):
        return None, "no format section"
    dur_raw = fmt.get("duration")
    try:
        duration_s = float(dur_raw) if dur_raw is not None else None
    except (TypeError, ValueError):
        duration_s = None
    if duration_s is None or duration_s < 0 or math.isnan(duration_s):
        streams = doc.get("streams")
        if isinstance(streams, list):
            for s in streams:
                if not isinstance(s, dict):
                    continue
                try:
                    d = float(s.get("duration"))
                    if d >= 0 and not math.isnan(d):
                        return d, ""
                except (TypeError, ValueError):
                    continue
        return None, "invalid duration"
    return duration_s, ""


def probe_video_frame_count(path: Path, *, fps: float = INSPIRED_DELIVERY_FPS) -> tuple[int | None, str]:
    """
    Frame count from rendered MP4: prefer ``nb_frames`` on the video stream, else
    ``round(duration_seconds * fps)``.
    """
    doc = _ffprobe_json(path)
    if not doc:
        if not shutil.which("ffprobe"):
            return None, "ffprobe missing"
        if not path.is_file():
            return None, "file missing"
        return None, "ffprobe failed"

    video: dict | None = None
    streams = doc.get("streams")
    if isinstance(streams, list):
        for s in streams:
            if isinstance(s, dict) and s.get("codec_type") == "video":
                video = s
                break
    if not video:
        return None, "no video stream"

    nb = video.get("nb_frames")
    if nb is not None:
        try:
            n = int(str(nb).strip())
            if n >= 0:
                return n, ""
        except (TypeError, ValueError):
            pass

    duration_s, derr = _duration_seconds_from_probe(doc)
    if duration_s is None:
        return None, derr or "invalid duration"
    stream_fps = parse_frame_rate(video.get("avg_frame_rate")) or parse_frame_rate(video.get("r_frame_rate"))
    use_fps = stream_fps if stream_fps and stream_fps > 0 else fps
    return int(round(duration_s * use_fps)), ""


def probe_wav_frame_count(path: Path, *, fps: float = INSPIRED_DELIVERY_FPS) -> tuple[int | None, str]:
    """WAV duration via ffprobe → frame-equivalent count at delivery FPS."""
    doc = _ffprobe_json(path)
    if not doc:
        if not shutil.which("ffprobe"):
            return None, "ffprobe missing"
        if not path.is_file():
            return None, "file missing"
        return None, "ffprobe failed"
    duration_s, err = _duration_seconds_from_probe(doc)
    if duration_s is None:
        return None, err or "invalid duration"
    return int(round(duration_s * fps)), ""


def _within_tolerance(a: int, b: int, tolerance: int) -> bool:
    return abs(a - b) <= tolerance


def validate_clip_frame_alignment(
    *,
    filename: str,
    mp4_path: Path,
    com_wav_path: Path | None,
    cfx_wav_path: Path | None,
    require_cfx_wav: bool,
    fps: float = INSPIRED_DELIVERY_FPS,
    tolerance: int = DEFAULT_FRAME_TOLERANCE,
) -> ClipFrameAlignment:
    clip = ClipFrameAlignment(
        filename=filename,
        mp4_path=mp4_path,
        com_wav_path=com_wav_path,
        cfx_wav_path=cfx_wav_path,
    )

    if not mp4_path.is_file():
        clip.passed = False
        clip.mp4_error = "rendered MP4 missing"
        return clip

    clip.mp4_frames, clip.mp4_error = probe_video_frame_count(mp4_path, fps=fps)
    if clip.mp4_frames is None:
        clip.passed = False
        return clip

    if com_wav_path is None or not com_wav_path.is_file():
        clip.passed = False
        clip.com_error = "COM WAV missing"
        return clip

    clip.com_wav_frames, clip.com_error = probe_wav_frame_count(com_wav_path, fps=fps)
    if clip.com_wav_frames is None:
        clip.passed = False
        return clip

    if not _within_tolerance(clip.mp4_frames, clip.com_wav_frames, tolerance):
        clip.passed = False
        return clip

    if require_cfx_wav:
        if cfx_wav_path is None or not cfx_wav_path.is_file():
            clip.passed = False
            clip.cfx_error = "CFX WAV missing"
            return clip
        clip.cfx_wav_frames, clip.cfx_error = probe_wav_frame_count(cfx_wav_path, fps=fps)
        if clip.cfx_wav_frames is None:
            clip.passed = False
            return clip
        if not _within_tolerance(clip.mp4_frames, clip.cfx_wav_frames, tolerance):
            clip.passed = False
            return clip

    return clip


def _media_row_flag_ok(row: dict[str, object], key: str) -> bool:
    return str(row.get(key, "")).strip().casefold() == "yes"


def validate_delivery_frame_alignment(
    mp4_paths: list[Path],
    media_dir: Path,
    media_rows: list[dict[str, object]],
    *,
    fps: float = INSPIRED_DELIVERY_FPS,
    tolerance: int = DEFAULT_FRAME_TOLERANCE,
) -> FrameAlignmentBatchResult:
    """
    Validate every input ENGP whose video encode succeeded. Compare packaged MP4 vs COM/CFX WAV
    under ``media_dir``. Clips with failed video encode are reported and fail the batch.
    """
    by_name: dict[str, dict[str, object]] = {}
    for row in media_rows:
        fn = str(row.get("engp_filename", "")).strip()
        if fn:
            by_name[fn] = row

    clips: list[ClipFrameAlignment] = []
    log_blocks: list[str] = []

    for mp4 in mp4_paths:
        fn = mp4.name
        row = by_name.get(fn, {})
        out_mp4, out_com, out_cfx = (
            media_dir / fn,
            media_dir / f"{mp4.stem}_COM.wav",
            media_dir / f"{mp4.stem}_CFX.wav",
        )

        if not _media_row_flag_ok(row, "video_encode_ok"):
            clip = ClipFrameAlignment(
                filename=fn,
                mp4_path=out_mp4,
                com_wav_path=out_com,
                cfx_wav_path=out_cfx,
                passed=False,
                skipped_reason="video encode failed",
            )
            clip.mp4_error = "video not rendered successfully"
            clips.append(clip)
            log_blocks.append(
                f"[ERROR] FRAME ALIGNMENT SKIPPED (video failed): {fn}"
            )
            continue

        require_cfx = _media_row_flag_ok(row, "cfx_wav_ok")
        clip = validate_clip_frame_alignment(
            filename=fn,
            mp4_path=out_mp4,
            com_wav_path=out_com if _media_row_flag_ok(row, "com_wav_ok") else out_com,
            cfx_wav_path=out_cfx if require_cfx else None,
            require_cfx_wav=require_cfx,
            fps=fps,
            tolerance=tolerance,
        )
        clips.append(clip)
        if not clip.passed:
            log_blocks.append(clip.format_mismatch_block())

    passed = all(c.passed for c in clips) and bool(clips)
    if not clips:
        passed = False
        summary = "frame alignment QC: no clips to validate"
    elif passed:
        summary = f"frame alignment QC: passed ({len(clips)} clip(s), tolerance ±{tolerance} frame(s) @ {fps} fps)"
    else:
        summary = f"frame alignment QC: FAILED ({sum(1 for c in clips if not c.passed)} mismatch(es) of {len(clips)} clip(s))"

    return FrameAlignmentBatchResult(passed=passed, clips=clips, log_blocks=log_blocks, summary=summary)


def write_frame_alignment_qc_report(path: Path, result: FrameAlignmentBatchResult) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [result.summary, f"overall_passed: {result.passed}", ""]
        for clip in result.clips:
            lines.append(f"--- {clip.filename} ---")
            lines.append(f"passed: {clip.passed}")
            if clip.skipped_reason:
                lines.append(f"skipped: {clip.skipped_reason}")
            lines.append(f"MP4 Frames: {clip.mp4_frames}")
            lines.append(f"COM WAV Frames: {clip.com_wav_frames}")
            lines.append(f"CFX WAV Frames: {clip.cfx_wav_frames}")
            if clip.mp4_error:
                lines.append(f"mp4_error: {clip.mp4_error}")
            if clip.com_error:
                lines.append(f"com_error: {clip.com_error}")
            if clip.cfx_error:
                lines.append(f"cfx_error: {clip.cfx_error}")
            lines.append("")
        if result.log_blocks:
            lines.append("=== mismatch log blocks ===")
            lines.extend(result.log_blocks)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False
