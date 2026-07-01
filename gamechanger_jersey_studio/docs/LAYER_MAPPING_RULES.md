# Layer Mapping Rules

## Principles

1. **Configuration only** — mappings live in JSON, not Python constants.
2. **Validation against analysis** — mapped layer names must exist in `analysis.json`.
3. **Smart Object awareness** — pattern and collar components may target Smart Objects.
4. **Render layer linkage** — optional `render_layer` connects PSD targets to Live Renderer layers.

## Resolution order

When publishing mappings for the Render Engine:

1. Load `layer_mappings.json` for active template
2. Match `design_spec_field` to rules
3. Resolve `smart_object_id` or `psd_layer_id` from analysis index
4. Expose via `PublishedTemplateMappings`

## Colour vs component fields

Colour fields (`primary_colour`, `collar_colour`) may map to the same PSD layer as their component counterparts. Multiple rules per field are supported.

## Adding a new template

1. Register in `config/templates/manifest.json`
2. Add template folder with `template.json`, `layer_mappings.json`, `anchor_points.json`
3. Place PSD (optional for seed) and run analysis
4. Validate before certifying
