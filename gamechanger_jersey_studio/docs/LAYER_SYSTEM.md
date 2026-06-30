# Layer System

## Render order (bottom → top)

1. Presentation background
2. Base body (material + primary colour)
3. Sleeves
4. Collar
5. Trim
6. Pattern
7. Texture
8. Shadows
9. Lighting
10. Highlights

## Catalogue mapping

| Layer                    | Design Spec fields                          |
|--------------------------|---------------------------------------------|
| Base body                | `material_style`, `primary_colour`          |
| Sleeves                  | `sleeve_style`, `sleeve_colour`             |
| Collar                   | `collar_style`, `collar_colour`               |
| Trim                     | `trim_style`, `trim_colour`                 |
| Pattern                  | `pattern`, scale/rotation/opacity, colours  |
| Texture                  | `texture_style`, `material_style`           |
| Shadows                  | `shadow_style`                              |
| Lighting / Highlights    | `lighting_style`                            |
| Presentation background  | `RendererSettings.background_colour`        |

## Debugging

Each layer is toggleable in the Live Preview panel. Hidden layers are skipped during compositing but remain in the cache.

## Rules

- Every visual element must come from a certified catalogue component.
- No procedural geometry when an approved component exists.
- Legacy slugs (`v-neck`, `hoops`) resolve to canonical IDs before assembly.
