# Catalogue JSON Format

## Category manifest

Path: `config/component_library/{category}/manifest.json`

```json
{
  "catalogue_id": "collars",
  "catalogue_version": "1.0.0",
  "category": "collars",
  "components": [ /* CatalogueComponent[] */ ]
}
```

## Component example

```json
{
  "id": "COLLAR_0004",
  "name": "Mandarin",
  "category": "collars",
  "description": "Standing mandarin collar",
  "version": "1.0.0",
  "status": "Certified",
  "preview_image": "previews/COLLAR_0004.png",
  "tags": ["collar"],
  "legacy_ids": ["mandarin"],
  "assets": {
    "png_preview": "previews/COLLAR_0004.png",
    "psd_layer_ref": "",
    "mask_ref": "",
    "geometry": {},
    "anchor_points": [],
    "rendering_metadata": {}
  },
  "version_history": [
    {
      "version": "1.0.0",
      "date": "2026-06-30T12:00:00+00:00",
      "notes": "Initial certified release",
      "author": "Gamechanger"
    }
  ]
}
```

## Import / export

Individual components export as standalone JSON files. Import merges into the category manifest.

## Legacy format

`config/catalogues/*.json` remains supported as fallback when the Component Library is absent.
