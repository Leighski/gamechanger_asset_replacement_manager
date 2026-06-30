# Image Manifest Format

**Path in .gjs:** `references/manifest.json`  
**Schema version:** 1.0

---

## Structure

```json
{
  "schema_version": "1.0",
  "images": [
    {
      "image_id": "a1b2c3d4e5f67890",
      "filename": "front_view.png",
      "import_date": "2026-06-30T11:00:00+00:00",
      "width": 1920,
      "height": 1080,
      "file_size": 245760,
      "colour_profile": "sRGB",
      "checksum": "sha256hex...",
      "orientation": 0,
      "tags": ["Front View"],
      "notes": "",
      "validation_status": "Passed",
      "analysis_status": "Not started",
      "sort_order": 0,
      "storage_path": "references/images/a1b2c3d4e5f67890.png",
      "media_type": "image/png"
    }
  ]
}
```

---

## Fields

| Field | Description |
|-------|-------------|
| `image_id` | Unique 16-character hex identifier |
| `filename` | Display filename |
| `import_date` | ISO 8601 UTC timestamp |
| `width` / `height` | Pixel dimensions after EXIF transpose |
| `file_size` | Byte size of stored image |
| `colour_profile` | sRGB, ICC, or empty |
| `checksum` | SHA-256 hex digest of stored bytes |
| `orientation` | Display rotation metadata (0, 90, 180, 270) |
| `tags` | Category tags (multiple allowed) |
| `notes` | Operator notes |
| `validation_status` | Per-image validation state |
| `analysis_status` | Future AI analysis placeholder |
| `sort_order` | Gallery ordering |
| `storage_path` | Path within .gjs ZIP |
| `media_type` | MIME type |

---

## Categories

Front View, Rear View, Side View, Detail, Collar, Sleeve, Pattern, Manufacturer, Badge, Sponsor, Texture, Other
