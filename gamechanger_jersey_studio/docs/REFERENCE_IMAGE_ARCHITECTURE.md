# Reference Image Architecture

**Version:** 1.0.0-alpha.5 · Build 005

Reference images are **immutable source evidence** — not the Design Specification. Future AI analysis will interpret them; operators review them. No subsystem may edit image pixels.

---

## Principles

1. **Evidence, not specification** — images inform the Design Specification; they do not replace it
2. **Immutability** — import, replace, delete only; no in-app pixel editing
3. **Manifest-first** — AI and tooling read `references/manifest.json`, not folder scans
4. **Portable** — image bytes live inside `.gjs`; thumbnails live in workspace only

---

## Storage

```
My_Project.gjs
├── manifest.json
├── history.json
├── design/specification.json
└── references/
    ├── manifest.json          # Image metadata (canonical index)
    └── images/
        └── {image_id}.png     # Immutable image bytes

cache/workspace/{project_id}/
└── reference_thumbnails/
    └── {image_id}.png         # Generated thumbnails (not in .gjs)
```

---

## Components

| Layer | Path |
|-------|------|
| Model | `models/reference_image.py` |
| Import I/O | `services/reference_image_io.py` |
| Service | `services/reference_image_service.py` |
| Validation | `services/reference_image_validation.py` |
| Thumbnails | `services/reference_thumbnail_service.py` |
| Byte store | `services/reference_image_store.py` |
| UI gallery | `ui/widgets/reference_images_panel.py` |
| UI viewer | `ui/widgets/reference_image_viewer.py` |
| UI card | `ui/widgets/reference_image_card.py` |

---

## Supported formats

PNG, JPEG, TIFF, WEBP, PSD (flattened composite on import)

---

## Operations

Import, Replace, Delete, Duplicate, Rotate (metadata), Rename, Retag, Reorder, Reveal in Finder, Copy Path (via project file), View

---

## History events

- Reference Image Imported
- Reference Image Deleted
- Reference Image Replaced
- Reference Image Retagged
- Reference Image Renamed
- Reference Image Viewed
