# Colour Analysis

## Measured colours

| Name | Typical Design Spec field |
|------|---------------------------|
| Primary Colour | `primary_colour` |
| Secondary Colour | `secondary_colour` |
| Accent Colour | `third_colour` |
| Trim Colour | `trim_colour` |
| Collar Colour | `collar_colour` |
| Sleeve Colour | `sleeve_colour` |

## Output channels

Each `ColourMeasurement` includes:

- **RGB** — `(R, G, B)` integers 0–255
- **HSV** — Hue (°), Saturation (%), Value (%)
- **LAB** — Approximate CIELAB (L*, a*, b*)
- **Hex** — `#RRGGBB`
- **Confidence** — 0–100%
- **Catalogue match** — Nearest Gamechanger swatch name when within threshold

## Method

1. Segment shirt pixels using the background mask.
2. Quantise RGB to 16-step bins.
3. Rank clusters by pixel count.
4. Assign top clusters to named colour slots.
5. Derive confidence from cluster size and intra-cluster variance.

## Catalogue swatches (Phase 1)

Sky Blue, White, Navy, Red, Black, Gold — nearest-Euclidean match in RGB space.
