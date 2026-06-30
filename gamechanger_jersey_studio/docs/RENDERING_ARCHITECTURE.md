# Rendering Architecture — Gamechanger Jersey Studio

## Overview

The Live Renderer assembles jersey previews from **certified Component Library** assets. It is the visual feedback engine for Design Specification editing — not the production PSD renderer.

## Subsystem layout

```
services/rendering/
├── engine.py              RenderingEngine — pipeline orchestration
├── component_assembler.py ComponentAssembler — resolve & load catalogue PNGs
├── layer_manager.py       LayerManager — order, visibility, composite
├── colour_mapper.py       ColourMapper — solid colour mapping
├── pattern_mapper.py      PatternMapper — scale, rotation, opacity
├── texture_mapper.py      TextureMapper — non-destructive material overlays
├── lighting_engine.py     LightingEngine — catalogue shadow/light helpers
├── preview_cache.py       PreviewCache — per-layer in-memory cache
├── render_queue.py        RenderQueue — coalesce rapid render requests
└── errors.py              RenderingError

services/live_renderer_service.py  Project integration & settings
```

## Data flow

1. **Design Specification** + **RendererSettings** enter `RenderingEngine.render()`.
2. `ComponentAssembler` resolves canonical catalogue IDs via `ComponentReferenceResolver`.
3. Each visible layer is built (or retrieved from `PreviewCache`).
4. `LayerManager` alpha-composites layers in fixed order.
5. PNG bytes and `RenderStats` return to the UI.

## Quality modes

| Mode     | Size    | Resampling |
|----------|---------|------------|
| Draft    | 256×320 | Bilinear   |
| Standard | 400×500 | Bilinear   |
| High     | 600×750 | Lanczos    |

## Project persistence

Renderer settings persist as `renderer/settings.json` inside `.gjs`. **Rendered previews are never stored** in the project package.

## Logging

- Render started / completed
- Per-layer timings (debug)
- Cache hit/miss summary
- Render failures

## Future production renderer

The production PSD pipeline (alpha.10+) should reuse `ComponentAssembler`, mappers, and layer ordering — swapping PNG preview assets for PSD layer references.
