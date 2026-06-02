# Inspired audio specification — pre-remediation audit

Audit date: implementation baseline review of `Inspired_Delivery_Generator.py`.

## 1. WAV generation locations

| Location | Function | Role |
|----------|----------|------|
| ~4211 | `ffmpeg_extract_inspired_wav(mp4, out_com, …)` | COM WAV from ENGP source |
| ~4231 | `ffmpeg_extract_inspired_wav(cfx_src, out_cfx, …)` | CFX WAV from CFX-side source |
| ~3576 | `ffmpeg_extract_inspired_wav()` | FFmpeg command builder |

**Previous FFmpeg flags:** `-c:a pcm_s16le -ar 48000 -ac 2` (stereo).

## 2. WAV validation locations

| Location | Function | Role |
|----------|----------|------|
| ~3727 | `validate_packaged_wav_inspired()` | ffprobe post-encode validation |
| ~4247–4250 | `_run_media_generation_phase` | Calls validator after encode |
| `services/frame_alignment_validator.py` | Duration/frame parity only | Not codec/channel spec |

**Previous pass criteria:** `sample_rate == 48000`, `channels == 2`, `codec == pcm_s16le`.

## 3. Stereo assumptions found

| Line / area | Assumption |
|-------------|------------|
| `ffmpeg_extract_inspired_wav` docstring | “48 kHz **stereo** PCM s16le” |
| FFmpeg `-ac 2` | Forces stereo output |
| `validate_packaged_wav_inspired` | `ch == 2` required for PASS |
| No delivery block | Spec mismatch logged only in media report |

## 4. Metadata validation (pre-enhancement)

| Area | Rules |
|------|-------|
| `normalize_inspired_cell` | Country, team abbrev, goal time by `_G_`/`_O_` filename |
| `build_inspired_row` | Required column checks |
| `warnings_for_run_heuristic` | Goal time warnings on `_G_` clips |
| `build_delivery_validation_rows` | Per-clip media/metadata presence |
| Team QC | Unordered filename vs Home/Away pair |

**Missing before remediation:** Goal Scored ↔ filename `_G_`/`_O_` rules, Action Miss/Save rules, Goal Type/Action when Goal Scored TRUE.

## 5. QC report locations (pre-enhancement)

| Output | Path |
|--------|------|
| Media generation | `reports/media_generation_report.xlsx` |
| Delivery validation | `reports/delivery_validation_report.xlsx` |
| Frame alignment | `reports/frame_alignment_qc_report.txt` |
| Unknown teams | `reports/unknown_teams.csv` |
| Delivery summary | `delivery_summary.txt` |
| Delivery log | `delivery_log.txt` |

**Missing before remediation:** Dedicated metadata QC report, INSPIRED QC SUMMARY, audio spec delivery blocking.

## 6. Remediation applied

See `Inspired_Delivery_Generator.py` and `services/inspired_audio_validator.py` for mono generation, strict validation, delivery blocking, metadata QC, and `inspired_qc_summary.txt`. Historical audit: `Inspired_Audio_Audit.py`.
