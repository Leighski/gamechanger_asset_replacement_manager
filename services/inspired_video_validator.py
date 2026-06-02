"""
Inspired delivery packaged MP4 validation (H264, no audio, 25/50 fps).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

INSPIRED_VIDEO_CODEC = "h264"
INSPIRED_ALLOWED_FPS: tuple[float, ...] = (25.0, 50.0)
INSPIRED_MP4_CONTAINERS = {"mp4", "mov", "m4v", "isom", "iso6", "iso2"}

FFPROBE_TIMEOUT_SEC = 180


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


def _ffprobe_json(path: Path) -> dict | None:
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
            timeout=FFPROBE_TIMEOUT_SEC,
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


def _fps_is_inspired_allowed(fps: float | None) -> bool:
    if fps is None:
        return False
    return any(abs(fps - allowed) <= 0.05 for allowed in INSPIRED_ALLOWED_FPS)


def _normalize_delivery_fps(fps: float) -> float:
    for allowed in INSPIRED_ALLOWED_FPS:
        if abs(fps - allowed) <= 0.05:
            return allowed
    return round(fps, 3)


def probe_media_duration_seconds(path: Path) -> float | None:
    doc = _ffprobe_json(path)
    if not doc:
        return None
    fmt = doc.get("format")
    if isinstance(fmt, dict):
        try:
            d = float(fmt.get("duration"))
            if d >= 0:
                return d
        except (TypeError, ValueError):
            pass
    streams = doc.get("streams")
    if isinstance(streams, list):
        for s in streams:
            if not isinstance(s, dict):
                continue
            try:
                d = float(s.get("duration"))
                if d >= 0:
                    return d
            except (TypeError, ValueError):
                continue
    return None


def validate_inspired_mp4(path: Path) -> dict[str, str]:
    """Validate packaged video-only MP4 against Inspired video specification."""
    fields: dict[str, str] = {
        "container": "",
        "codec": "",
        "resolution": "",
        "fps": "",
        "audio_stream_count": "",
        "audio_absent": "",
        "validation_ok": "no",
        "validation_notes": "",
        "failure_reason": "",
    }
    doc = _ffprobe_json(path)
    if not doc:
        fields["validation_notes"] = "ffprobe failed or file missing"
        fields["failure_reason"] = "MP4 probe failed or file missing"
        return fields

    fmt = doc.get("format") if isinstance(doc.get("format"), dict) else {}
    fmt_name = str(fmt.get("format_name", "") or "").lower()
    fields["container"] = fmt_name or Path(path).suffix.lstrip(".").lower()
    container_tokens = {t.strip() for t in fmt_name.split(",") if t.strip()}
    if container_tokens and not (container_tokens & INSPIRED_MP4_CONTAINERS):
        fields["validation_notes"] = f"container {fmt_name!r} (expected MP4)"
        fields["failure_reason"] = f"container is not MP4 ({fmt_name!r})"

    notes: list[str] = []
    failures: list[str] = []
    if fields["validation_notes"]:
        notes.append(fields["validation_notes"])
        failures.append(fields["failure_reason"])

    streams = doc.get("streams")
    video: dict | None = None
    audio_streams = 0
    if isinstance(streams, list):
        for s in streams:
            if not isinstance(s, dict):
                continue
            if s.get("codec_type") == "video" and video is None:
                video = s
            elif s.get("codec_type") == "audio":
                audio_streams += 1

    fields["audio_stream_count"] = str(audio_streams)
    fields["audio_absent"] = "yes" if audio_streams == 0 else "no"
    if audio_streams > 0:
        notes.append(f"unexpected audio stream(s): {audio_streams}")
        failures.append(f"video contains {audio_streams} audio stream(s); expected none")

    if not video:
        fields["validation_notes"] = "no video stream"
        fields["failure_reason"] = "MP4 has no video stream"
        return fields

    codec = str(video.get("codec_name", "")).lower()
    fields["codec"] = codec
    if codec != INSPIRED_VIDEO_CODEC:
        notes.append(f"codec {codec} (expected {INSPIRED_VIDEO_CODEC})")
        failures.append(f"codec is {codec!r} (expected H264)")

    w, h = int(video.get("width") or 0), int(video.get("height") or 0)
    fields["resolution"] = f"{w}x{h}"
    fps = parse_frame_rate(video.get("avg_frame_rate")) or parse_frame_rate(video.get("r_frame_rate"))
    fields["fps"] = f"{fps:.3f}" if fps else ""
    if not _fps_is_inspired_allowed(fps):
        notes.append(f"fps {fields['fps']} (expected 25 or 50)")
        failures.append(f"frame rate {fields['fps'] or 'unknown'} is not 25fps or 50fps")

    ok = (
        audio_streams == 0
        and codec == INSPIRED_VIDEO_CODEC
        and _fps_is_inspired_allowed(fps)
        and not (container_tokens and not (container_tokens & INSPIRED_MP4_CONTAINERS))
    )
    fields["validation_ok"] = "yes" if ok and not notes else "no"
    if notes:
        fields["validation_notes"] = "; ".join(notes)
    if failures:
        fields["failure_reason"] = "; ".join(failures)
    return fields


def validate_delivery_mp4_fps_consistency(media_rows: list[dict[str, object]]) -> tuple[bool, str, float | None]:
    """
    All packaged MP4s in one delivery must share the same frame rate (25 or 50).
    Returns (passed, message, canonical_fps).
    """
    seen: dict[float, list[str]] = {}
    for row in media_rows:
        if str(row.get("video_encode_ok", "")).strip().casefold() != "yes":
            continue
        mp4_path = Path(str(row.get("output_video", "")))
        if not mp4_path.is_file():
            continue
        val = validate_inspired_mp4(mp4_path)
        fps_raw = val.get("fps", "")
        try:
            fps = float(fps_raw)
        except (TypeError, ValueError):
            continue
        canon = _normalize_delivery_fps(fps)
        seen.setdefault(canon, []).append(str(row.get("engp_filename", mp4_path.name)))

    if not seen:
        return True, "", None
    if len(seen) == 1:
        only_fps = next(iter(seen))
        return True, "", only_fps

    parts = [f"{fps}fps ({len(files)} clip(s))" for fps, files in sorted(seen.items())]
    return False, f"Mixed frame rates in delivery: {', '.join(parts)}", None


def validate_audio_duration_vs_mp4(
    wav_path: Path,
    mp4_path: Path,
    *,
    label: str = "WAV",
) -> dict[str, str]:
    """COM/CFX WAV duration must not exceed corresponding packaged MP4 duration."""
    out: dict[str, str] = {
        "wav_duration": "",
        "mp4_duration": "",
        "duration_ok": "no",
        "validation_notes": "",
        "failure_reason": "",
    }
    wav_d = probe_media_duration_seconds(wav_path)
    mp4_d = probe_media_duration_seconds(mp4_path)
    if wav_d is not None:
        out["wav_duration"] = f"{wav_d:.6f}"
    if mp4_d is not None:
        out["mp4_duration"] = f"{mp4_d:.6f}"
    if wav_d is None or mp4_d is None:
        out["validation_notes"] = "could not probe WAV or MP4 duration"
        out["failure_reason"] = "could not probe WAV or MP4 duration for comparison"
        return out
    if wav_d > mp4_d + 0.001:
        out["validation_notes"] = f"wav_duration {wav_d:.3f}s > mp4_duration {mp4_d:.3f}s"
        out["failure_reason"] = "Audio duration exceeds corresponding video duration."
        return out
    out["duration_ok"] = "yes"
    return out
