# Batch Rendering Guide

## Overview

Batch rendering processes multiple approved projects sequentially through the Production PSD Renderer. Parallel rendering is not supported — each project completes before the next begins.

## Starting a batch

1. Open **Production → Queue**
2. Accept suggestions until projects show **Ready to Render**
3. Click **Batch Render Approved**
4. Or use **Tools → Batch Processing**

## Progress display

The Batch Render dialog shows:

- **Queue position** — current job index and project name
- **Current stage** — PSD pipeline stage (Open PSD, Apply colours, etc.)
- **Elapsed time** — time for current render
- **Estimated remaining** — based on average completed render times

## Controls

| Control | Action |
|---------|--------|
| Pause | Stop dequeuing new jobs; current render completes |
| Resume | Continue queue processing |
| Cancel | Abort remaining jobs |
| Retry Failed | Re-queue failed jobs |
| Close | Dismiss dialog after batch ends |

## Output

Each project writes to its configured `output_folder/renders/`:

- `{project_name}_render.psd`
- `{project_name}_preview.png`
- `render_log.json`

## Audit

Each successful render records:

- Project history events (Render Started, Completed, PSD Saved, PNG Generated)
- Production audit chain of custody

## Performance target

The queue is optimised for **100 sequential renders** without application restart. Memory is released between jobs via working-copy isolation per render.

## Background processing

Batch renders run on a background `QThread` to keep the UI responsive during long production runs.
