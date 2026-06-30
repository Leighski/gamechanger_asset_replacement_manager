# Component Specification

## Required fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique canonical ID (e.g. `COLLAR_0004`) |
| `name` | string | Friendly display name |
| `category` | enum | Component category |
| `description` | string | Human-readable description |
| `version` | string | Semantic component version |
| `status` | enum | Draft / Review / Approved / Certified / Deprecated |
| `preview_image` | string | Relative path to PNG preview |
| `metadata` | object | Extensible key-value metadata |
| `tags` | string[] | Searchable tags |
| `created_at` | ISO datetime | Creation timestamp |
| `modified_at` | ISO datetime | Last modification |
| `author` | string | Author or team |
| `notes` | string | Operator notes |
| `legacy_ids` | string[] | Backwards-compatible slug IDs |

## Assets (`assets`)

| Field | Purpose |
|-------|---------|
| `png_preview` | PNG thumbnail for browser |
| `svg_preview` | Vector preview (future) |
| `psd_layer_ref` | PSD layer reference (future renderer) |
| `mask_ref` | Segmentation mask (future) |
| `geometry` | Geometry definition object |
| `anchor_points` | Rendering anchor points |
| `rendering_metadata` | Renderer consumption hints |

## Dependencies

`dependencies` lists other component IDs required by this component.

## Version history

`version_history` tracks changes with version, date, notes, and author.
