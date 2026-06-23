# Gamechanger Asset Replacement Manager

Desktop application for safely replacing existing media files in S3 while preserving Iconik assets, metadata, file sets, and object relationships.

Replaces manual AWS CLI workflows for ENGP, Serie A, Serie B, Serie C, and Bulgarian football libraries.

## Requirements

- Python 3.13+
- AWS credentials (environment, `~/.aws/credentials`, or Settings tab)
- Network access to S3

## Install

```bash
cd gamechanger_asset_replacement_manager
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python app/main.py
```

## Workflow

1. Open the app
2. Select a path preset (or browse / drag-and-drop a source folder)
3. Select catalogue destination (ENGP, SERIE_A, SERIE_B, SERIE_C, BULGARIAN, or CUSTOM)
4. **Scan** — recursive discovery of `.mp4` / `.mov` files
5. Review filename sanitisation preview (AppleDouble, spaces, extension case)
6. **Run Pre-flight Validation** — S3 HEAD per file; REPLACE vs SKIP
7. Review upload preview counts
8. **Start Upload** — threaded boto3 uploads (replace existing only by default)
9. Audit reports written to `reports/`
10. Close

## Safety mode

Default: **Replace existing only**

- File exists in S3 → upload permitted (REPLACE)
- File missing in S3 → skip (prevents accidental new assets)

## Configuration

| File | Purpose |
|------|---------|
| `config/user_settings.json` | Source folder, last catalogue, sanitisation options |
| `config/path_presets.json` | Folder path presets |
| `config/catalogues.json` | Catalogue → S3 URI mappings |
| `config/aws_settings.json` | Optional explicit AWS keys |
| `logs/replacement.log` | Application log |
| `reports/replacement_report.csv` | Latest audit CSV |
| `reports/replacement_report.xlsx` | Latest audit Excel |

## Interface

Dark-mode operational UI inspired by professional media tools (Adobe / DaVinci style):

- Dashboard header with AWS bucket, catalogue, file count, and ready status
- Sidebar workflow navigation with future module placeholders
- Card-based sections with Gamechanger blue (`#007ACC`) accents
- Sortable, searchable validation tables with status icons (✓ ⚠ ✕)
- Upload preview stat cards and detailed progress (speed, ETA, success/failure counts)
- Tabbed **Preferences** dialog (General, AWS, Catalogues, Path Presets, Reports, Iconik)

## Architecture

```
app/          Application entry, logging
gui/          PySide6 UI, theme, widgets, background workers
services/     Discovery, sanitisation, S3, upload, reports
models/       Dataclasses for workflow state
config/       JSON configuration
reports/      Generated audit exports
logs/         Rotating log file
```

**Phase 2:** `services/iconik_verification.py` — stub for future Iconik asset lookup and preservation checks.

## Problem cases handled

- `._FRA_MNP_20240226_O_14-ITA.mp4` (AppleDouble)
- `FRA_MNP_20240226_O_14-ITA .mp4` (trailing space)
- `.DS_Store` / `Thumbs.db` ignored
- Duplicate clean filenames flagged
- Local-only files skipped when safety mode is on
- S3 size mismatch warnings in pre-flight table
