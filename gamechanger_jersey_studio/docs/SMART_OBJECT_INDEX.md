# Smart Object Index

## Purpose

Index Smart Objects inside registered PSD templates. **Read-only** — no editing in alpha.10.

## Record schema

```json
{
  "smart_object_id": "SO0001",
  "name": "Collar Smart Object",
  "layer_id": "L0005",
  "parent_group": "L0002",
  "offset_x": 960,
  "offset_y": 200,
  "width": 480,
  "height": 220
}
```

## Detection

`PSDTemplateLoader` identifies layers with `kind == "smartobject"` during PSD analysis. `SmartObjectService` provides query methods:

- `index(analysis)` — all Smart Objects
- `find_by_name(analysis, name)`
- `find_by_id(analysis, smart_object_id)`
- `in_group(analysis, parent_group)`

## Broadcast v1 Smart Objects

| ID | Name | Purpose |
|----|------|---------|
| SO0001 | Collar Smart Object | Collar component placement |
| SO0002 | Pattern Smart Object | Pattern overlay |

Mapped via `layer_mappings.json` using `smart_object_id`.
