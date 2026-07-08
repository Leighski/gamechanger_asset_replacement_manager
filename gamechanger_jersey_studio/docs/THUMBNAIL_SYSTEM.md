# Thumbnail System

Reference image thumbnails are **workspace-only** — never stored in `.gjs`.

---

## Location

```
cache/workspace/{project_id}/reference_thumbnails/{image_id}.png
```

---

## Generation

- Triggered on import, replace, duplicate, and project open
- Size: 240×240 max (aspect preserved, Lanczos resampling)
- Rotation metadata applied before scaling
- Regenerated when image is replaced or orientation changes

---

## Service

`services/reference_thumbnail_service.py` — `ReferenceThumbnailService`

```python
service.generate(project_id, image_id, image_bytes, orientation=0)
service.remove(project_id, image_id)
service.clear_project(project_id)
```

---

## UI usage

- Reference image cards display workspace thumbnails
- Project Dashboard shows first-image preview thumbnail
