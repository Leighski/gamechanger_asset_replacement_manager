# Gamechanger Rename Manager

Production emergency utility for **transactional media renaming** and **integrity repair** across Iconik and AWS S3 (MAIN / CFX / MT variants).

## Features (MVP)

- Dark CustomTkinter GUI: search, thumbnail preview, rename planner, dry-run, live console
- Iconik search by filename or asset ID (explicit asset selection required)
- Integrity warnings (title/file_set mismatch, missing S3, duplicates, shared keys, missing variants)
- Six-phase transactional rename with production-validated file_set PATCH:
  `files/v1/assets/{asset_id}/file_sets/{fileset_id}/`
- Dry-run mode showing exact planned S3 and Iconik operations
- JSON settings + audit logs

## Requirements

- macOS (developed for standalone `.app` packaging)
- Python 3.10+ for development
- `ffmpeg` / `ffprobe` on PATH (thumbnail fallback)
- Iconik API credentials and AWS S3 access

## Install (development)

```bash
cd gamechanger_rename_manager
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Settings

Stored at:

`~/Library/Application Support/Gamechanger Rename Manager/settings.json`

Configure Iconik base URL, App-ID, Auth Token, collection UUID, AWS keys, S3 bucket/prefix.

## Build standalone `.app` (PyInstaller)

From the repo root (with venv active and dependencies installed):

```bash
pip install pyinstaller
pyinstaller gamechanger_rename_manager/build/pyinstaller.spec
```

Output: `dist/Gamechanger Rename Manager.app`

Copy to another Mac — no Python install required. Ensure `ffmpeg` is available on target machines for local thumbnail fallback, or rely on Iconik proxy URLs.

## Project layout

```
gamechanger_rename_manager/
  config/       settings, theme
  services/     Iconik, S3, integrity, thumbnails, audit
  workflows/    transactional rename engine
  ui/           CustomTkinter app + settings dialog
  main.py
```

## Safety

- **Dry Run** is enabled by default.
- Rename actions require a **selected asset** from search results — never from typed filename alone.
- Review integrity warnings and transaction preview before disabling dry run.
