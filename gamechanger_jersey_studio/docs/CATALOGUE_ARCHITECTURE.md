# Catalogue Architecture

**Build:** 1.0.0-alpha.8 (GJS-008)

## Purpose

The Component Library is the **permanent source of all reusable design components**. The Design Specification references catalogue IDs (e.g. `COLLAR_0004`), not free-text descriptions. Future AI interpretation and PSD rendering will consume these assets.

## Layout

```
config/component_library/
├── collars/manifest.json
├── sleeves/manifest.json
├── patterns/manifest.json
├── trims/manifest.json
├── materials/manifest.json
├── textures/manifest.json
├── lighting_profiles/manifest.json
├── shadow_profiles/manifest.json
├── effects/manifest.json
├── build_profiles/manifest.json
├── validation_profiles/manifest.json
├── colour_palettes/manifest.json
├── previews/              # PNG preview assets
└── catalogue_history.json # Operation audit trail

services/catalogue/
├── loader.py
├── validator.py
├── search.py
├── resolver.py
├── import_export.py
└── history.py

services/catalogue_manager_service.py   # Orchestration
services/design_catalogue_service.py    # Bridge to DesignCatalogues
```

## Separation

| Layer | Responsibility |
|-------|----------------|
| Component Library | Certified reusable assets with metadata |
| DesignCatalogues | Legacy bridge for editor dropdowns |
| Design Specification | Stores canonical component IDs |
| Catalogue Browser | Search, filter, preview components |
| Validation | Reference existence, status warnings |

## Backwards compatibility

Each component may define `legacy_ids` (e.g. `"crew"` → `COLLAR_0001`). Existing projects using slug IDs continue to validate and display friendly names.

## Performance

39 components load in **< 3ms** on reference hardware (see test suite).
