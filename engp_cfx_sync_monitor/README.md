# ENGP_CFX Sync Monitor

Lightweight always-on **CustomTkinter** GUI for monitoring the `com.gcs.engp_cfx_sync` LaunchAgent on a Mac mini.

## Features

- LaunchAgent running / loaded status (10s polling)
- Last successful and failed sync times (parsed from logs)
- Live sync and error log tails
- NAS mount check for ENGP_CLEANFX folder
- AWS connectivity check (`aws sts get-caller-identity`, optional S3 bucket probe)
- Manual sync, restart LaunchAgent, open logs folder
- Dark mode UI, rotating monitor log at `~/sync_logs/engp_cfx_monitor.log`

## Requirements

- macOS with the sync LaunchAgent installed
- Python 3.10+
- [AWS CLI](https://aws.amazon.com/cli/) in `PATH` (for S3 check)
- `customtkinter`

## Install

```bash
cd engp_cfx_sync_monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

From the **repository root** (parent of `engp_cfx_sync_monitor`):

```bash
pip install -r engp_cfx_sync_monitor/requirements.txt
python3 -m engp_cfx_sync_monitor.main
```

Or:

```bash
python3 engp_cfx_sync_monitor/main.py
```

## Configuration

Edit `engp_cfx_sync_monitor/config.py` or set environment variables:

| Variable | Purpose |
|----------|---------|
| `ENGP_CFX_S3_BUCKET` | Optional bucket for `aws s3 ls` probe |
| `ENGP_CFX_S3_PREFIX` | Optional prefix under the bucket |

Default paths:

| Item | Path |
|------|------|
| LaunchAgent | `com.gcs.engp_cfx_sync` |
| Sync log | `~/sync_logs/engp_cfx_sync.log` |
| Error log | `~/sync_logs/engp_cfx_error.log` |
| NAS | `/Volumes/03_EDITORIAL/.../ENGP_CLEANFX/` |

## Log parsing

Success/failure timestamps are detected using flexible patterns in `config.py` (e.g. `sync completed successfully`, `ERROR`, `sync failed`). Adjust patterns to match your sync script output if needed.

## Always-on (optional)

Run at login via a separate LaunchAgent or `open` from Login Items:

```bash
/usr/bin/python3 -m engp_cfx_sync_monitor.main
```
