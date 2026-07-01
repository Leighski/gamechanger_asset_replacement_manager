# Export Specification

## Output location

All production render outputs are written under the project export folder:

```
{output_folder}/renders/{project_name}_{timestamp}/
```

`PSDExportService.build_output_dir()` creates this directory automatically.

## Files produced

| File | Description |
|------|-------------|
| `{project_name}_working.psd` | Working copy of the template (mutated during render) |
| `{project_name}_render.psd` | Final layered PSD output |
| `{project_name}_preview.png` | Flattened composite preview |
| `render_log.json` | Structured render log with stage timings |

## Render log schema

`PSDRenderLog` (`models/psd_render.py`):

```json
{
  "schema_version": "1.0",
  "template_id": "TEMPLATE_BROADCAST_0001",
  "template_version": "1.0.0",
  "project_name": "Coventry City Home 2026",
  "started_at": "2026-06-30T15:38:01+00:00",
  "completed_at": "2026-06-30T15:38:02+00:00",
  "success": true,
  "total_ms": 1127.3,
  "stages": [
    {"stage": "Open PSD template", "duration_ms": 72.29, "message": "..."}
  ],
  "component_ids": {"collar_style": "COLLAR_0002"},
  "colours_applied": {"primary_colour": "#69B3E7"},
  "patterns_applied": ["Pattern Smart Object"],
  "textures_applied": ["Texture Overlay"],
  "smart_objects_updated": ["SO0001"],
  "layers_toggled": ["show:Base Shirt"],
  "warnings": [],
  "errors": [],
  "validation_issues": []
}
```

## PNG preview

- Generated from `psd.composite()` after all mutations
- Full canvas resolution (e.g. 2400×3000 for Broadcast v1)
- RGB PNG, no alpha channel in file format (composite is flattened)

## PSD output

- Layer structure preserved from template
- Blend modes and adjustment layers untouched unless a mapped pixel layer is explicitly tinted
- Smart Object contents updated where mappings apply

## Project history events

| Event | When |
|-------|------|
| Render Started | Before pipeline begins |
| Render Completed | Successful export |
| Render Failed | Validation or pipeline error |
| PSD Saved | `*_render.psd` written |
| PNG Generated | `*_preview.png` written |

## Example deliverables

See `docs/examples/`:

- `GJS011_COVENTRY_RENDER.psd`
- `GJS011_COVENTRY_PREVIEW.png`
- `GJS011_RENDER_LOG.json`
- `GJS011_BENCHMARK.json`
