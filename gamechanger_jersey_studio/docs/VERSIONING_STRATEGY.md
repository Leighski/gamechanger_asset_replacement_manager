# Versioning Strategy

## Catalogue versioning

Each category manifest includes `catalogue_version` (e.g. `1.0.0`). Catalogues are versioned **independently** — updating collars does not require a patterns bump.

## Component versioning

Each component has its own `version` field and `version_history` array.

| Change type | Version bump |
|-------------|--------------|
| Metadata or tag update | Patch (1.0.1) |
| Asset or geometry change | Minor (1.1.0) |
| Breaking ID or dependency change | Major (2.0.0) |

## Design Specification references

Projects store the component `id` at time of assignment. If a component is deprecated, validation emits a **warning** but does not block loading.

## Schema versioning

`ComponentLibrary.schema_version` tracks the top-level library schema (currently `1.0`).
