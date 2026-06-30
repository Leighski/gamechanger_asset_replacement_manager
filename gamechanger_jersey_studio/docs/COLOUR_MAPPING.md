# Colour Mapping

## Supported fields

| Role      | Design Specification field |
|-----------|----------------------------|
| Primary   | `primary_colour`           |
| Secondary | `secondary_colour`         |
| Accent    | `third_colour`             |
| Trim      | `trim_colour`              |
| Sleeve    | `sleeve_colour`            |
| Collar    | `collar_colour`            |

## Implementation

`ColourMapper.tint_rgba()` applies solid hex colours to catalogue preview PNGs using luminance-weighted tinting. The source alpha channel is preserved.

## Layer assignment

- **Base body** — `primary_colour` on `material_style` component
- **Sleeves** — `sleeve_colour` (falls back to secondary/primary)
- **Collar** — `collar_colour`
- **Trim** — `trim_colour` (falls back to third colour)
- **Pattern** — `secondary_colour` (falls back to primary)

Gradients are not supported in alpha.9; solid mapping only.
