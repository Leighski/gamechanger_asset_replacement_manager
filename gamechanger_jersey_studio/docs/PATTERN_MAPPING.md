# Pattern Mapping

## Design Specification inputs

- `pattern` — catalogue pattern ID (canonical or legacy slug)
- `pattern_scale` — 0.1–5.0
- `pattern_rotation` — degrees (−360 to 360)
- `pattern_opacity` — 0.0–1.0

## Implementation

`PatternMapper.apply_pattern()`:

1. Loads the certified pattern component preview.
2. Tints with the secondary colour via `ColourMapper`.
3. Resizes by scale relative to canvas dimensions.
4. Rotates by `pattern_rotation`.
5. Tiles across the layer canvas.
6. Alpha-composites onto the pattern layer with `pattern_opacity`.

Patterns are applied on an independent layer between trim and texture.
