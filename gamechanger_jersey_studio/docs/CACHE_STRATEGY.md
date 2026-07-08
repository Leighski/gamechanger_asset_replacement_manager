# Cache Strategy

## Per-layer cache

`PreviewCache` stores rendered layer images in memory keyed by:

- Layer ID
- Render quality and dimensions
- Relevant Design Specification field values for that layer

## Invalidation

Changing a single property (e.g. `collar_colour`) invalidates only the **collar** layer key. Unchanged layers are reused on the next render.

Quality or dimension changes invalidate all layers (new cache keys).

## Statistics

`RenderStats` exposes:

- `cache_hits` / `cache_misses`
- Per-layer `cache_hit` flag in `layer_timings`
- Estimated memory usage (RGBA byte count)

## Disk cache

`LiveRendererService.cache_disk_root()` provisions `workspace/preview_cache/` for future disk persistence. Alpha.9 uses in-memory cache only.

## UI

The Renderer Inspector displays cache hits/misses and per-layer timings for optimisation.
