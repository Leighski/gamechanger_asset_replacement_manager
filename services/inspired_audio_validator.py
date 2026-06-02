"""
Inspired delivery WAV specification validation (PCM_S16LE, 48000 Hz, mono, 16-bit).
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

INSPIRED_WAV_SAMPLE_RATE = 48000
INSPIRED_WAV_CHANNELS = 1
INSPIRED_WAV_CODEC = "pcm_s16le"
INSPIRED_WAV_BIT_DEPTH = 16
INSPIRED_WAV_BITRATE_BPS = 768_000  # 48000 * 16 * 1
INSPIRED_WAV_BITRATE_KBPS = 768

FFPROBE_TIMEOUT_SEC = 180


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


def validate_inspired_wav(path: Path) -> dict[str, str]:
    """
    Validate packaged WAV against Inspired audio specification.

    Returns fields including Sample Rate, Channels, Codec, Bit Depth, Bitrate,
    validation_ok (yes/no), validation_notes, and failure_reason (operator-facing).
    """
    fields: dict[str, str] = {
        "sample_rate": "",
        "channels": "",
        "codec": "",
        "bit_depth": "",
        "bitrate": "",
        "duration": "",
        "validation_ok": "no",
        "validation_notes": "",
        "failure_reason": "",
    }
    doc = _ffprobe_json(path)
    if not doc:
        fields["validation_notes"] = "ffprobe failed or file missing"
        fields["failure_reason"] = "WAV probe failed or file missing"
        return fields

    streams = doc.get("streams")
    audio: dict | None = None
    if isinstance(streams, list):
        for s in streams:
            if isinstance(s, dict) and s.get("codec_type") == "audio":
                audio = s
                break
    if not audio:
        fields["validation_notes"] = "no audio stream"
        fields["failure_reason"] = "WAV has no audio stream"
        return fields

    fmt = doc.get("format") if isinstance(doc.get("format"), dict) else {}

    fields["sample_rate"] = str(audio.get("sample_rate", ""))
    fields["codec"] = str(audio.get("codec_name", ""))
    fields["channels"] = str(audio.get("channels", ""))
    bps = audio.get("bits_per_sample")
    if bps is not None and str(bps).strip():
        fields["bit_depth"] = str(int(float(bps)))
    elif str(audio.get("sample_fmt", "")).lower() in ("s16", "s16p"):
        fields["bit_depth"] = "16"

    br = fmt.get("bit_rate") or audio.get("bit_rate")
    if br is not None:
        try:
            fields["bitrate"] = str(int(float(br)))
        except (TypeError, ValueError):
            fields["bitrate"] = str(br)

    dur = audio.get("duration") or fmt.get("duration")
    fields["duration"] = str(dur) if dur is not None else ""

    notes: list[str] = []
    failure_parts: list[str] = []

    try:
        sr = int(float(fields["sample_rate"]))
    except (TypeError, ValueError):
        sr = 0
    if sr != INSPIRED_WAV_SAMPLE_RATE:
        notes.append(f"sample_rate {sr} (expected {INSPIRED_WAV_SAMPLE_RATE})")
        failure_parts.append(f"sample rate is {sr} Hz (expected {INSPIRED_WAV_SAMPLE_RATE} Hz)")

    try:
        ch = int(float(fields["channels"]))
    except (TypeError, ValueError):
        ch = 0
    if ch != INSPIRED_WAV_CHANNELS:
        notes.append(f"channels {ch} (expected {INSPIRED_WAV_CHANNELS})")
        if ch == 2:
            failure_parts.append("WAV is stereo. Inspired specification requires mono.")
        else:
            failure_parts.append(f"channel count is {ch} (expected mono)")

    codec = str(fields["codec"]).lower()
    if codec != INSPIRED_WAV_CODEC:
        notes.append(f"codec {fields['codec']} (expected {INSPIRED_WAV_CODEC})")
        failure_parts.append(f"codec is {fields['codec']!r} (expected {INSPIRED_WAV_CODEC})")

    if fields["bit_depth"]:
        try:
            bd = int(fields["bit_depth"])
            if bd != INSPIRED_WAV_BIT_DEPTH:
                notes.append(f"bit_depth {bd} (expected {INSPIRED_WAV_BIT_DEPTH})")
                failure_parts.append(f"bit depth is {bd}-bit (expected 16-bit)")
        except ValueError:
            pass

    ok = (
        sr == INSPIRED_WAV_SAMPLE_RATE
        and ch == INSPIRED_WAV_CHANNELS
        and codec == INSPIRED_WAV_CODEC
        and (not fields["bit_depth"] or fields["bit_depth"] == str(INSPIRED_WAV_BIT_DEPTH))
    )
    fields["validation_ok"] = "yes" if ok else "no"
    fields["validation_notes"] = "; ".join(notes)
    fields["failure_reason"] = "; ".join(failure_parts)
    return fields


def wav_spec_failure_message(label: str, fields: dict[str, str]) -> str:
    """Operator-facing delivery failure line."""
    reason = str(fields.get("failure_reason", "")).strip()
    if reason:
        return f"Delivery failed: {label} — {reason}"
    notes = str(fields.get("validation_notes", "")).strip()
    return f"Delivery failed: {label} does not meet Inspired WAV specification ({notes or 'validation failed'})."


def audit_wav_pass_fail(fields: dict[str, str]) -> str:
    return "PASS" if str(fields.get("validation_ok", "")).lower() == "yes" else "FAIL"
