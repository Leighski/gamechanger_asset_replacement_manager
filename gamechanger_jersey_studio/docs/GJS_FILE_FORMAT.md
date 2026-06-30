# .gjs Project File Specification

**Format version:** 1.0  
**Work package:** GJS-002 / GJS-004 / GJS-005 / GJS-006 / GJS-007  
**Extension:** `.gjs`

## Overview

A Gamechanger Jersey Studio project is a portable ZIP archive with the `.gjs` extension. All durable project data lives inside this package. Runtime files (preview cache, thumbnails, undo buffers) are stored separately in the workspace folder and are **never** embedded in `.gjs`.

## Package structure

```
My_Project.gjs (ZIP, deflate)
├── manifest.json              # Required — project metadata
├── history.json               # Optional on read — project event history
├── design/
│   └── specification.json     # Optional on read — design specification (GJS-004+)
├── references/
│   ├── manifest.json          # Optional on read — image manifest (GJS-005+)
│   └── images/                # Immutable image bytes
│       └── {image_id}.png
├── vision/
│   └── analyses.json          # Optional on read — vision analysis archive (GJS-006+)
└── interpretation/
    └── results.json           # Optional on read — interpretation archive (GJS-007+)
```

Projects created before Build 004 omit `design/specification.json`. Projects created before Build 005 omit `references/`. Projects created before Build 006 omit `vision/`. Projects created before Build 007 omit `interpretation/`. On open, missing members are initialised empty. On save, all members are written.

Future work packages may add additional members (for example `reports/`) without breaking the format.

## manifest.json

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format_version` | string | yes | Schema version (`"1.0"`) |
| `project_id` | string | yes | Stable runtime workspace identifier |
| `project_name` | string | yes | Display name |
| `club_name` | string | yes | Club name |
| `competition` | string | yes | Competition name |
| `season` | string | yes | Season label |
| `kit_type` | string | yes | Home, Away, Third, Goalkeeper, Women's |
| `build_profile` | string | yes | Default: Gamechanger Broadcast |
| `output_folder` | string | yes | Original output directory |
| `project_notes` | string | no | Free text |
| `author` | string | yes | Project author |
| `created_at` | string | yes | ISO 8601 UTC timestamp |
| `modified_at` | string | yes | ISO 8601 UTC timestamp |
| `application_version` | string | yes | Jersey Studio version at creation |
| `status` | string | yes | Draft, Active, Archived |
| `reference_image_count` | integer | yes | Count placeholder for GJS-003+ |
| `generated_output_count` | integer | yes | Count placeholder for future builds |
| `validation_status` | string | yes | Not started, Pending, Passed, Failed |

## history.json

```json
{
  "entries": [
    {
      "timestamp": "2026-06-29T12:00:00+00:00",
      "event": "Project Created",
      "application_version": "0.2.0",
      "user": "Author Name",
      "details": "optional"
    }
  ]
}
```

### Standard events

- Project Created
- Opened
- Saved
- Closed
- Recovery Restored
- Duplicated
- Archived
- Deleted
- Design Specification Changed

## design/specification.json

Canonical jersey design data. See `docs/DESIGN_SPECIFICATION.md` for the full schema.

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Design spec schema (`"1.0"`) |
| `club` | string | Club name |
| `competition` | string | Competition |
| `season` | string | Season |
| `kit_type` | string | Kit type enum value |
| `manufacturer` | string | Kit manufacturer |
| `primary_colour` … `trim_colour` | string | Hex colour values |
| `pattern` | string | Catalogue pattern id |
| `pattern_scale` | float | 0.1 – 5.0 |
| `pattern_rotation` | float | Degrees |
| `pattern_opacity` | float | 0.0 – 1.0 |
| `sleeve_style` | string | Catalogue id |
| `collar_style` | string | Catalogue id |
| `trim_style` | string | Free text |
| `material_style` | string | Catalogue id |
| `shadow_style` | string | Catalogue id |
| `lighting_style` | string | Catalogue id |
| `texture_style` | string | Catalogue id |
| `output_profile` | string | Output profile enum |
| `validation_status` | string | Validation state |
| `operator_notes` | string | Operator notes |

## Workspace (not part of .gjs)

Runtime workspace path:

```
cache/workspace/{project_id}/
├── preview_cache/
├── thumbnails/
├── temp_renders/
├── undo/
└── recovery/
    └── autosave.gjs
```

Autosave writes only to `recovery/autosave.gjs`. The primary `.gjs` file is never overwritten during autosave.

## Session state

Unclean shutdown is tracked in `cache/session_state.json`. On next launch, recovery copies are offered if `clean_shutdown` is `false`.

## Portability

Copy the `.gjs` file to another machine. Open via **File → Open Project**. Workspace folders are recreated automatically from `project_id`.
